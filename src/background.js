const tabData = {};

browser.webRequest.onHeadersReceived.addListener(
  async (details) => {
    const {
      requestId,
      tabId,
      url,
      timeStamp,
      ip,
      statusCode,
      fromCache,
      type,
    } = details;

    if (fromCache) return;

    const securityInfo = await browser.webRequest.getSecurityInfo(
      requestId,
      {}
    );

    const { usedEch, usedPrivateDns } = securityInfo;

    if (usedEch === undefined || usedPrivateDns === undefined) return;

    if (!tabData[tabId]) tabData[tabId] = [];

    const data = {
      tabId,
      timeStamp,
      url,
      ip,
      statusCode,
      usedEch,
      usedPrivateDns,
    };

    // group by main frame and subsequent requests
    if (type == "main_frame") tabData[tabId].push([data]);
    else tabData[tabId][tabData[tabId].length - 1].push(data);

    browser.runtime.sendMessage({
      type: "doechUpdate",
      data: {
        tabId,
        entries: tabData[tabId],
      },
    });
  },
  {
    urls: ["<all_urls>"],
  },
  ["blocking"]
);

browser.tabs.onRemoved.addListener((tabId) => {
  if (tabData[tabId]) delete tabData[tabId];
});

browser.tabs.onActivated.addListener((activeInfo) => {
  const { tabId } = activeInfo;
  if (!tabData[tabId]) tabData[tabId] = [];

  const entries = tabData[tabId];

  browser.runtime.sendMessage({
    type: "doechUpdate",
    data: {
      tabId,
      entries,
    },
  });
});

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message.type.startsWith("doech")) return;

  const type = message.type.replace("doech", "").toLowerCase();
  const { data } = message;

  if (type === "requestupdate") {
    const { tabId } = data;
    const entries = tabData[tabId] || [];

    browser.runtime.sendMessage({
      type: "doechUpdate",
      data: {
        tabId,
        entries,
      },
    });
  }
});
