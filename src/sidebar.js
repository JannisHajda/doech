let totalMainFrames = 0;
let usedPrivateDns = 0;
let usedEch = 0;

const addMainFrame = (data) => {
  if (!$("#noData").hasClass("hidden")) {
    $("#noData").addClass("hidden");
    $("#mainFrames").removeClass("hidden");
  }

  totalMainFrames++;
  if (data.usedEch) usedEch++;
  if (data.usedPrivateDns) usedPrivateDns++;

  updateMainFramesChart(totalMainFrames, usedEch, usedPrivateDns);

  $("#mainFrames").prepend(
    `<div class="card h-16 w-full bg-slate-600 flex items-center p-2 rounded-md mb-5" id="mainFrame-${
      data.requestId
    }">
            <div
              class="rounded-lg h-12 w-12 bg-slate-300 flex items-center justify-center flex-shrink-0"
            >
              <span>${data.statusCode}</span>
            </div>
            <div class="url ml-2 flex-grow overflow-hidden">
              <p
                class="text-ellipsis overflow-hidden whitespace-nowrap w-full text-white"
                title="${data.url}"
              >
              ${data.url}
              </p>
            </div>
            <div class="stats flex items-center ml-2 flex-shrink-0 text-white">
              <span class="material-icons mr-1" title="DoH Usage">
                ${data.usedPrivateDns ? "check_circle" : "error"}
              </span>
              <span class="material-icons" title="ECH Usage">
                ${data.usedEch ? "check_circle" : "error"}
              </span>
            </div>`
  );
};

browser.runtime.onMessage.addListener(async (message) => {
  if (!message.type.startsWith("doech-")) return;

  let messageType = message.type.replace("doech-", "");

  const data = message.data;

  if (messageType === "mainFrame") addMainFrame(data);
});

const exportData = async () => {
  const res = await browser.runtime.sendMessage({ type: "doech-export" });

  const exportedData = res.data.map((req) => ({
    ...req,
    timeStamp: new Date(req.timeStamp).toISOString(),
  }));

  const blob = new Blob([JSON.stringify(exportedData, null, 2)], {
    type: "application/json",
  });

  const url = URL.createObjectURL(blob);

  browser.downloads.download({
    url,
    filename: "doech_data.json",
    saveAs: true,
  });
};

document.addEventListener("DOMContentLoaded", async () => {
  const res = await browser.runtime.sendMessage({
    type: "doech-init",
  });

  for (const data of res.data) addMainFrame(data);

  $("#export").on("click", () => exportData());
});
