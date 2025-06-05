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

  type == "main_frame"
    ? (data.type = "primaryRequest")
    : (data.type = "subRequest");

  requests.push(data);

  try {
    await browser.runtime.sendMessage({
      type: "doech-update",
      data,
    });
  } catch (e) {
    // sidebar is not opened, ignore the error
  }
};

browser.runtime.onMessage.addListener(async (message, sender) => {
  if (!message.type.startsWith("doech-")) return;

  let messageType = message.type.replace("doech-", "");

  if (messageType === "init") return { data: requests };
});
