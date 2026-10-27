"""
power.py
--------
Linear server power model used in energy estimation.

  P(u) = P_idle + (P_max - P_idle) * u

where u is the CPU utilisation fraction of an active node.
Inactive (powered-off) nodes draw 0 W.
"""

from typing import List
from src.models import Node

# Power constants (Watts)
P_IDLE: float = 200.0   # idle power per server
P_MAX:  float = 400.0   # peak power per server


def node_power(node: Node) -> float:
    """Return instantaneous power draw of a single node in Watts."""
    if not node.active:
        return 0.0
    cpu_util, _ = node.utilization()
    return P_IDLE + (P_MAX - P_IDLE) * cpu_util


def compute_cluster_power(nodes: List[Node]) -> float:
    """Return total cluster power in Watts."""
    return sum(node_power(n) for n in nodes)


def compute_cluster_energy(nodes: List[Node], T: float = 3600.0) -> float:
    """
    Return total cluster energy in kWh.

    Parameters
    ----------
    nodes : list of Node
    T     : observation window in seconds (default 1 hour)
    """
    total_watts = compute_cluster_power(nodes)
    return total_watts * T / 3_600_000.0   # W·s → kWh
