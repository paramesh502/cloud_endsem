# consolidation.py
# Algorithm 2 from the paper: greedy all-or-nothing live migration.
#
# The idea is simple — find the least-loaded node in the cluster and try
# to move every job on it to some other node. If all jobs fit elsewhere,
# commit the moves and power off the source. If even one job can't move,
# roll everything back and leave the node alone.
#
# We repeat this until a full pass produces no freed nodes (converged).

from typing import Dict, List, Set
from src.models import Node, Job


def consolidate(
    nodes: List[Node],
    placements: Dict[str, List[Job]],
    max_rounds: int = 10,
) -> int:
    total_freed: int = 0
    freed_ids: Set[str] = set()

    for _round in range(max_rounds):
        # Sort active nodes by CPU utilisation ascending — drain the emptiest first
        sources = sorted(
            [n for n in nodes if n.active and n.machine_id not in freed_ids],
            key=lambda n: (n.cpu_cap - n.cpu_left) / n.cpu_cap
        )

        freed_this_round = 0

        for source in sources:
            jobs_on_source = placements.get(source.machine_id, [])
            if not jobs_on_source:
                continue

            tentative: List[tuple] = []
            all_moved = True

            for job in list(jobs_on_source):
                dest = None
                for candidate in nodes:
                    if candidate.machine_id == source.machine_id:
                        continue
                    if candidate.machine_id in freed_ids:
                        continue
                    if candidate.can_fit(job):
                        dest = candidate
                        break

                if dest is not None:
                    dest.place(job)
                    tentative.append((dest, job))
                else:
                    # Can't move this job — undo everything we just placed
                    for (d, j) in tentative:
                        d.remove(j)
                    all_moved = False
                    break

            if all_moved:
                # Clear the source node
                for job in list(jobs_on_source):
                    source.remove(job)
                placements[source.machine_id] = []
                source.active = False
                freed_ids.add(source.machine_id)

                # Update placement records for destination nodes
                for (dest, job) in tentative:
                    dest.active = True
                    placements.setdefault(dest.machine_id, []).append(job)

                freed_this_round += 1
                total_freed      += 1

        if freed_this_round == 0:
            break  # no progress this round, stop early

    return total_freed
