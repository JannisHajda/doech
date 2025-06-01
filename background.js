const tabData = {};

browser.webRequest.onHeadersReceived.addListener(
  async (details) => {
    const { requestId, tabId, url, timeStamp, ip, statusCode, fromCache } =
      details;

    if (fromCache) return;

    const securityInfo = await browser.webRequest.getSecurityInfo(
      requestId,
      {}
    );

    const { usedEch, usedPrivateDns } = securityInfo;

    if (usedEch === undefined || usedPrivateDns === undefined) return;

    const data = {
      tabId,
      timeStamp,
      url,
      ip,
      statusCode,
      usedEch,
      usedPrivateDns,
    };

    if (!tabData[tabId]) tabData[tabId] = [];

    tabData[tabId].push(data);

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
