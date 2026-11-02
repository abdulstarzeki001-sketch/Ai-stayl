// Browser content script: only installed on AI Stayl Pages origins.
(function() {
  const KEY = "ai_stayl_bridge_payload";
  function deliver(payload) {
    if (!payload || !Array.isArray(payload.pages) || !payload.pages.length) return;
    window.postMessage({ channel:"AI_STAYL_BROWSER_BRIDGE", action:"pages", pages:payload.pages.slice(0, 5) }, location.origin);
    chrome.storage.local.remove(KEY);
  }
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes[KEY]?.newValue) deliver(changes[KEY].newValue);
  });
  chrome.storage.local.get(KEY).then(result => { if (result[KEY]) setTimeout(() => deliver(result[KEY]), 250); });
})();