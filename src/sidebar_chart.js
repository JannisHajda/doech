let mainFramesChart;

const data = {
  labels: ["Secure DNS", "Unsecure DNS", "ECH Enabled", "ECH Disabled"],
  datasets: [
    {
      backgroundColor: ["#dab2ff", "#3c0366"],

      data: [0, 100],
    },
    {
      backgroundColor: ["#ffa1ad", "#8b0836"],
      data: [0, 100],
    },
  ],
};

const config = {
  type: "pie",
  data: data,
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          generateLabels: (chart) => {
            const original =
              Chart.overrides.pie.plugins.legend.labels.generateLabels;
            const labelsOriginal = original.call(this, chart);

            let datasetColors = chart.data.datasets.map(
              (e) => e.backgroundColor
            );

            datasetColors = datasetColors.flat();

            labelsOriginal.forEach((label) => {
              label.datasetIndex = Math.floor(label.index / 2);
              label.hidden = !chart.isDatasetVisible(label.datasetIndex);
              label.fillStyle = datasetColors[label.index];
            });

            return labelsOriginal;
          },
        },
        onClick: (e, legendItem, legend) => {
          const ci = legend.chart;
          const datasetIndex = legendItem.datasetIndex;
          const meta = ci.getDatasetMeta(datasetIndex);

          meta.hidden = ci.isDatasetVisible(datasetIndex);
          ci.update();
        },
      },
      tooltip: {
        callbacks: {
          title: (context) => {
            const labelIndex =
              context[0].datasetIndex * 2 + context[0].dataIndex;
            return (
              context[0].chart.data.labels[labelIndex] +
              ": " +
              context[0].formattedValue
            );
          },
        },
      },
    },
  },
};

const updateMainFramesChart = (total = 0, usedEch, usedPrivateDns) => {
  if (!mainFramesChart) return;

  const usedEchPercentage = Math.round((usedEch / total) * 100);

  const usedPrivateDnsPercentage = Math.round((usedPrivateDns / total) * 100);

  if (mainFramesChart.data.datasets.length >= 2) {
    mainFramesChart.data.datasets[0].data = [
      usedPrivateDnsPercentage,
      100 - usedPrivateDnsPercentage,
    ];
    mainFramesChart.data.datasets[1].data = [
      usedEchPercentage,
      100 - usedEchPercentage,
    ];
    mainFramesChart.update();
  }
};

window.addEventListener("DOMContentLoaded", () => {
  const ctx = document.getElementById("mainFramesChart");
  mainFramesChart = new Chart(ctx, config);
});

window.addEventListener("resize", () => {
  if (mainFramesChart) mainFramesChart.resize();
});
