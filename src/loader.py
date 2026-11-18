# loader.py
# Reads the Alibaba 2017 cluster trace and returns a list of Nodes and Jobs
# ready for the schedulers to consume.
#
# CSV column order (files have no header row):
#   server_event.csv : timestamp, machineID, event_type, event_detail,
#                      cpu_capacity, mem_capacity, disk
#   server_usage.csv : timestamp, machineID, cpu_util, mem_util, disk_util,
#                      load1, load5, load15
#   batch_task.csv   : create_ts, modify_ts, job_id, task_id, instance_num,
#                      status, plan_cpu, plan_mem

import os
import pandas as pd
import numpy as np
from src.models import Node, Job


def load_data(data_dir: str, n_jobs: int = 5000, random_state: int = 42):
    nodes = _load_nodes(data_dir)
    jobs  = _load_jobs(data_dir, n_jobs=n_jobs, random_state=random_state)
    return nodes, jobs


def _load_nodes(data_dir: str):
    # --- machine capacities from server_event.csv ---
    event_cols = ["timestamp", "machineID", "event_type", "event_detail",
                  "cpu_cap", "mem_cap", "disk"]
    ev = pd.read_csv(
        os.path.join(data_dir, "server_event.csv"),
        header=None,
        names=event_cols,
        dtype={"machineID": str, "event_type": str},
        low_memory=False,
    )

    # Only 'add' events carry capacity info
    ev = ev[ev["event_type"] == "add"].copy()
    ev["cpu_cap"] = pd.to_numeric(ev["cpu_cap"], errors="coerce")
    ev["mem_cap"] = pd.to_numeric(ev["mem_cap"], errors="coerce")
    ev = ev.dropna(subset=["cpu_cap", "mem_cap"])
    ev = ev[ev["cpu_cap"] > 0][ev["mem_cap"] > 0]
    ev = ev.drop_duplicates(subset="machineID", keep="first")
    ev = ev.set_index("machineID")[["cpu_cap", "mem_cap"]]

    # --- actual utilisation from server_usage.csv ---
    usage_cols = ["timestamp", "machineID", "cpu_util", "mem_util",
                  "disk_util", "load1", "load5", "load15"]
    us = pd.read_csv(
        os.path.join(data_dir, "server_usage.csv"),
        header=None,
        names=usage_cols,
        dtype={"machineID": str},
        low_memory=False,
    )
    us["cpu_util"] = pd.to_numeric(us["cpu_util"], errors="coerce")
    us["mem_util"] = pd.to_numeric(us["mem_util"], errors="coerce")
    us = us.dropna(subset=["cpu_util", "mem_util"])

    # Values are 0-100; convert to 0-1 fraction
    us["cpu_util"] = us["cpu_util"].clip(0, 100) / 100.0
    us["mem_util"] = us["mem_util"].clip(0, 100) / 100.0
    mean_util = us.groupby("machineID")[["cpu_util", "mem_util"]].mean()

    # --- merge and compute leftover resources ---
    merged = ev.join(mean_util, how="left")
    merged["cpu_util"] = merged["cpu_util"].fillna(0.0)  # no usage data = idle
    merged["mem_util"] = merged["mem_util"].fillna(0.0)
    merged["cpu_left"] = (merged["cpu_cap"] * (1.0 - merged["cpu_util"])).clip(lower=0)
    merged["mem_left"] = (merged["mem_cap"] * (1.0 - merged["mem_util"])).clip(lower=0)

    nodes = []
    for machine_id, row in merged.iterrows():
        nodes.append(Node(
            machine_id=str(machine_id),
            cpu_cap=float(row["cpu_cap"]),
            mem_cap=float(row["mem_cap"]),
            cpu_left=float(row["cpu_left"]),
            mem_left=float(row["mem_left"]),
            active=False,
        ))

    print(f"  Loaded {len(nodes)} nodes from server trace.")
    return nodes


def _load_jobs(data_dir: str, n_jobs: int = 5000, random_state: int = 42):
    task_cols = ["create_ts", "modify_ts", "job_id", "task_id",
                 "instance_num", "status", "plan_cpu", "plan_mem"]
    bt = pd.read_csv(
        os.path.join(data_dir, "batch_task.csv"),
        header=None,
        names=task_cols,
        dtype={"job_id": str, "task_id": str, "status": str},
        low_memory=False,
    )

    # Only use tasks that actually completed and have resource specs
    bt = bt[bt["status"] == "Terminated"].copy()
    bt["plan_cpu"] = pd.to_numeric(bt["plan_cpu"], errors="coerce")
    bt["plan_mem"] = pd.to_numeric(bt["plan_mem"], errors="coerce")
    bt = bt.dropna(subset=["plan_cpu", "plan_mem"])
    bt = bt[(bt["plan_cpu"] > 0) & (bt["plan_mem"] > 0)]

    bt["create_ts"] = pd.to_numeric(bt["create_ts"], errors="coerce")
    bt["modify_ts"]  = pd.to_numeric(bt["modify_ts"],  errors="coerce")
    bt = bt.dropna(subset=["create_ts", "modify_ts"])
    bt["duration"] = bt["modify_ts"] - bt["create_ts"]
    bt = bt[bt["duration"] >= 0]

    median_dur = bt["duration"].median()
    bt["is_short"] = bt["duration"] <= median_dur
    bt["uid"] = bt["job_id"].astype(str) + "_" + bt["task_id"].astype(str)

    if len(bt) > n_jobs:
        bt = bt.sample(n=n_jobs, random_state=random_state)

    # plan_cpu in the trace is in milli-cores (50 = 0.5 physical cores)
    # dividing by 100 makes it comparable to node cpu_left which is in cores
    jobs = []
    for _, row in bt.iterrows():
        jobs.append(Job(
            job_id=row["uid"],
            cpu=float(row["plan_cpu"]) / 100.0,
            mem=float(row["plan_mem"]),
            duration=float(row["duration"]),
            is_short=bool(row["is_short"]),
        ))

    print(f"  Loaded {len(jobs)} jobs from batch task trace.")
    return jobs
