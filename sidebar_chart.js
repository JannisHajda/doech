let myChart;

const data = {
  labels: ["Secure DNS", "Unsecure DNS", "ECH Enabled", "ECH Disabled"],
  datasets: [
    {
      backgroundColor: ["#AAA", "#777"],
      data: [21, 79],
    },
    {
      backgroundColor: ["hsl(0, 100%, 60%)", "hsl(0, 100%, 35%)"],
      data: [33, 67],
    },
  ],
};

const updateStats = (secure = 0, unsecure = 0, enabled = 0, disabled = 0) => {
  if (myChart) {
    if (myChart.data.datasets.length >= 2) {
      myChart.data.datasets[0].data = [secure, unsecure];
      myChart.data.datasets[1].data = [enabled, disabled];
      myChart.update();
    } else {
      console.warn("updateStats: Unexpected dataset structure");
    }
  }
};

const config = {
  type: "pie",
  data: data,
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          generateLabels: function (chart) {
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
        onClick: function (e, legendItem, legend) {
          const ci = legend.chart;
          const datasetIndex = legendItem.datasetIndex;
          const meta = ci.getDatasetMeta(datasetIndex);

          meta.hidden = ci.isDatasetVisible(datasetIndex);
          ci.update();
        },
      },
      tooltip: {
        callbacks: {
          title: function (context) {
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

window.addEventListener("DOMContentLoaded", () => {
  const ctx = document.getElementById("myChart");
  myChart = new Chart(ctx, config);

  initDataTable([]);
});

const initDataTable = (data) => {
  const tableElement = document.querySelector("#example");

  if ($.fn.DataTable.isDataTable(tableElement)) {
    $(tableElement).DataTable().clear().destroy();
  }

  new DataTable(tableElement, {
    columns: [
      { title: "Time" },
      { title: "URL" },
      { title: "IP" },
      { title: "Status Code." },
      { title: "Used ECH" },
      { title: "Used Private DNS" },
    ],
    data: data,
    autoWidth: false,
    columnDefs: [
      {
        targets: 1, // URL column
        width: "10%",
      },
    ],
  });
};

window.addEventListener("resize", () => {
  if (myChart) {
    myChart.resize();
  }
});
