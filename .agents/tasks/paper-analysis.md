# Paper Analysis: Idle Fragmentation-Aware Resource Scheduling for Hyperscale Energy-Efficient Cloud Data Centers

**Source:** Beena et al., IEEE Open Journal of Computer Society, Vol. 7, 2026. DOI: 10.1109/OJCS.2026.3699545

---

## Summary (Read This First)

The paper proposes a **Fragmentation-Aware Scheduling (FAS)** framework for Kubernetes-based cloud data centers. The core idea is to define a **Resource Fragmentation Index (RFI)** that measures the imbalance between leftover CPU and memory on each node, then use this metric as the primary signal for scheduling placement decisions and node consolidation. The result: 33.14% reduction in RFI, 24.9% improvement in average cluster utilization, and 36.9% energy savings — all while maintaining 100% job acceptance.

For Review 1 (base paper implementation), you need to implement: (1) a Python-based cluster simulator, (2) four schedulers (FF, BFD, DRF, FAS), (3) the greedy consolidation algorithm, (4) the linear power model, and (5) the evaluation pipeline using Alibaba Cluster Trace data.

---

## 1. Core Problem the Paper Addresses

**Idle CPU–memory fragmentation** in containerized cloud data centers. When containers are scheduled onto nodes, they leave behind asymmetric scraps of CPU and memory. For example, a node might have 40% free CPU but only 10% free memory — neither scrap is usable for any typical incoming workload because both resources must be satisfied simultaneously. This forces lightly-loaded nodes to stay powered on, wasting energy.

Traditional schedulers (First-Fit, Best-Fit, DRF) optimize for throughput or fairness but ignore the *geometry* of leftover resources. The key gap identified is the **absence of explicit CPU–memory fragmentation modeling** in Kubernetes-native schedulers.

---

## 2. Proposed Algorithms and Their Steps

### Algorithm 1: Fragmentation-Aware Scheduler (FAS)

**Input:** Job `j = (cpu_j, mem_j, is_short)`, set of machines `M`  
**Output:** Boolean — placement success

```
Pre-Sort: Sort jobs descending by (¬is_short, cpu_j + mem_j)
         → long, large jobs placed first

For each machine M_i in M:
    If M_i can fit job j (has enough CPU and memory):
        Compute post-placement free fractions:
            f_c = (M_i.cpu_left − cpu_j) / M_i.cpu_cap
            f_m = (M_i.mem_left − mem_j) / M_i.mem_cap

        Compute leftover_total = f_c + f_m

        Compute post-placement RFI:
            RFI_after = 1 − min(f_c, f_m) / (leftover_total + ε)
            where ε = 1e−12 (numerical stability)

        Determine weight w:
            if is_short: w = 2.0   (encourages tight packing)
            else:        w = 0.5   (preserves large resource blocks)

        Score = RFI_after + w × leftover_total

        Track machine with minimum Score

If best machine found:
    Place job on it → return True
Else:
    return False
```

**Key insight:** Short jobs get weight 2.0 so the score penalizes leftover space heavily — pack them tightly. Long jobs get weight 0.5 so the score is lenient about leaving space — preserve room for future large jobs.

---

### Algorithm 2: Greedy Consolidation for FAS

**Input:** Set of machines `M`, number of consolidation rounds `R`  
**Output:** `Freed_Count` — number of nodes powered off

```
Freed_Count = 0

For r = 1 to R:
    Sources = machines that have jobs, sorted by INCREASING utilization
    Machines_freed = 0

    For each source machine M_s in Sources:
        Jobs_move = all jobs currently on M_s
        tentative_placements = []
        all_moved = True

        For each job j in Jobs_move:
            Find first destination M_d (≠ M_s) that can fit j
            If M_d found:
                Tentatively place j on M_d
                Record (M_d, j) in tentative_placements
            Else:
                Rollback ALL tentative placements
                all_moved = False
                Break

        If all_moved:
            Clear M_s (source is now empty)
            Freed_Count += 1
            Machines_freed += 1

    If Machines_freed == 0:
        Break (no progress, stop early)

Return Freed_Count
```

**Key insight:** Consolidation is "all-or-nothing" per source machine. Either every job on a node can be migrated (and the node is freed), or nothing moves. This prevents partial migrations that worsen fragmentation.

---

### Kubernetes Deployment Extension (beyond pure simulation)

In the live Kubernetes portion, the scheduling scoring function is slightly extended to include a "combined DRF and fragmentation-based score":

```
placement_score = post_placement_dominant_share + residual_free_CPU_memory_balance + remaining_fill_space
```

Nodes below 35% CPU AND memory utilization are flagged as safe shutdown candidates after placement.

---

## 3. Key Metrics Used for Evaluation

| Metric | Definition | Formula / Notes |
|---|---|---|
| **Resource Fragmentation Index (RFI)** | Imbalance between leftover CPU and memory fractions | `RFI_k = 1 − min(f_c,k, f_m,k) / max(f_c,k, f_m,k)` |
| **Average Utilization (AU)** | Mean CPU+memory packing efficiency across active nodes | Higher is better |
| **Energy Consumption (EC)** | Power drawn by the cluster | Linear model: `P(u) = P_idle + (P_max − P_idle) × u` |
| **Energy Savings** | Reduction from powering off idle nodes | `(Energy_before − Energy_after) / Energy_before × 100%` |
| **Job Acceptance Rate (JAR)** | Fraction of jobs successfully placed | 100% maintained by FAS |
| **Nodes Freed** | Count of nodes powered off via consolidation | FAS freed 59 in simulation, 3 in Kubernetes test |
| **SLA Violation Rate** | Fraction of jobs missing resource guarantees | FAS: 0.026 (below 3% threshold) |
| **MigrationOps** | Total workload migrations during consolidation | FAS: 2,475 in simulation |

**RFI interpretation example (from paper):**  
40% free CPU, 10% free memory → `RFI = 1 − 0.10/0.40 = 0.75` (high imbalance; resources exist but are unusable).

---

## 4. Simulation / Experimental Setup

The paper uses a **two-stage** evaluation:

### Stage 1: Python-Based Simulation

- **Cluster size:** 1,310 machines (derived from Alibaba dataset)
- **Schedulers compared:** FF (First-Fit), BFD (Best-Fit Decreasing), DRF, and FAS
- **Job set:** 5,000 jobs (for baseline FF test); 4,877 successfully placed by FF/BFD/FAS; DRF rejected 417 due to fairness-driven placement
- **Workload generation:** Lognormal sampling of CPU and memory demands (preserving real-world variability); job durations drawn from data to classify short vs. long
- **Representative task size:** 75th percentile of batch workloads = 0.70 CPU cores, 0.0085 normalized memory
- **Power model:** `P(u) = P_idle + (P_max − P_idle) × u` (linear)
- **Consolidation:** Run after initial placement; multi-round greedy

**5-step experimental procedure:**
1. Dataset processing and workload extraction (machine configs, CPU/memory, job traces)
2. Workload generation and classification (lognormal sampling, short/long labeling)
3. Python simulator runs all four schedulers; post-placement RFI, utilization, energy computed
4. Kubernetes deployment of containerized workloads
5. Evaluation using metrics: AU, RFI, EC, JAR, Nodes Freed, SLA Violation Rate

### Stage 2: Live Kubernetes Cluster

- **Cluster:** 5-node Kubernetes cluster
- **Workloads deployed:** 120 containerized workloads (pods)
- **Result:** FAS consolidated all pods onto 3 nodes; 2 nodes idled and eligible for shutdown
- **Energy:** 9.77 kWh → 6.17 kWh (36.8% reduction)
- **Per-node power:** 813.99 W → 364.00 W (55.3% reduction after consolidation)

### Scalability Analysis

Evaluated across cluster sizes 10 to 100 nodes:
- Utilization increases from ~0.70 (10 nodes) to ~0.86 (100 nodes)
- SLA violation rate maintained below 3% at all sizes

---

## 5. Datasets and Benchmarks Used

### Alibaba Cluster Trace V2017
- **Source:** https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2017
- **Description:** Public large-scale production workload trace from Alibaba cloud infrastructure
- **Contents:** Real CPU/memory usage patterns, container lifecycle events, machine-level resource statistics from thousands of servers

**Trace files used (Table 2 in paper):**

| File | Contents |
|---|---|
| `machine_meta.csv` | Machine configurations (CPU capacity, memory capacity) |
| `machine_usage.csv` | Per-machine CPU and memory utilization over time |
| `container_meta.csv` | Container/job metadata (resource requests) |
| `batch_task.csv` | Batch task logs with CPU/memory demands and durations |

**Preprocessing steps:**
1. Merge server usage logs with machine capacity records → valid CPU/memory capacity per node
2. Convert CPU usage percentages to core units
3. Compute mean CPU and memory utilization per machine
4. Derive leftover resources = capacity − actual usage
5. Normalize leftover resources for fair comparison
6. Compute RFI from normalized idle resources
7. Extract 75th percentile CPU/memory from batch task logs → representative task size
8. Identify machines with low utilization + high RFI → consolidation candidates

**Key data points extracted:**
- 187,962 machine–usage entries
- 1,310 distinct machines
- 75th percentile task: 0.70 CPU cores, 0.0085 normalized memory
- Average tasks per machine (theoretical): 23.33

---

## 6. Mathematical Models and Formulations

### 6.1 Workload Model

Each job is a 3-tuple:
```
j_i = (c_i, m_i, d_i)
```
where:
- `c_i` = CPU demand (cores)
- `m_i` = memory demand (GiB or normalized fraction)
- `d_i` = execution duration

**Job classification:**
```
is_short(j_i) = 1  if d_i ≤ median(d)
                0  otherwise
```

### 6.2 Node Model

Each machine:
```
M_k = (C_k, Mem_k)
```
where `C_k` = total CPU capacity, `Mem_k` = total memory capacity.

**Post-scheduling residual fractions:**
```
f_c,k = (C_k − Σ c_i) / C_k       (for all i placed on M_k)
f_m,k = (Mem_k − Σ m_i) / Mem_k   (for all i placed on M_k)
```

### 6.3 Resource Fragmentation Index (RFI)

**Per-node RFI:**
```
RFI_k = 1 − min(f_c,k, f_m,k) / max(f_c,k, f_m,k)
```

Range: [0, 1]
- `RFI = 0`: perfectly balanced leftover resources (no fragmentation)
- `RFI → 1`: severe imbalance (one resource almost gone, other plentiful — highly fragmented)

**Note:** The paper also uses a cluster-wide RFI as the mean of per-node RFIs.

### 6.4 Placement Scoring Function

For placing job `j` on machine `M_k`:
```
S_k(j) = RFI_after_k + w_i × (f_c,k + f_m,k)
```
where:
- `RFI_after_k` = RFI computed after hypothetically placing `j` on `M_k`
- `f_c,k + f_m,k` = total fractional leftover after placement
- `w_i = 2.0` if `is_short(j)` else `0.5`

**Selection rule:** Choose `M_k` with **minimum** `S_k(j)`.

**Inside the score computation:**
```
f_c = (M_k.cpu_left − c_j) / M_k.cpu_cap
f_m = (M_k.mem_left − m_j) / M_k.mem_cap
leftover_total = f_c + f_m
RFI_after = 1 − min(f_c, f_m) / (leftover_total + ε)    [ε = 1e-12]
Score = RFI_after + w × leftover_total
```

### 6.5 Power / Energy Model

**Linear utilization-based power model:**
```
P(u) = P_idle + (P_max − P_idle) × u
```
where:
- `u` = node CPU utilization (fraction 0–1)
- `P_idle` = power at 0% utilization (idle power)
- `P_max` = power at 100% utilization

**Assumptions for simulation (typical server values to use):**
- `P_idle ≈ 200 W`, `P_max ≈ 400 W` (standard values in cloud computing literature)
- Powered-off nodes draw zero power

**Cluster energy consumption:**
```
E_total = Σ_k P(u_k) × T
```
where `T` is the time window.

**Energy savings:**
```
Savings% = (E_before − E_after) / E_before × 100
```

### 6.6 Feasibility Constraint

A job `j` can be placed on node `M_k` only if:
```
M_k.cpu_left ≥ c_j   AND   M_k.mem_left ≥ m_j
```

### 6.7 Kubernetes Target Utilization Constraint

In the live Kubernetes stage, the minimum number of active nodes is:
```
N_min = ceil( (Σ cpu_demand / u_max) / cpu_per_node )
     where u_max = 0.92
```

---

## 7. Baseline Schedulers to Implement (for comparison)

| Scheduler | Logic |
|---|---|
| **First-Fit (FF)** | Place job on first machine that has enough CPU and memory |
| **Best-Fit Decreasing (BFD)** | Sort jobs descending by size; place on machine with tightest post-placement fit (least leftover) |
| **DRF (Dominant Resource Fairness)** | Select node that minimizes the resulting dominant share (max of CPU fraction, memory fraction used) |
| **FAS (proposed)** | Algorithm 1 above; pre-sort by (long-first, large-first); score = RFI_after + w × leftover; post-placement consolidation via Algorithm 2 |

---

## 8. Key Results to Reproduce

| Metric | FF | BFD | DRF | FAS |
|---|---|---|---|---|
| Jobs accepted | 4,877 | 4,877 | 4,460 (rejected 417) | 4,877 |
| RFI (pre-consolidation) | 0.7756 | ~high | 0.8241 (lowest) | 0.9646 |
| RFI (end-to-end, Kubernetes) | 0.175 (baseline) | — | — | 0.117 (−33.14%) |
| Average utilization | 0.209 | — | — | 0.261 (+24.9%) |
| Energy (Kubernetes) | 9.77 kWh | — | — | 6.17 kWh (−36.8%) |
| Nodes freed | 0 | — | — | 59 (simulation); 3 (Kubernetes) |
| SLA violation rate | 0.031 | — | — | 0.026 |
| Migration ops | 0 | 0 | 0 | 2,475 |

**Baseline energy waste (simulation):** 1,310 active machines vs. 684 needed → 626 unnecessary → 1.126 MWh wasted.

---

## 9. Implementation Recommendations for Review 1

### What to build (minimum viable implementation)

1. **Data loader:** Parse Alibaba Cluster Trace V2017 CSV files (`machine_meta.csv`, `machine_usage.csv`, `batch_task.csv`). Merge, normalize, compute per-node idle CPU/memory.

2. **Node class:** Holds `cpu_cap`, `mem_cap`, `cpu_left`, `mem_left`; method `can_fit(job)` and `place(job)`.

3. **Job class:** Holds `cpu`, `mem`, `duration`, `is_short` (bool).

4. **RFI calculator:** `compute_rfi(f_c, f_m)` → `1 - min(f_c, f_m) / max(f_c, f_m)`.

5. **Four schedulers:** FF, BFD, DRF, FAS — each takes a job list and node list, returns placement assignments.

6. **Greedy Consolidation (Algorithm 2):** Applied after FAS placement; returns freed node count.

7. **Power model:** `P(u) = P_idle + (P_max - P_idle) * u`; compute total cluster energy.

8. **Evaluation harness:** Run all four schedulers on the same workload, collect metrics, print comparison table.

### Language and libraries recommended

- **Python 3** (the paper's own implementation uses Python + Kubernetes Python client API)
- `pandas` for CSV parsing
- `numpy` for lognormal sampling and statistics
- `matplotlib` for result plots (Figures 4–8)
- No ML libraries needed for Review 1

### Dataset note

Download the Alibaba Cluster Trace V2017 from:  
https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2017

If the full dataset is too large, the paper uses the 75th percentile representative task (0.70 CPU cores, 0.0085 normalized memory) — you can use this fixed task size to generate a synthetic but representative workload and still reproduce the core results.

### What NOT to build for Review 1

- Actual Kubernetes deployment (that's the live validation stage — optional for Review 1)
- Docker container management
- Non-linear thermal models (explicitly listed as future work)
- Migration cost estimation (also future work)

---

## 10. Limitations Acknowledged by the Paper

- Migration overhead not modeled (assumed negligible)
- Linear power model only — does not capture non-linear thermal behavior
- Live Kubernetes validation on only 5 nodes (small scale)
- No workload uncertainty or prediction modeling

These are natural novelty hooks for Review 2.
