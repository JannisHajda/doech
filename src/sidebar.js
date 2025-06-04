let latestMainFrameRequestId = null;

let mainFrameCount = 0;
let mainFrameEchCount = 0;
let mainFramePrivateDnsCount = 0;

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

const updateChart = () => {
  const echPercentage =
    mainFrameCount === 0
      ? 0
      : ((mainFrameEchCount / mainFrameCount) * 100).toFixed(2);
  const privateDnsPercentage =
    mainFrameCount === 0
      ? 0
      : ((mainFramePrivateDnsCount / mainFrameCount) * 100).toFixed(2);
  updateStats(
    privateDnsPercentage,
    100 - privateDnsPercentage,
    echPercentage,
    100 - echPercentage
  );
};

browser.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (!message.type.startsWith("doech")) return;

  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const type = message.type.replace("doech", "").toLowerCase();
  const { data } = message;
  const { tabId } = data;

  if (tabs.length === 0 || tabs[0].id !== tabId) return;

  if (type === "update") {
    if (message.data.type === "main_frame") {
      latestMainFrameRequestId = message.data.requestId;
      mainFrameCount++;
      if (message.data.usedEch) mainFrameEchCount++;
      if (message.data.usedPrivateDns) mainFramePrivateDnsCount++;
      updateChart();

      console.log("Main frame request received: ", latestMainFrameRequestId);

      // add a div for the main frame
      $("#mainFrames").append(
        `<div class="card h-16 w-full bg-slate-600 flex items-center p-2 rounded-md mb-5" id="mainFrame-${
          message.data.requestId
        }">
            <div
              class="rounded-lg h-12 w-12 bg-slate-300 flex items-center justify-center flex-shrink-0"
            >
              <span>${message.data.statusCode}</span>
            </div>
            <div class="url ml-2 flex-grow overflow-hidden">
              <p
                class="text-ellipsis overflow-hidden whitespace-nowrap w-full text-white"
                title="${message.data.url}"
              >
              ${message.data.url}
              </p>
            </div>
            <div class="stats flex items-center ml-2 flex-shrink-0 text-white">
              <span class="material-icons" title="DoH Usage">
                ${message.data.usedPrivateDns ? "check_circle" : "error"}
              </span>
              <span class="material-icons" title="ECH Usage">
${message.data.usedEch ? "check_circle" : "error"}
              </span>
              <span class="material-icons" title="Cached"> ${
                message.data.cached ? "check_circle" : "error"
              } </span>
            </div>`
      );
    } else
      console.log(
        "Subsequent request received! Latest main frame ID: ",
        latestMainFrameRequestId
      );

    //// entries is 2d array -> first element is main frame (first item in each sub-array)
    //// subsequent requests are in the same sub-array
    //// print the main frame and below it (ul) subsequent requests

    //const usedEchCount = entries.filter((entry) => entry.usedEch).length;
    //const usedPrivateDnsCount = entries.filter(
    //  (entry) => entry.usedPrivateDns
    //).length;
    //const totalCount = entries.length;
    //const echPercentage = ((usedEchCount / totalCount) * 100).toFixed(2);
    //const privateDnsPercentage = (
    //  (usedPrivateDnsCount / totalCount) *
    //  100
    //).toFixed(2);

    //updateStats(
    //  privateDnsPercentage,
    //  100 - privateDnsPercentage,
    //  echPercentage,
    //  100 - echPercentage
    //);

    //let data = [];
    //entries.forEach((entry) => {
    //  data.push([
    //    new Date(entry.timeStamp).toLocaleString(),
    //    entry.url,
    //    entry.ip,
    //    entry.statusCode,
    //    entry.usedEch,
    //    entry.usedPrivateDns,
    //  ]);
    //});

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
