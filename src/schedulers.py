# schedulers.py
# Four resource schedulers implemented for comparison in the FAS paper:
#   1. First-Fit (FF)
#   2. Best-Fit Decreasing (BFD)
#   3. Dominant Resource Fairness (DRF)
#   4. Fragmentation-Aware Scheduler (FAS) — the proposed method
#
# Each scheduler takes a job list and a fresh copy of the node list,
# and returns: (placements dict, active node count, accepted count, rejected count)

import copy
from typing import Dict, List, Tuple

from src.models import Node, Job
from src import consolidation as cons
from src.power import compute_cluster_energy

SchedulerResult = Tuple[Dict[str, List[Job]], int, int, int]


# --- First-Fit -----------------------------------------------------------
# Iterate nodes in order, place each job on the first node that fits.
# Simple and fast but doesn't optimise packing at all.

def schedule_ff(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    placements: Dict[str, List[Job]] = {n.machine_id: [] for n in nodes}
    accepted = 0
    rejected = 0

    for job in jobs:
        placed = False
        for node in nodes:
            if node.can_fit(job):
                node.place(job)
                placements[node.machine_id].append(job)
                accepted += 1
                placed = True
                break
        if not placed:
            rejected += 1

    active_count = sum(1 for n in nodes if n.active)
    return placements, active_count, accepted, rejected


# --- Best-Fit Decreasing -------------------------------------------------
# Sort jobs largest-first, then pack each into the node that leaves the
# least slack after placement (tightest fit).

def schedule_bfd(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    sorted_jobs = sorted(jobs, key=lambda j: j.cpu + j.mem, reverse=True)
    placements: Dict[str, List[Job]] = {n.machine_id: [] for n in nodes}
    accepted = 0
    rejected = 0

    for job in sorted_jobs:
        best_node  = None
        best_slack = float("inf")

        for node in nodes:
            if node.can_fit(job):
                slack = (node.cpu_left - job.cpu) + (node.mem_left - job.mem)
                if slack < best_slack:
                    best_slack = slack
                    best_node  = node

        if best_node is not None:
            best_node.place(job)
            placements[best_node.machine_id].append(job)
            accepted += 1
        else:
            rejected += 1

    active_count = sum(1 for n in nodes if n.active)
    return placements, active_count, accepted, rejected


# --- Dominant Resource Fairness (DRF) ------------------------------------
# For each job, pick the node where the dominant share (max of cpu_share
# and mem_share after placement) is lowest.

def schedule_drf(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    placements: Dict[str, List[Job]] = {n.machine_id: [] for n in nodes}
    accepted = 0
    rejected = 0

    for job in jobs:
        best_node = None
        best_dom  = float("inf")

        for node in nodes:
            if not node.can_fit(job):
                continue
            cpu_share = (node.cpu_cap - node.cpu_left + job.cpu) / node.cpu_cap
            mem_share = (node.mem_cap - node.mem_left + job.mem) / node.mem_cap
            dom_share = max(cpu_share, mem_share)
            if dom_share < best_dom:
                best_dom  = dom_share
                best_node = node

        if best_node is not None:
            best_node.place(job)
            placements[best_node.machine_id].append(job)
            accepted += 1
        else:
            rejected += 1

    active_count = sum(1 for n in nodes if n.active)
    return placements, active_count, accepted, rejected


# --- FAS helpers ---------------------------------------------------------

def _rfi_score(node: Node, job: Job) -> float:
    # Compute what the fragmentation looks like AFTER placing this job here.
    # We want to minimise this score across candidate nodes.
    #
    # score = RFI_after + w * leftover_total
    #
    # w = 2.0 for short jobs  → penalises leftover heavily (pack tight)
    # w = 0.5 for long jobs   → lenient about leftover (preserve space)

    f_c = max((node.cpu_left - job.cpu) / node.cpu_cap, 0.0)
    f_m = max((node.mem_left - job.mem) / node.mem_cap, 0.0)

    rfi_after      = 1.0 - min(f_c, f_m) / (max(f_c, f_m) + 1e-12)
    leftover_total = f_c + f_m
    w = 2.0 if job.is_short else 0.5

    return rfi_after + w * leftover_total


# --- Fragmentation-Aware Scheduler (FAS) ---------------------------------
# Algorithm 1 from the paper: score-based placement to minimise RFI,
# followed by Algorithm 2 (greedy consolidation) to power off idle nodes.

def schedule_fas(
    jobs: List[Job],
    nodes: List[Node],
) -> Tuple[Dict[str, List[Job]], int, int, int, int, float, float]:
    # Long large jobs go first so they get the best pick of nodes;
    # short jobs fill in the gaps afterwards.
    sorted_jobs = sorted(
        jobs,
        key=lambda j: (not j.is_short, j.cpu + j.mem),
        reverse=True,
    )

    placements: Dict[str, List[Job]] = {n.machine_id: [] for n in nodes}
    accepted = 0
    rejected = 0

    for job in sorted_jobs:
        best_node  = None
        best_score = float("inf")

        for node in nodes:
            if not node.can_fit(job):
                continue
            score = _rfi_score(node, job)
            if score < best_score:
                best_score = score
                best_node  = node

        if best_node is not None:
            best_node.place(job)
            placements[best_node.machine_id].append(job)
            accepted += 1
        else:
            rejected += 1

    # Measure energy before we start moving things around
    energy_before        = compute_cluster_energy(nodes)
    active_before_consol = sum(1 for n in nodes if n.active)

    # Run consolidation — drain least-utilised nodes and power them off
    cons.consolidate(nodes, placements, max_rounds=10)

    energy_after = compute_cluster_energy(nodes)
    active_count = sum(1 for n in nodes if n.active)
    nodes_freed  = active_before_consol - active_count

    return placements, active_count, accepted, rejected, nodes_freed, energy_before, energy_after
