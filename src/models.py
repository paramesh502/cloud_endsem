"""
models.py
---------
Dataclasses for Node and Job used across the simulation.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Job:
    """Represents a batch task / workload to be scheduled."""
    job_id: str
    cpu: float          # cores demanded
    mem: float          # normalised memory demanded (0-1 scale)
    duration: float     # seconds
    is_short: bool      # True if duration <= median duration


@dataclass
class Node:
    """Represents a physical server in the cluster."""
    machine_id: str
    cpu_cap: float      # total CPU cores
    mem_cap: float      # total normalised memory (0-1 scale)
    cpu_left: float     # remaining CPU after current placements
    mem_left: float     # remaining memory after current placements
    active: bool = False  # True when at least one job is placed

    # ------------------------------------------------------------------ #
    # Scheduling primitives
    # ------------------------------------------------------------------ #

    def can_fit(self, job: Job) -> bool:
        """Return True if this node has enough resources for the job."""
        if self.cpu_cap <= 0 or self.mem_cap <= 0:
            return False
        return self.cpu_left >= job.cpu and self.mem_left >= job.mem

    def place(self, job: Job) -> None:
        """Allocate resources for the job and mark node active."""
        self.cpu_left -= job.cpu
        self.mem_left -= job.mem
        self.active = True

    def remove(self, job: Job) -> None:
        """Release resources occupied by the job."""
        self.cpu_left += job.cpu
        self.mem_left += job.mem
        # active flag is managed by the caller (consolidation) when needed

    def utilization(self):
        """Return (cpu_util_fraction, mem_util_fraction) for this node."""
        cpu_util = (self.cpu_cap - self.cpu_left) / self.cpu_cap if self.cpu_cap > 0 else 0.0
        mem_util = (self.mem_cap - self.mem_left) / self.mem_cap if self.mem_cap > 0 else 0.0
        return cpu_util, mem_util
