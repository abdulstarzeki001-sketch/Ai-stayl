const APP = "https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html";
const KEY = "ai_stayl_bridge_payload";
const el = id => document.getElementById(id);
const available = [];
function show(message) { el("status").textContent = message; }
async function load() {
  const tabs = await chrome.tabs.query({});
  el("tabs").replaceChildren();
  for (const tab of tabs) {
    if (!/^https:\/\//i.test(tab.url || "") || (tab.url?.includes("ai-stayl-app.pages.dev") || tab.url?.includes("agent-ai-stayl.abdulstarzeki001.workers.dev"))) continue;
    const row = document.createElement("div"); row.className = "tab";
    const check = document.createElement("input"); check.type = "checkbox"; check.id = "tab-" + tab.id;
    const label = document.createElement("label"); label.htmlFor = check.id; label.textContent = tab.title || tab.url;
    const url = document.createElement("small"); url.textContent = (() => { try { return new URL(tab.url).hostname; } catch { return ""; } })();
    label.append(url); row.append(check, label); el("tabs").append(row);
    available.push({ tab, check });
  }
  if (!available.length) show("لا توجد تبويبات HTTP/HTTPS قابلة للاستيراد.");
}
function snapshotPage() {
  // innerText includes rendered text rather than hidden DOM text. Form values are not collected.
  const rendered = String(document.body?.innerText || "");
  const text = rendered
    .replace(/(?:Bearer\s+)[A-Za-z0-9_.-]{15,}/gi, "[REDACTED]")
    .replace(/\b(?:sk-[A-Za-z0-9_-]{12,}|sb_secret_[A-Za-z0-9_-]{12,})\b/g, "[REDACTED]")
    .replace(/(password|access_token|refresh_token|api_key)\s*[:=]\s*[^\s,;&]{6,}/gi, "$1=[REDACTED]")
    .replace(/\s+/g," ").trim().slice(0,8200);
  return { title:String(document.title).slice(0,180), url:location.origin + location.pathname, text };
}
el("capture").onclick = async () => {
  const selected = available.filter(x => x.check.checked).slice(0, 5);
  if (!selected.length) return show("حدد صفحة واحدة على الأقل.");
  el("capture").disabled = true; const pages = [];
  // Chrome requires permissions.request to run directly from the user gesture.
  // Request all selected HTTPS origins together before any awaited tab extraction.
  const origins = [...new Set(selected.map(({tab}) => new URL(tab.url).origin + "/*"))];
  let granted = false;
  try { granted = await chrome.permissions.request({ origins }); }
  catch (error) { show("تعذر طلب الصلاحيات: " + error.message); }
  if (!granted) { el("capture").disabled = false; return show("يحتاج استيراد الصفحات موافقتك على المواقع المحددة."); }
  for (const { tab } of selected) {
    try {
      const result = await chrome.scripting.executeScript({ target:{tabId:tab.id}, func:snapshotPage });
      if (result?.[0]?.result?.text) pages.push(result[0].result);
    } catch (e) { show("تعذرت قراءة بعض التبويبات: " + (e.message || e)); }
  }
  if (!pages.length) { el("capture").disabled = false; return show("ماكو نص قابل للاستيراد."); }
  await chrome.storage.local.set({ [KEY]:{pages, createdAt:Date.now()} });
  const existing = await chrome.tabs.query({ url:["https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html*", "https://ai-stayl-app.pages.dev/agent.html*", "https://*.ai-stayl-app.pages.dev/agent.html*"] });
  if (existing.length) await chrome.tabs.update(existing[0].id,{active:true});
  else await chrome.tabs.create({url:APP,active:true});
  show("تم تجهيز " + pages.length + " صفحات للتحليل. افتح Agent.");
  el("capture").disabled = false;
};
load().catch(e=>show("خطأ: "+e.message));