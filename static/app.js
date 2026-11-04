document.addEventListener("DOMContentLoaded", () => {
  const runBtn     = document.getElementById("run-btn");
  const nJobsSelect = document.getElementById("n-jobs");
  const loading    = document.getElementById("loading");
  const errorMsg   = document.getElementById("error-msg");
  const results    = document.getElementById("results");

  let chartInstances = {};

  const COLORS = {
    FF:  "#8e8e93",
    BFD: "#aeaeb2",
    DRF: "#c7c7cc",
    FAS: "#0071e3",
  };

  function fmt(val) {
    if (val === "N/A") return "N/A";
    if (typeof val === "number") return val.toLocaleString(undefined, { maximumFractionDigits: 4 });
    return val;
  }

  function populateCard(id, name, metrics) {
    const card = document.getElementById(id);
    const h3   = card.querySelector("h3");
    // Preserve badge HTML for FAS
    if (id !== "card-FAS") {
      h3.textContent = name;
    }

    const body = card.querySelector(".metrics-body");
    body.innerHTML = "";

    const rows = [
      ["Jobs Accepted",   metrics.jobs_accepted],
      ["Jobs Rejected",   metrics.jobs_rejected],
      ["Active Nodes",    metrics.active_nodes],
      ["Avg RFI",         metrics.avg_rfi],
      ["Avg Utilization", metrics.avg_utilization],
      ["Energy (kWh)",    metrics.energy_kwh],
    ];

    if (id === "card-FAS") {
      rows.push(["Nodes Freed",      metrics.nodes_freed]);
      rows.push(["Energy Savings %", metrics.energy_savings_pct]);
    }

    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "metric-row";
      row.innerHTML = `<span class="metric-label">${label}</span>
                       <span class="metric-value">${fmt(value)}</span>`;
      body.appendChild(row);
    });
  }

  function renderCharts(data) {
    const schedulers = ["FF", "BFD", "DRF", "FAS"];
    const bgColors   = schedulers.map(s => COLORS[s]);

    // Destroy existing chart instances
    Object.values(chartInstances).forEach(c => c.destroy());
    chartInstances = {};

    const chartDefaults = {
      plugins: { legend: { display: false } },
      responsive: true,
      animation: { duration: 800, easing: "easeOutQuart" },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#6e6e73" },
        },
        y: {
          grid: { color: "#f5f5f7" },
          ticks: { color: "#6e6e73" },
        },
      },
    };

    // RFI
    chartInstances["rfi"] = new Chart(document.getElementById("chart-rfi"), {
      type: "bar",
      data: {
        labels: schedulers,
        datasets: [{
          label: "Avg RFI",
          data: schedulers.map(s => data[s].avg_rfi),
          backgroundColor: bgColors,
          borderRadius: 8,
        }],
      },
      options: { ...chartDefaults },
    });

    // Utilization
    chartInstances["util"] = new Chart(document.getElementById("chart-util"), {
      type: "bar",
      data: {
        labels: schedulers,
        datasets: [{
          label: "Avg Utilization",
          data: schedulers.map(s => data[s].avg_utilization),
          backgroundColor: bgColors,
          borderRadius: 8,
        }],
      },
      options: { ...chartDefaults },
    });

    // Energy
    chartInstances["energy"] = new Chart(document.getElementById("chart-energy"), {
      type: "bar",
      data: {
        labels: schedulers,
        datasets: [{
          label: "Energy (kWh)",
          data: schedulers.map(s => data[s].energy_kwh),
          backgroundColor: bgColors,
          borderRadius: 8,
        }],
      },
      options: { ...chartDefaults },
    });

    // Jobs Accepted vs Rejected
    chartInstances["jobs"] = new Chart(document.getElementById("chart-jobs"), {
      type: "bar",
      data: {
        labels: schedulers,
        datasets: [
          {
            label: "Accepted",
            data: schedulers.map(s => data[s].jobs_accepted),
            backgroundColor: bgColors,
            borderRadius: 8,
          },
          {
            label: "Rejected",
            data: schedulers.map(s => data[s].jobs_rejected),
            backgroundColor: "#ff3b30",
            borderRadius: 8,
          },
        ],
      },
      options: {
        ...chartDefaults,
        plugins: {
          legend: { display: true },
        },
      },
    });
  }

  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    loading.style.display = "block";
    results.style.display = "none";
    errorMsg.style.display = "none";

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n_jobs: parseInt(nJobsSelect.value) }),
      });

      const json = await response.json();

      if (!response.ok || json.error) {
        throw new Error(json.error || `HTTP ${response.status}`);
      }

      loading.style.display = "none";

      const metrics = json.metrics;
      populateCard("card-FF",  "FF",  metrics.FF);
      populateCard("card-BFD", "BFD", metrics.BFD);
      populateCard("card-DRF", "DRF", metrics.DRF);
      populateCard("card-FAS", "FAS", metrics.FAS);

      renderCharts(metrics);
      results.style.display = "block";

    } catch (err) {
      loading.style.display = "none";
      errorMsg.textContent  = `Error: ${err.message}`;
      errorMsg.style.display = "block";
    } finally {
      runBtn.disabled = false;
    }
  });
});
