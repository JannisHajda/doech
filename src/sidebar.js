let showAll = false;

let primaryRequests = [];
let subRequests = [];

let primaryRequestCount = 0;
let primaryRequestCountEch = 0;
let primaryRequestCountPrivateDns = 0;

let subRequestCount = 0;
let subRequestCountEch = 0;
let subRequestCountPrivateDns = 0;

const updateChart = () => {
  const total = primaryRequestCount + (showAll ? subRequestCount : 0);
  const totalEch = primaryRequestCountEch + (showAll ? subRequestCountEch : 0);
  const totalDns =
    primaryRequestCountPrivateDns + (showAll ? subRequestCountPrivateDns : 0);

  setChartData(total || 100, totalEch, totalDns);
};

const updateNoRequestsMessage = () => {
  const noPrimary = primaryRequests.length === 0;
  const noSub = subRequests.length === 0;

  if (showAll && noPrimary && noSub) {
    $("#noRequests")
      .removeClass("hidden")
      .find("h2")
      .text("No requests found.");
  } else if (!showAll && noPrimary) {
    $("#noRequests")
      .removeClass("hidden")
      .find("h2")
      .text("No primary requests found.");
  } else {
    $("#noRequests").addClass("hidden");
  }
};

const addRequestCard = (data, isPrimary) => {
  const requestType = isPrimary ? "primaryRequest" : "subRequest";
  const typeClass = isPrimary ? "h-16" : "h-12 text-sm";
  const bgColor = isPrimary ? "bg-slate-900" : "bg-slate-700";
  const hiddenClass = isPrimary || showAll ? "" : "hidden";

  return `
    <div class="${hiddenClass} request" id="${requestType}-${data.requestId}">
      <div class="flex ${typeClass} w-full ${bgColor} items-center p-2 rounded-md mb-5">
        <div class="rounded-lg ${
          isPrimary ? "h-12 w-12" : "h-8 w-8"
        } bg-slate-300 flex items-center justify-center flex-shrink-0">
          <span>${data.statusCode}</span>
        </div>
        <div class="url ml-2 flex-grow overflow-hidden">
          <p class="text-ellipsis overflow-hidden whitespace-nowrap w-full text-white" title="${
            data.url
          }">
            ${data.url}
          </p>
        </div>
        <div class="stats flex items-center ml-2 flex-shrink-0 text-white">
          <span class="material-icons mr-1" title="DoH Usage">${
            data.usedPrivateDns ? "check_circle" : "error"
          }</span>
          <span class="material-icons" title="ECH Usage">${
            data.usedEch ? "check_circle" : "error"
          }</span>
        </div>
      </div>
    </div>`;
};

const addPrimaryRequest = (data) => {
  primaryRequests.push(data);
  primaryRequestCount++;
  if (data.usedEch) primaryRequestCountEch++;
  if (data.usedPrivateDns) primaryRequestCountPrivateDns++;

  $("#requests").prepend(addRequestCard(data, true));
  updateChart();
  updateNoRequestsMessage();
};

const addSubRequest = (data) => {
  subRequests.push(data);
  subRequestCount++;
  if (data.usedEch) subRequestCountEch++;
  if (data.usedPrivateDns) subRequestCountPrivateDns++;

  $("#requests").prepend(addRequestCard(data, false));
  updateChart();
  updateNoRequestsMessage();
};

browser.runtime.onMessage.addListener(async (message) => {
  if (message.type !== "doech-update") return;

  const request = message.data;
  request.type === "primaryRequest"
    ? addPrimaryRequest(request)
    : addSubRequest(request);
});

const exportData = async () => {
  const exportedData = requests.map((req) => ({
    ...req,
    timeStamp: new Date(req.timeStamp).toISOString(),
  }));

  if (!exportedData.length) {
    alert("No data to export.");
    return;
  }

  const blob = new Blob([JSON.stringify(exportedData, null, 2)], {
    type: "application/json",
  });

  const url = URL.createObjectURL(blob);

  await browser.downloads.download({
    url,
    filename: "doech_data.json",
    saveAs: true,
  });
};

document.addEventListener("DOMContentLoaded", async () => {
  const res = await browser.runtime.sendMessage({ type: "doech-init" });

  res.data.forEach((data) =>
    data.type === "primaryRequest"
      ? addPrimaryRequest(data)
      : addSubRequest(data)
  );

  $("#export").on("click", exportData);

  $("#showAllRequests").on("click", () => {
    showAll = true;

    $("#showPrimaryRequests")
      .removeClass("bg-slate-700")
      .addClass("bg-slate-900");
    $("#showAllRequests").removeClass("bg-slate-900").addClass("bg-slate-700");

    $('#requests [id^="subRequest-"]').removeClass("hidden");

    updateChart();
    updateNoRequestsMessage();
  });

  $("#showPrimaryRequests").on("click", () => {
    showAll = false;

    $("#showAllRequests").removeClass("bg-slate-700").addClass("bg-slate-900");
    $("#showPrimaryRequests")
      .removeClass("bg-slate-900")
      .addClass("bg-slate-700");

    $('#requests [id^="subRequest-"]').addClass("hidden");

    updateChart();
    updateNoRequestsMessage();
  });
});
