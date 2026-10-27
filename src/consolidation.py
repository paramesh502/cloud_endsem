"""
consolidation.py
----------------
Algorithm 2 from the FAS paper: greedy all-or-nothing live migration.

For each round the algorithm tries to drain the least-utilised active
node by migrating ALL of its jobs to other nodes.  If every job fits,
the migration is committed and the source node is powered off.  If even
one job cannot be moved, the whole attempt is rolled back.

Convergence: stop when no node was successfully drained in a full pass.
"""

from typing import Dict, List, Set
from src.models import Node, Job


def consolidate(
    nodes: List[Node],
    placements: Dict[str, List[Job]],
    max_rounds: int = 10,
) -> int:
    """
    Run iterative consolidation on a cluster.

    Parameters
    ----------
    nodes       : list of Node objects (mutated in-place)
    placements  : dict mapping machine_id -> list[Job] (mutated in-place)
    max_rounds  : maximum consolidation passes

    Returns
    -------
    total_freed : number of nodes powered off across all rounds
    """
    total_freed: int = 0
    freed_ids: Set[str] = set()   # track nodes already powered off

    for _round in range(max_rounds):
        # Sources: active nodes sorted by INCREASING CPU utilisation
        # (least-loaded first — easiest to drain)
        sources = sorted(
            [n for n in nodes if n.active and n.machine_id not in freed_ids],
            key=lambda n: (n.cpu_cap - n.cpu_left) / n.cpu_cap
        )

        freed_this_round = 0

        for source in sources:
            jobs_on_source = placements.get(source.machine_id, [])
            if not jobs_on_source:
                continue

            tentative: List[tuple] = []   # (dest_node, job)
            all_moved = True

            for job in list(jobs_on_source):
                dest = None
                # Only migrate to nodes that are NOT the source and NOT already freed
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
                    # Cannot migrate this job → rollback all tentative moves
                    for (d, j) in tentative:
                        d.remove(j)
                        # Reset active flag if we over-placed (shouldn't happen, but be safe)
                        if d.cpu_cap - d.cpu_left <= 0:
                            d.active = False
                    all_moved = False
                    break

            if all_moved:
                # Commit: remove all jobs from source node
                for job in list(jobs_on_source):
                    source.remove(job)
                placements[source.machine_id] = []
                source.active = False
                freed_ids.add(source.machine_id)

                # Update placements for destination nodes
                for (dest, job) in tentative:
                    dest.active = True
                    placements.setdefault(dest.machine_id, []).append(job)

                freed_this_round += 1
                total_freed      += 1

        if freed_this_round == 0:
            # No progress in this round — converged
            break

    return total_freed
