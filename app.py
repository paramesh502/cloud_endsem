import copy
import json
import os
import sys

from flask import Flask, render_template, request, jsonify

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from src.loader import load_data
from src.schedulers import schedule_ff, schedule_bfd, schedule_drf, schedule_fas
from src.evaluate import compute_metrics

app = Flask(__name__)

DATA_DIR = os.path.join(ROOT, "data", "alibaba-trace-2017")

_cache = {"nodes": None, "jobs": None, "n_jobs": None}


def get_data(n_jobs):
    if _cache["nodes"] is None or _cache["n_jobs"] != n_jobs:
        nodes, jobs = load_data(DATA_DIR, n_jobs=n_jobs)
        _cache["nodes"] = nodes
        _cache["jobs"] = jobs
        _cache["n_jobs"] = n_jobs
    return _cache["nodes"], _cache["jobs"]


def fresh_nodes(nodes):
    return copy.deepcopy(nodes)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run", methods=["POST"])
def api_run():
    try:
        body = request.get_json(silent=True) or {}
        n_jobs = int(body.get("n_jobs", 5000))

        nodes, jobs = get_data(n_jobs)
        results = {}

        # First Fit
        ff_nodes = fresh_nodes(nodes)
        _, _, ff_acc, ff_rej = schedule_ff(jobs, ff_nodes)
        m = compute_metrics(ff_nodes, ff_acc, ff_rej)
        m["nodes_freed"] = "N/A"
        m["energy_savings_pct"] = "N/A"
        results["FF"] = m

        # Best Fit Decreasing
        bfd_nodes = fresh_nodes(nodes)
        _, _, bfd_acc, bfd_rej = schedule_bfd(jobs, bfd_nodes)
        m = compute_metrics(bfd_nodes, bfd_acc, bfd_rej)
        m["nodes_freed"] = "N/A"
        m["energy_savings_pct"] = "N/A"
        results["BFD"] = m

        # Dominant Resource Fairness
        drf_nodes = fresh_nodes(nodes)
        _, _, drf_acc, drf_rej = schedule_drf(jobs, drf_nodes)
        m = compute_metrics(drf_nodes, drf_acc, drf_rej)
        m["nodes_freed"] = "N/A"
        m["energy_savings_pct"] = "N/A"
        results["DRF"] = m

        # Fragmentation-Aware Scheduling
        fas_nodes = fresh_nodes(nodes)
        pl, active, acc, rej, freed, energy_before, energy_after = schedule_fas(jobs, fas_nodes)
        m = compute_metrics(fas_nodes, acc, rej)
        m["nodes_freed"] = freed
        m["energy_savings_pct"] = (
            round((energy_before - energy_after) / energy_before * 100, 2)
            if energy_before > 0
            else 0.0
        )
        results["FAS"] = m

        return jsonify({"schedulers": ["FF", "BFD", "DRF", "FAS"], "metrics": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
