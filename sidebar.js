browser.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (!message.type.startsWith("doech")) return;

  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const type = message.type.replace("doech", "").toLowerCase();
  const { data } = message;
  const { tabId, entries } = data;
  const container = document.getElementById("content");

  if (tabs.length === 0 || tabs[0].id !== tabId) return;

  if (type === "update") {
    container.innerHTML = ""; // Clear previous content

    if (entries.length === 0) {
      container.innerHTML = "<p>No ECH updates found for this tab.</p>";
      return;
    }

    // calculate percentage of used ECH and private DNS
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

    for (const data of entries) {
      const p = document.createElement("p");
      p.className = "ech-update";
      p.innerHTML = `
            <strong>Time:</strong> ${new Date(
              data.timeStamp
            ).toLocaleTimeString()}<br>
            <strong>URL:</strong> ${data.url}<br>
            <strong>IP:</strong> ${data.ip}<br>
            <strong>Status Code:</strong> ${data.statusCode}<br>
            <strong>Used ECH:</strong> ${data.usedEch ? "Yes" : "No"}<br>
            <strong>Used Private DNS:</strong> ${
              data.usedPrivateDns ? "Yes" : "No"
            }<br>
        `;
      container.appendChild(p);
    }
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const exportButton = document.getElementById("export");

  exportButton.addEventListener("click", async () => {
    alert("Export functionality is not implemented yet.");
  });
});
