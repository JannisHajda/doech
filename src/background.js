const tabData = {};

const requests = [];

browser.webRequest.onHeadersReceived.addListener(
  (details) => receivedRequest(details),
  { urls: ["<all_urls>"] },
  ["blocking"]
);

const receivedRequest = async (details) => {
  const { tabId, requestId, url, timeStamp, ip, statusCode, fromCache, type } =
    details;

  const securityInfo = await browser.webRequest.getSecurityInfo(requestId, {});

  const { usedEch, usedPrivateDns } = securityInfo;

  if (usedEch === undefined || usedPrivateDns === undefined) return;

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

  if (type == "main_frame") {
    data.subsequentRequests = [];
    requests.push(data);

    browser.runtime.sendMessage({
      type: "doech-mainFrame",
      data,
    });
  } else {
    // find the main frame request
    const mainFrameRequest = requests.findLast(
      (req) => req.tabId === tabId && req.type === "main_frame"
    );

    // ignore subsequent requests if the main frame is not present
    if (tabId === -1 || !mainFrameRequest) return;

    // add the subsequent request to the main frame request
    // mainFrameRequest.subsequentRequests.push(data);

    // TODO: send update
  }
};

browser.runtime.onMessage.addListener(async (message, sender) => {
  if (!message.type.startsWith("doech-")) return;

  let messageType = message.type.replace("doech-", "");

  if (messageType === "init") return { data: requests };

  if (messageType === "export") return { data: requests };
});
