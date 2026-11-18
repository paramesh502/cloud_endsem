# models.py
# Core data structures for the simulation — a Node (physical server)
# and a Job (batch task to be scheduled).

from dataclasses import dataclass


@dataclass
class Job:
    job_id: str
    cpu: float      # cores requested
    mem: float      # normalised memory (0-1 scale)
    duration: float # seconds from create to finish
    is_short: bool  # True if duration is below the median


@dataclass
class Node:
    machine_id: str
    cpu_cap: float   # total CPU cores on this machine
    mem_cap: float   # total normalised memory
    cpu_left: float  # how much CPU is still free
    mem_left: float  # how much memory is still free
    active: bool = False  # flipped to True the moment a job lands here

    def can_fit(self, job: Job) -> bool:
        # Reject degenerate nodes and check both dimensions
        if self.cpu_cap <= 0 or self.mem_cap <= 0:
            return False
        return self.cpu_left >= job.cpu and self.mem_left >= job.mem

    def place(self, job: Job) -> None:
        self.cpu_left -= job.cpu
        self.mem_left -= job.mem
        self.active = True

    def remove(self, job: Job) -> None:
        # Called during consolidation rollback or migration
        self.cpu_left += job.cpu
        self.mem_left += job.mem

    def utilization(self):
        # Returns (cpu_fraction_used, mem_fraction_used)
        cpu_util = (self.cpu_cap - self.cpu_left) / self.cpu_cap if self.cpu_cap > 0 else 0.0
        mem_util = (self.mem_cap - self.mem_left) / self.mem_cap if self.mem_cap > 0 else 0.0
        return cpu_util, mem_util
