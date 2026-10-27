"""
plot_results.py
---------------
Generates comparison charts from results/metrics.json.

Charts saved to results/:
  rfi_comparison.png  – Mean RFI across schedulers
  utilization.png     – Average utilisation across schedulers
  energy.png          – Energy consumption (kWh) across schedulers
  job_acceptance.png  – Jobs accepted vs rejected per scheduler
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")          # headless rendering
import matplotlib.pyplot as plt
import numpy as np

ROOT        = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, "results")
METRICS_PATH = os.path.join(RESULTS_DIR, "metrics.json")

SCHEDULERS = ["FF", "BFD", "DRF", "FAS"]
COLORS     = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]


# ------------------------------------------------------------------ #
# Load data
# ------------------------------------------------------------------ #

def load_metrics():
    if not os.path.exists(METRICS_PATH):
        sys.exit(f"ERROR: {METRICS_PATH} not found. Run main.py first.")
    with open(METRICS_PATH) as fh:
        return json.load(fh)


# ------------------------------------------------------------------ #
# Chart helpers
# ------------------------------------------------------------------ #

def _save(fig, filename):
    path = os.path.join(RESULTS_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def _bar_chart(values, title, ylabel, filename, color_list=None):
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = color_list or COLORS
    bars = ax.bar(SCHEDULERS, values, color=colors, edgecolor="white", linewidth=0.7)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(values) * 0.01,
            f"{val:.4g}",
            ha="center", va="bottom", fontsize=9,
        )

    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xlabel("Scheduler", fontsize=10)
    ax.set_ylim(0, max(values) * 1.15 if max(values) > 0 else 1)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, filename)


# ------------------------------------------------------------------ #
# Individual charts
# ------------------------------------------------------------------ #

def plot_rfi(metrics):
    values = [metrics[s]["avg_rfi"] for s in SCHEDULERS]
    _bar_chart(values, "Mean Idle Fragmentation Index (RFI)", "RFI", "rfi_comparison.png")


def plot_utilization(metrics):
    values = [metrics[s]["avg_utilization"] for s in SCHEDULERS]
    _bar_chart(values, "Average Node Utilization", "Utilization (fraction)", "utilization.png")


def plot_energy(metrics):
    values = [metrics[s]["energy_kwh"] for s in SCHEDULERS]
    _bar_chart(values, "Cluster Energy Consumption", "Energy (kWh)", "energy.png")


def plot_job_acceptance(metrics):
    accepted = [metrics[s]["jobs_accepted"] for s in SCHEDULERS]
    rejected = [metrics[s]["jobs_rejected"] for s in SCHEDULERS]

    x     = np.arange(len(SCHEDULERS))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4))
    bars_acc = ax.bar(x - width / 2, accepted, width, label="Accepted",
                      color="#55A868", edgecolor="white")
    bars_rej = ax.bar(x + width / 2, rejected, width, label="Rejected",
                      color="#C44E52", edgecolor="white")

    for bar in bars_acc:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)
    for bar in bars_rej:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)

    ax.set_title("Jobs Accepted vs Rejected per Scheduler",
                 fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel("Number of Jobs", fontsize=10)
    ax.set_xlabel("Scheduler", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(SCHEDULERS)
    ax.legend()
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "job_acceptance.png")


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def main():
    print("Loading metrics ...")
    metrics = load_metrics()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("Generating charts ...")
    plot_rfi(metrics)
    plot_utilization(metrics)
    plot_energy(metrics)
    plot_job_acceptance(metrics)

    print("All charts saved to results/")


if __name__ == "__main__":
    main()
