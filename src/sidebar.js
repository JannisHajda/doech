let detailsEnabled = false;

$(() => {
  $(".card").on("click", () => {
    showDetails();
  });

  $("#closeDetails").on("click", () => {
    closeDetails();
  });
});

const showDetails = () => {
  $("#mainHeader").hide();
  $("#detailsHeader").show();
  detailsEnabled = true;
};

const closeDetails = () => {
  $("#mainHeader").show();
  $("#detailsHeader").hide();
  detailsEnabled = false;
};

browser.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (!message.type.startsWith("doech")) return;

  console.log(
    "Received message:",
    message,
    " details enabled:",
    detailsEnabled
  );

  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const type = message.type.replace("doech", "").toLowerCase();
  const { data } = message;
  const { tabId, entries } = data;

  if (tabs.length === 0 || tabs[0].id !== tabId) return;

  if (type === "update") {
    if (entries.length === 0) return;

    // entries is 2d array -> first element is main frame (first item in each sub-array)
    // subsequent requests are in the same sub-array
    // print the main frame and below it (ul) subsequent requests

    const usedEchCount = entries.filter((entry) => entry.usedEch).length;
    const usedPrivateDnsCount = entries.filter(
      (entry) => entry.usedPrivateDns
    ).length;
    const totalCount = entries.length;
    const echPercentage = ((usedEchCount / totalCount) * 100).toFixed(2);
    const privateDnsPercentage = (
      (usedPrivateDnsCount / totalCount) *
      100
    ).toFixed(2);

    updateStats(
      privateDnsPercentage,
      100 - privateDnsPercentage,
      echPercentage,
      100 - echPercentage
    );

    let data = [];
    entries.forEach((entry) => {
      data.push([
        new Date(entry.timeStamp).toLocaleString(),
        entry.url,
        entry.ip,
        entry.statusCode,
        entry.usedEch,
        entry.usedPrivateDns,
      ]);
    });

    // initDataTable(data);
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

  if (tab) {
    browser.runtime.sendMessage({
      type: "doechRequestUpdate",
      data: {
        tabId: tab.id,
      },
    });
  }
});
