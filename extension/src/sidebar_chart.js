let chart;

const chartLabels = [
  "Secure DNS",
  "Unsecure DNS",
  "ECH Enabled",
  "ECH Disabled",
];

const chartData = {
  labels: chartLabels,
  datasets: [
    {
      label: "DNS",
      backgroundColor: ["#dab2ff", "#3c0366"],
      data: [0, 100],
    },
    {
      label: "ECH",
      backgroundColor: ["#ffa1ad", "#8b0836"],
      data: [0, 100],
    },
  ],
};

const chartConfig = {
  type: "pie",
  data: chartData,
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          generateLabels(chart) {
            const originalGenerate =
              Chart.overrides.pie.plugins.legend.labels.generateLabels;
            const labels = originalGenerate.call(this, chart);

            const flatColors = chart.data.datasets.flatMap(
              (ds) => ds.backgroundColor
            );

            labels.forEach((label) => {
              label.datasetIndex = Math.floor(label.index / 2);
              label.hidden = !chart.isDatasetVisible(label.datasetIndex);
              label.fillStyle = flatColors[label.index];
            });

            return labels;
          },
        },
        onClick(e, legendItem, legend) {
          const chart = legend.chart;
          const datasetIndex = legendItem.datasetIndex;
          const meta = chart.getDatasetMeta(datasetIndex);

          meta.hidden = chart.isDatasetVisible(datasetIndex);
          chart.update();
        },
      },
      tooltip: {
        callbacks: {
          title(context) {
            const labelIndex =
              context[0].datasetIndex * 2 + context[0].dataIndex;
            const label = context[0].chart.data.labels[labelIndex];
            return `${label}: ${context[0].formattedValue}`;
          },
        },
      },
    },
  },
};

const setChartData = (total = 100, usedEch = 0, usedPrivateDns = 0) => {
  if (!chart) return;

  const toPercent = (value) => Math.round((value / total) * 100);

  chart.data.datasets[0].data = [
    toPercent(usedPrivateDns),
    100 - toPercent(usedPrivateDns),
  ];

  chart.data.datasets[1].data = [toPercent(usedEch), 100 - toPercent(usedEch)];

  chart.update();
};

window.addEventListener("DOMContentLoaded", () => {
  const ctx = document.getElementById("chart");
  if (ctx) {
    chart = new Chart(ctx, chartConfig);
  }
});

window.addEventListener("resize", () => {
  chart?.resize();
});
