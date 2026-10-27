"""
schedulers.py
-------------
Implements four resource schedulers from (or compared against) the FAS paper:

  1. First-Fit (FF)       – baseline bin-packing
  2. Best-Fit Decreasing (BFD) – classic bin-packing heuristic
  3. DRF                  – Dominant Resource Fairness
  4. FAS                  – Fragmentation-Aware Scheduler (Algorithm 1)
                            with greedy consolidation (Algorithm 2)

Each scheduler accepts a job list and a FRESH deep copy of the node list,
and returns:
    placements       : dict  {machine_id: [Job, ...]}
    active_node_count: int
    accepted_count   : int
    rejected_count   : int
"""

import copy
from typing import Dict, List, Tuple

from src.models import Node, Job
from src import consolidation as cons
from src.power import compute_cluster_energy


# ------------------------------------------------------------------ #
# Type alias
# ------------------------------------------------------------------ #
SchedulerResult = Tuple[Dict[str, List[Job]], int, int, int]


# ================================================================== #
# 1. First-Fit (FF)
# ================================================================== #

def schedule_ff(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    """
    First-Fit scheduler.

    For each job, iterate nodes in order and place on the first one
    that has enough free resources.
    """
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


# ================================================================== #
# 2. Best-Fit Decreasing (BFD)
# ================================================================== #

def schedule_bfd(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    """
    Best-Fit Decreasing scheduler.

    Sort jobs descending by total demand (cpu + mem), then place each
    job on the node that leaves the least combined slack after placement.
    """
    sorted_jobs = sorted(jobs, key=lambda j: j.cpu + j.mem, reverse=True)
    placements: Dict[str, List[Job]] = {n.machine_id: [] for n in nodes}
    accepted = 0
    rejected = 0

    for job in sorted_jobs:
        best_node = None
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


# ================================================================== #
# 3. Dominant Resource Fairness (DRF)
# ================================================================== #

def schedule_drf(jobs: List[Job], nodes: List[Node]) -> SchedulerResult:
    """
    DRF-inspired scheduler.

    For each job, choose the node that results in the minimum dominant
    share after placement.  Dominant share = max(cpu_share, mem_share)
    where share_x = (used_x + demand_x) / capacity_x.
    """
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


# ================================================================== #
# 4. FAS – Fragmentation-Aware Scheduler  (Algorithm 1 + 2)
# ================================================================== #

def _rfi_score(node: Node, job: Job) -> float:
    """
    Compute placement score for the FAS scheduler.

    Lower score = preferred node.

    score = RFI_after - w * leftover_total

    where:
      f_c           = (cpu_left - job.cpu) / cpu_cap    (remaining CPU fraction)
      f_m           = (mem_left - job.mem) / mem_cap    (remaining mem fraction)
      RFI_after     = 1 - min(f_c, f_m) / (max(f_c, f_m) + ε)
      leftover_total= f_c + f_m
      w             = 2.0 for short jobs, 0.5 for long jobs
    """
    f_c = (node.cpu_left - job.cpu) / node.cpu_cap
    f_m = (node.mem_left - job.mem) / node.mem_cap

    # Clamp to zero in case of tiny floating-point underflow
    f_c = max(f_c, 0.0)
    f_m = max(f_m, 0.0)

    rfi_after      = 1.0 - min(f_c, f_m) / (max(f_c, f_m) + 1e-12)
    leftover_total = f_c + f_m

    w = 2.0 if job.is_short else 0.5
    return rfi_after - w * leftover_total


def schedule_fas(
    jobs: List[Job],
    nodes: List[Node],
) -> Tuple[Dict[str, List[Job]], int, int, int, int, float, float]:
    """
    FAS scheduler with post-placement consolidation.

    Returns
    -------
    placements        : {machine_id: [Job]}
    active_count      : nodes active AFTER consolidation
    accepted          : jobs accepted
    rejected          : jobs rejected
    nodes_freed       : nodes powered off by consolidation
    energy_before_kwh : energy before consolidation
    energy_after_kwh  : energy after consolidation
    """
    # Sort: long-large jobs first, then short-small
    # Tuple (not is_short, cpu+mem) sorted descending
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

    # Energy snapshot BEFORE consolidation
    energy_before = compute_cluster_energy(nodes)
    active_before_consol = sum(1 for n in nodes if n.active)

    # Run Algorithm 2 – greedy consolidation
    cons.consolidate(nodes, placements, max_rounds=10)

    # Energy snapshot AFTER consolidation
    energy_after = compute_cluster_energy(nodes)

    active_count = sum(1 for n in nodes if n.active)
    # nodes_freed = net reduction in active nodes due to consolidation
    nodes_freed  = active_before_consol - active_count
    return placements, active_count, accepted, rejected, nodes_freed, energy_before, energy_after
