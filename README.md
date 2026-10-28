# Idle Fragmentation-Aware Resource Scheduling for Hyperscale Energy-Efficient Cloud Data Centers

Implementation of the base paper:
> Beena et al., "Idle Fragmentation-Aware Resource Scheduling for Hyperscale Energy-Efficient Cloud Data Centers", IEEE Open Journal of Computer Society, Vol. 7, 2026. DOI: 10.1109/OJCS.2026.3699545

---

## Overview

This project simulates a **Fragmentation-Aware Scheduler (FAS)** for cloud data centers. The core idea is to minimize CPU–memory fragmentation on servers — the imbalance between leftover CPU and memory that makes resources unusable — using a **Resource Fragmentation Index (RFI)**.

Four schedulers are implemented and compared:
- **First-Fit (FF)** — place job on the first node that fits
- **Best-Fit Decreasing (BFD)** — sort jobs by size, pack tightest fit
- **DRF** — minimize dominant resource share per node
- **FAS** — minimize RFI per placement + greedy consolidation to power off idle nodes

---

## Project Structure

```
cloud_endsem/
├── src/
│   ├── models.py         # Node and Job classes
│   ├── loader.py         # Alibaba trace data parser
│   ├── schedulers.py     # FF, BFD, DRF, FAS algorithms
│   ├── consolidation.py  # Greedy all-or-nothing consolidation (Algorithm 2)
│   ├── power.py          # Linear power model: P(u) = P_idle + (P_max - P_idle) * u
│   └── evaluate.py       # RFI, utilization, energy metrics
├── main.py               # Runs all 4 schedulers and prints comparison table
├── plot_results.py       # Generates matplotlib bar charts
├── requirements.txt
└── README.md
```

---

## Dataset

Uses the **Alibaba Cluster Trace V2017** — a public production workload trace from Alibaba's cloud infrastructure (~1,313 machines, 12-hour period).

Download it yourself:
```bash
mkdir -p data
curl -L -o data/alibaba-trace-2017.tar.gz \
  http://aliopentrace.oss-cn-beijing.aliyuncs.com/v2017Traces/alibaba-trace-2017.tar.gz
tar -xzf data/alibaba-trace-2017.tar.gz -C data/
```

Files used:
- `data/alibaba-trace-2017/server_event.csv` — machine CPU/memory capacities
- `data/alibaba-trace-2017/server_usage.csv` — per-machine utilization over time
- `data/alibaba-trace-2017/batch_task.csv` — batch job resource demands and durations

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Run

```bash
# Run simulation and print comparison table
python main.py

# Generate bar charts (saved to results/)
python plot_results.py
```

---

## Key Algorithms

### Resource Fragmentation Index (RFI)
```
RFI = 1 - min(f_cpu, f_mem) / max(f_cpu, f_mem)
```
- `f_cpu`, `f_mem` = fractional leftover CPU and memory on a node
- RFI = 0 → perfectly balanced leftovers (no fragmentation)
- RFI → 1 → severe imbalance (resources exist but are unusable together)

### FAS Placement Score
```
score = RFI_after + w * (f_cpu + f_mem)
```
- `w = 2.0` for short jobs (pack tightly), `w = 0.5` for long jobs (preserve space)
- Node with **minimum score** is selected

### Greedy Consolidation
All-or-nothing migration: if every job on a low-utilization node can be moved elsewhere, the node is powered off. Runs for up to 10 rounds.

### Power Model
```
P(u) = P_idle + (P_max - P_idle) * u
```
- `P_idle = 200 W`, `P_max = 400 W`
- Powered-off nodes draw 0 W

---

## Sample Results

| Metric | FF | BFD | DRF | FAS |
|---|---|---|---|---|
| Jobs Accepted | 5000 | 5000 | 5000 | 5000 |
| Avg RFI | 0.987 | 0.984 | 0.219 | 0.982 |
| Avg Utilization | 0.879 | 0.850 | 0.392 | 0.862 |
| Active Nodes | 104 | 132 | 394 | 112 |
| Energy (kWh) | 36.67 | 45.64 | 103.6 | 38.73 |
| Nodes Freed | — | — | — | 321 |
| Energy Savings | — | — | — | 65.83% |

---

## Review 2 (Planned)

Novelty additions planned for Review 2:
- Non-linear thermal power model
- Migration cost-aware consolidation
- Predictive / ML-based consolidation trigger
