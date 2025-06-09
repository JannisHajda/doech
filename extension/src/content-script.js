window.addEventListener("message", async (event) => {
  if (event.data?.from === "selenium" && event.data.action === "export") {
    let res = await browser.runtime.sendMessage({
      type: "doech-export",
    });

    if (!res || !res.data) {
      console.error("Failed to export data");
      return;
    }

    window.postMessage({
      from: "doech",
      to: "selenium",
      action: "export",
      data: res.data,
    });
  }
});
