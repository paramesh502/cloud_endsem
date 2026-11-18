# power.py
# Linear server power model from the paper:
#   P(u) = P_idle + (P_max - P_idle) * u
#
# u is the CPU utilisation fraction of an active node.
# Nodes that are powered off draw 0 W.

from typing import List
from src.models import Node

P_IDLE: float = 200.0  # watts at idle
P_MAX:  float = 400.0  # watts at full load


def node_power(node: Node) -> float:
    if not node.active:
        return 0.0
    cpu_util, _ = node.utilization()
    return P_IDLE + (P_MAX - P_IDLE) * cpu_util


def compute_cluster_power(nodes: List[Node]) -> float:
    return sum(node_power(n) for n in nodes)


def compute_cluster_energy(nodes: List[Node], T: float = 3600.0) -> float:
    # T is the observation window in seconds (default 1 hour)
    # Returns energy in kWh
    total_watts = compute_cluster_power(nodes)
    return total_watts * T / 3_600_000.0
