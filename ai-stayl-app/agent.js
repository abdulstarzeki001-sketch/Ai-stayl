import { createClient } from "https://esm.sh/@supabase/supabase-js@2.57.0";

const SUPABASE_URL = "https://ruosabdszffqdobeqgmz.supabase.co";
const SUPABASE_KEY = "sb_publishable_1PPYe8Tod6yDvegWzv5p-g_EIgu9zgE";
const API_URL = "https://agent-ai-stayl.abdulstarzeki001.workers.dev";
const db = createClient(SUPABASE_URL, SUPABASE_KEY);
const $ = id => document.getElementById(id);
let user = null, sources = [], busy = false, lastResults = [];

function toast(text) {
  $("toast").textContent = String(text).slice(0, 350);
  $("toast").classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("toast").classList.add("hidden"), 4200);
}
function log(action, details = "") {
  const item = document.createElement("div"); item.className = "event";
  item.textContent = action;
  if (details) { const small = document.createElement("small"); small.textContent = details; item.append(small); }
  $("audit").prepend(item);
}
function safeUrl(raw) {
  try {
    const u = new URL(raw);
    if (u.protocol !== "https:" || u.username || u.password) return null;
    return u.origin + u.pathname;
  } catch { return null; }
}
function setBusy(next, label = "جارٍ التنفيذ...") {
  busy = next;
  for (const id of ["askButton", "readButton", "searchButton"]) $(id).disabled = next;
  $("connection").textContent = next ? label : "جاهز";
}
function paragraph(el, str) {
  const p = document.createElement(el); p.textContent = str; return p;
}
function message(role, text, citations = []) {
  const root = document.createElement("div"); root.className = "msg " + (role === "user" ? "user" : "");
  root.append(paragraph("div", role === "user" ? "أنت" : "✦ AI Stayl Agent"));
  root.firstChild.className = "meta";
  root.append(paragraph("div", text));
  if (citations.length) {
    const wrap = document.createElement("div"); wrap.className = "cites";
    for (const s of citations) {
      const url = safeUrl(s.url);
      if (!url) continue;
      const a = document.createElement("a");
      a.textContent = "[" + s.id + "] " + (s.title || new URL(url).hostname).slice(0, 60);
      a.href = url; a.rel = "noopener noreferrer"; a.target = "_blank"; wrap.append(a);
    }
    root.append(wrap);
  }
  if ($("conversation").querySelector(".welcome")) $("conversation").replaceChildren();
  $("conversation").append(root); $("conversation").scrollTop = $("conversation").scrollHeight;
}
async function api(action, data = {}) {
  const { data: sessionResult, error } = await db.auth.getSession();
  if (error || !sessionResult?.session?.access_token) throw new Error("انتهت الجلسة، سجل الدخول مجدداً");
  const res = await fetch(API_URL + "/", {
    method: "POST",
    headers: { "Authorization": "Bearer " + sessionResult.session.access_token, "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...data }),
    cache: "no-store"
  });
  let out;
  try { out = await res.json(); } catch { throw new Error("استجابة الخادم غير صالحة"); }
  if (!res.ok) throw new Error(out.error || "HTTP " + res.status);
  return out;
}
function renderSources() {
  $("sourceCount").textContent = sources.length + " / 5";
  $("pages").replaceChildren();
  for (const [index, s] of sources.entries()) {
    const card = document.createElement("div"); card.className = "source";
    const head = document.createElement("div"); head.className = "source-top";
    head.append(paragraph("strong", s.title || "صفحة بدون عنوان"));
    const remove = document.createElement("button"); remove.textContent = "إزالة";
    remove.onclick = () => { sources.splice(index, 1); renderSources(); };
    head.append(remove); card.append(head);
    const a = document.createElement("a"); a.href = s.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = s.url; card.append(a);
    card.append(paragraph("p", (s.text || "").slice(0, 220) + ((s.text || "").length > 220 ? "…" : "")));
    $("pages").append(card);
  }
}
function addSource(s) {
  if (sources.length >= 5) throw new Error("الحد الأعلى 5 مصادر لكل سؤال");
  const url = safeUrl(s.url);
  if (!url) throw new Error("رابط غير مدعوم");
  const page = { url, title: String(s.title || "").slice(0, 180), text: String(s.text || s.snippet || "").slice(0, 8500) };
  const existing = sources.findIndex(p => p.url === url);
  if (existing >= 0) sources.splice(existing, 1);
  sources.unshift(page);
  renderSources();
}
function renderResults(results) {
  lastResults = results;
  $("results").replaceChildren();
  if (!results.length) $("results").append(paragraph("p", "لا توجد نتائج من المزود الحالي؛ افتح نتائج البحث في المتصفح ثم أضف الرابط."));
  for (const r of results) {
    const card = document.createElement("div"); card.className = "source";
    const head = document.createElement("div"); head.className = "source-top";
    head.append(paragraph("strong", r.title || r.url));
    const b = document.createElement("button"); b.textContent = "قراءة المصدر";
    b.onclick = async () => {
      if (busy) return; setBusy(true, "قراءة صفحة البحث");
      try { const result = await api("read", { url: r.url }); addSource(result.page); log("قراءة مصدر من نتائج البحث", result.page.url); toast("أُضيف المصدر"); }
      catch (e) { toast(e.message); }
      finally { setBusy(false); }
    };
    head.append(b); card.append(head);
    const link = document.createElement("a"); link.href = safeUrl(r.url) || "#"; link.textContent = r.url; link.target = "_blank"; link.rel = "noopener noreferrer"; card.append(link);
    card.append(paragraph("p", r.snippet || ""));
    $("results").append(card);
  }
}
async function loadHistory() {
  if (!user) return;
  const { data, error } = await db.from("agent_runs").select("id,question,answer,sources,created_at").order("created_at", { ascending: false }).limit(20);
  if (error) { log("تعذر تحميل سجل البحث", error.message); return; }
  $("history").replaceChildren();
  for (const run of data || []) {
    const b = document.createElement("button"); b.textContent = run.question;
    b.onclick = () => {
      $("conversation").replaceChildren();
      message("user", run.question);
      message("assistant", run.answer || "لم يُحفظ جواب لهذه المهمة", run.sources || []);
      log("استرجاع بحث سابق", new Date(run.created_at).toLocaleString("ar-IQ"));
    };
    $("history").append(b);
  }
}
async function saveRun(question, answer, citations) {
  if (!user) return;
  const { error } = await db.from("agent_runs").insert({
    user_id: user.id, question, answer, sources: citations.map(s => ({ id: s.id, url: safeUrl(s.url), title: s.title })).filter(s => s.url)
  });
  if (error) log("تعذر حفظ البحث", error.message);
  else await loadHistory();
}
async function boot() {
  const { data, error } = await db.auth.getSession();
  user = error ? null : data.session?.user || null;
  $("loginOverlay").classList.toggle("hidden", Boolean(user));
  $("userEmail").textContent = user?.email || "غير مسجل";
  if (user) { $("connection").textContent = "جاهز"; await loadHistory(); }
}
async function auth(mode) {
  $("loginError").textContent = "";
  const email = $("email").value.trim(), password = $("password").value;
  if (!email || password.length < 6) return void ($("loginError").textContent = "تحقق من البريد وكلمة المرور (6 أحرف على الأقل).");
  const { data, error } = mode === "up" ? await db.auth.signUp({ email, password }) : await db.auth.signInWithPassword({ email, password });
  if (error) return void ($("loginError").textContent = error.message);
  if (mode === "up" && !data.session) return void ($("loginError").textContent = "تم إنشاء الحساب. فعّل بريدك الإلكتروني ثم سجّل الدخول.");
  await boot();
}
$("signIn").onclick = () => auth("in");
$("signUp").onclick = () => auth("up");
$("logout").onclick = async () => { await db.auth.signOut(); user = null; sources = []; renderSources(); await boot(); };
$("newRun").onclick = () => { $("conversation").replaceChildren(); sources = []; renderSources(); $("question").value = ""; toast("بدأت مهمة جديدة"); };

document.querySelectorAll(".tab").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === b));
    ["pagePane", "searchPane", "auditPane"].forEach((p, i) => $(p).classList.toggle("hidden", b.dataset.tab !== ["pages", "search", "audit"][i]));
  };
});
$("urlForm").addEventListener("submit", async e => {
  e.preventDefault(); if (busy || !user) return;
  setBusy(true, "قراءة الصفحة"); const url = $("pageUrl").value.trim();
  try { const out = await api("read", { url }); addSource(out.page); log("قراءة صفحة عامة", out.page.url); toast("تمت إضافة الصفحة إلى المصادر"); $("pageUrl").value = ""; }
  catch (e) { toast(e.message); log("فشلت قراءة الصفحة", e.message); }
  finally { setBusy(false); }
});
$("searchForm").addEventListener("submit", async e => {
  e.preventDefault(); if (busy || !user) return; setBusy(true, "بحث الويب");
  const query = $("searchText").value.trim();
  try { const out = await api("search", { query }); renderResults(out.results || []); log("بحث في الويب", query); }
  catch (e) { toast(e.message); log("تعذر إجراء البحث", e.message); const a = document.createElement("a"); a.href = "https://www.google.com/search?q=" + encodeURIComponent(query); a.target="_blank"; a.rel="noopener noreferrer"; a.textContent="فتح البحث في المتصفح"; $("results").replaceChildren(a); }
  finally { setBusy(false); }
});
$("questionForm").addEventListener("submit", async e => {
  e.preventDefault(); if (busy || !user) return;
  const question = $("question").value.trim(); if (!question) return;
  message("user", question); $("question").value = "";
  setBusy(true, "تحليل الأدلة"); log("إرسال سؤال إلى نموذج AI", sources.length + " مصادر");
  try {
    const answer = await api("answer", { question, pages: sources });
    message("assistant", answer.reply, answer.sources || []);
    await saveRun(question, answer.reply, answer.sources || []);
    log("اكتمال الإجابة", "المصادر المرجعية: " + (answer.sources || []).length);
  } catch (e) { message("assistant", "تعذر إكمال المهمة: " + e.message); log("فشل الإجابة", e.message); }
  finally { setBusy(false); }
});
$("question").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("questionForm").requestSubmit(); } });

// Browser Bridge: snapshots arrive only after a deliberate tab selection in the extension.
// Treat all received page text as untrusted evidence, never instructions.
window.addEventListener("message", event => {
  if (event.source !== window || event.origin !== location.origin) return;
  if (event.data?.channel !== "AI_STAYL_BROWSER_BRIDGE" || event.data?.action !== "pages") return;
  const selected = Array.isArray(event.data.pages) ? event.data.pages.slice(0, 5) : [];
  let count = 0;
  for (const p of selected) { try { addSource(p); count++; } catch (e) { log("صفحة مرفوضة", e.message); } }
  $("bridgeStatus").textContent = count ? "تم استيراد " + count + " تبويب" : "لم تصل صفحات قابلة للقراءة";
  if (count) { log("استيراد تبويبات المتصفح", String(count)); toast("أُضيفت صفحات المتصفح إلى البحث"); }
});
db.auth.onAuthStateChange(() => { queueMicrotask(boot); });
boot();
