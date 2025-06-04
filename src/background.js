const tabData = {};

const handleHeadersReceived = async (tabId, details) => {
  const { requestId, url, timeStamp, ip, statusCode, fromCache, type } =
    details;

  const securityInfo = await browser.webRequest.getSecurityInfo(requestId, {});

  const { usedEch, usedPrivateDns } = securityInfo;

  if (usedEch === undefined || usedPrivateDns === undefined) return;

  if (!tabData[tabId]) tabData[tabId] = [];

  const data = {
    tabId,
    type,
    requestId,
    timeStamp,
    url,
    ip,
    statusCode,
    usedEch,
    usedPrivateDns,
    fromCache,
  };

  // group by main frame and subsequent requests
  if (type == "main_frame") tabData[tabId].push([data]);
  else tabData[tabId][tabData[tabId].length - 1].push(data);

  browser.runtime.sendMessage({
    type: "doechUpdate",
    data,
  });
};

browser.tabs.onRemoved.addListener((tabId) => {
  if (tabData[tabId]) delete tabData[tabId];
});

browser.tabs.onActivated.addListener((activeInfo) => {
  const { tabId } = activeInfo;
  if (!tabData[tabId]) tabData[tabId] = [];

  const entries = tabData[tabId];

  browser.runtime.sendMessage({
    type: "doechTabActivated",
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

const headersListener = {};

function createHeadersListener(tabId) {
  return function (details) {
    return handleHeadersReceived(tabId, details);
  };
}

browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading") {
    if (headersListener[tabId]) {
      browser.webRequest.onHeadersReceived.removeListener(
        headersListener[tabId]
      );
      delete headersListener[tabId];
    }

    const listener = createHeadersListener(tabId);
    browser.webRequest.onHeadersReceived.addListener(
      listener,
      { urls: ["<all_urls>"] },
      ["blocking"]
    );
    headersListener[tabId] = listener;
  }
});
