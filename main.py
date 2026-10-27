"""
main.py
-------
Entry point for the FAS paper simulation.

Runs all four schedulers (FF, BFD, DRF, FAS) on the Alibaba 2017 trace
data and prints a comparison table of key metrics.
Results are also saved to results/metrics.json.

Usage:
    python main.py
"""

import copy
import json
import os
import sys

# Ensure the project root is on sys.path so `src` resolves correctly
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.loader    import load_data
from src.schedulers import schedule_ff, schedule_bfd, schedule_drf, schedule_fas
from src.evaluate  import compute_metrics
from src.power     import compute_cluster_energy

# ------------------------------------------------------------------ #
# Paths
# ------------------------------------------------------------------ #
DATA_DIR    = os.path.join(ROOT, "data", "alibaba-trace-2017")
RESULTS_DIR = os.path.join(ROOT, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


# ------------------------------------------------------------------ #
# Helper
# ------------------------------------------------------------------ #

def fresh_nodes(nodes):
    """Return a deep copy of the node list for isolated scheduler runs."""
    return copy.deepcopy(nodes)


# ------------------------------------------------------------------ #
# Main pipeline
# ------------------------------------------------------------------ #

def main():
    print("=" * 60)
    print("  FAS Paper Simulation – Alibaba Cluster Trace 2017")
    print("=" * 60)

    # 1. Load data
    print("\n[1/6] Loading data ...")
    nodes, jobs = load_data(DATA_DIR, n_jobs=5000)
    print(f"       Nodes: {len(nodes)}, Jobs: {len(jobs)}")

    results = {}

    # 2. First-Fit
    print("\n[2/6] Running FF scheduler ...", end="", flush=True)
    ff_nodes = fresh_nodes(nodes)
    ff_pl, ff_active, ff_acc, ff_rej = schedule_ff(jobs, ff_nodes)
    ff_metrics = compute_metrics(ff_nodes, ff_acc, ff_rej)
    results["FF"] = ff_metrics
    print(" done")

    # 3. Best-Fit Decreasing
    print("[3/6] Running BFD scheduler ...", end="", flush=True)
    bfd_nodes = fresh_nodes(nodes)
    bfd_pl, bfd_active, bfd_acc, bfd_rej = schedule_bfd(jobs, bfd_nodes)
    bfd_metrics = compute_metrics(bfd_nodes, bfd_acc, bfd_rej)
    results["BFD"] = bfd_metrics
    print(" done")

    # 4. DRF
    print("[4/6] Running DRF scheduler ...", end="", flush=True)
    drf_nodes = fresh_nodes(nodes)
    drf_pl, drf_active, drf_acc, drf_rej = schedule_drf(jobs, drf_nodes)
    drf_metrics = compute_metrics(drf_nodes, drf_acc, drf_rej)
    results["DRF"] = drf_metrics
    print(" done")

    # 5. FAS (with consolidation)
    print("[5/6] Running FAS scheduler (+ consolidation) ...", end="", flush=True)
    fas_nodes = fresh_nodes(nodes)
    (fas_pl, fas_active, fas_acc, fas_rej,
     fas_freed, fas_energy_before, fas_energy_after) = schedule_fas(jobs, fas_nodes)
    fas_metrics = compute_metrics(fas_nodes, fas_acc, fas_rej)
    fas_metrics["nodes_freed"]         = fas_freed
    fas_metrics["energy_before_kwh"]   = round(fas_energy_before, 4)
    fas_metrics["energy_savings_pct"]  = (
        round((fas_energy_before - fas_energy_after) / fas_energy_before * 100, 2)
        if fas_energy_before > 0 else 0.0
    )
    results["FAS"] = fas_metrics
    print(" done")

    # 6. Print comparison table
    print("\n[6/6] Results\n")
    _print_table(results)

    # 7. Save metrics
    metrics_path = os.path.join(RESULTS_DIR, "metrics.json")
    with open(metrics_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nMetrics saved to: {metrics_path}")

    return results


def _print_table(results: dict):
    schedulers = ["FF", "BFD", "DRF", "FAS"]

    col_w = 12  # column width

    def fmt(val):
        if isinstance(val, float):
            return f"{val:.4f}"
        return str(val)

    header = f"{'Metric':<25}" + "".join(f"{s:>{col_w}}" for s in schedulers)
    sep    = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    rows = [
        ("Jobs Accepted",        "jobs_accepted"),
        ("Jobs Rejected",        "jobs_rejected"),
        ("Avg RFI",              "avg_rfi"),
        ("Avg Utilization",      "avg_utilization"),
        ("Active Nodes",         "active_nodes"),
        ("Energy (kWh)",         "energy_kwh"),
        ("Nodes Freed (consol)", "nodes_freed"),
        ("Energy Savings %",     "energy_savings_pct"),
    ]

    for label, key in rows:
        row_str = f"{label:<25}"
        for s in schedulers:
            val = results[s].get(key, "N/A")
            row_str += f"{fmt(val):>{col_w}}"
        print(row_str)

    print(sep)


if __name__ == "__main__":
    main()
