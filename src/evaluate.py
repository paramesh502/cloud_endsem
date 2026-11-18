# evaluate.py
# Computes cluster-level metrics after a scheduling run.
# Called with the final node state and the accepted/rejected counts
# from whichever scheduler was used.

from typing import Dict, List
from src.models import Node
from src.power import compute_cluster_energy


def compute_metrics(nodes: List[Node], accepted: int, rejected: int) -> Dict:
    active_nodes = [n for n in nodes if n.active]

    rfi_values  = []
    util_values = []

    for node in active_nodes:
        cpu_util, mem_util = node.utilization()
        util_values.append((cpu_util + mem_util) / 2.0)

        f_c = node.cpu_left / node.cpu_cap if node.cpu_cap > 0 else 0.0
        f_m = node.mem_left / node.mem_cap if node.mem_cap > 0 else 0.0

        # Skip nodes with nothing left — no fragmentation to measure
        if f_c == 0.0 and f_m == 0.0:
            continue

        rfi = 1.0 - min(f_c, f_m) / (max(f_c, f_m) + 1e-12)
        rfi_values.append(rfi)

    mean_rfi  = float(sum(rfi_values)  / len(rfi_values))  if rfi_values  else 0.0
    mean_util = float(sum(util_values) / len(util_values)) if util_values else 0.0
    energy    = compute_cluster_energy(nodes)

    return {
        "jobs_accepted":   accepted,
        "jobs_rejected":   rejected,
        "avg_rfi":         round(mean_rfi,  4),
        "avg_utilization": round(mean_util,  4),
        "active_nodes":    len(active_nodes),
        "energy_kwh":      round(energy, 4),
    }
