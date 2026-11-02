import test from "node:test";
import assert from "node:assert/strict";
import agent from "./agent-worker.js";

const base = {
  SUPABASE_URL: "https://example.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "test-publishable",
  AI: { async run(_model, payload) {
    assert.equal(payload.messages[0].role, "system");
    return { response: "الجواب من الدليل [1]" };
  }}
};
function req(body, { origin = "https://ai-stayl-app.pages.dev", auth = "Bearer valid" } = {}) {
  const headers = { "content-type":"application/json",origin };
  if (auth) headers.authorization = auth;
  return new Request("https://agent.example/", { method:"POST", headers, body:JSON.stringify(body) });
}
function stubFetch(handler) {
  const before = globalThis.fetch;
  globalThis.fetch = (url, options) => handler(String(url), options);
  return () => { globalThis.fetch = before; };
}
function authenticated(url, options) {
  assert.ok(url.startsWith("https://example.supabase.co/auth/v1/user"));
  assert.equal(options.headers.apikey, "test-publishable");
  assert.equal(options.headers.Authorization, "Bearer valid");
  return new Response('{"id":"test-user"}',{status:200});
}
test("health endpoint is ready and contains no secret", async () => {
  const r=await agent.fetch(new Request("https://agent.example/health"),base);
  assert.equal(r.status,200);
  const body=await r.json();
  assert.equal(body.aiConfigured,true);
  assert.equal(JSON.stringify(body).includes("test-publishable"),false);
});
test("refuse unauthenticated and foreign-origin POST requests",async()=>{
  const a=await agent.fetch(req({action:"answer",question:"hello"},{auth:""}),base);
  assert.equal(a.status,401);
  const b=await agent.fetch(req({action:"answer",question:"hello"},{origin:"https://evil.example"}),base);
  assert.equal(b.status,403);
});
test("block private URL and avoid outbound request",async()=>{
  let seen=0;
  const reset=stubFetch((url,opts)=>{ seen++;return authenticated(url,opts); });
  try {
    const r=await agent.fetch(req({action:"read",url:"https://127.0.0.1/admin"}),base);
    assert.equal(r.status,400);assert.equal(seen,1);
  } finally { reset(); }
});
test("read public HTML, scrub secrets and keep redirects disabled",async()=>{
  let network=0;
  const reset=stubFetch((url,opts)=>{
    network++;
    if(url.includes("/auth/v1/user")) return authenticated(url,opts);
    assert.equal(opts.redirect,"manual");
    assert.equal(url,"https://www.example.org/article?ref=1");
    return new Response('<html><head><title>Example Article</title><script>secret()</script></head><body><main>Useful content. password=super-secret</main></body></html>',{status:200,headers:{"content-type":"text/html"}});
  });
  try {
    const r=await agent.fetch(req({action:"read",url:"https://www.example.org/article?ref=1"}),base);
    assert.equal(r.status,200);
    const b=await r.json();
    assert.equal(b.page.title,"Example Article");
    assert.equal(b.page.url,"https://www.example.org/article");
    assert.ok(b.page.text.includes("Useful content"));
    assert.ok(!b.page.text.includes("super-secret"));
    assert.equal(network,2);
  } finally { reset(); }
});
test("search RSS and return public results",async()=>{
  const reset=stubFetch((url,opts)=>{
    if(url.includes("/auth/v1/user")) return authenticated(url,opts);
    assert.ok(url.includes("bing.com/search?format=rss"));
    return new Response('<rss><channel><item><title>Guide</title><link>https://www.example.org/guide</link><description>Useful guide</description></item></channel></rss>',{status:200});
  });
  try {
    const r=await agent.fetch(req({action:"search",query:"test guide"}),base);
    assert.equal(r.status,200);
    const b=await r.json();
    assert.equal(b.results.length,1);
    assert.equal(b.results[0].url,"https://www.example.org/guide");
  } finally { reset(); }
});
test("answer uses AI binding and returns citations from approved snapshots",async()=>{
  const reset=stubFetch((url,opts)=>authenticated(url,opts));
  try {
    const r=await agent.fetch(req({action:"answer",question:"اشرح",pages:[{url:"https://www.example.org/x",title:"Page",text:"Evidence"}]}),base);
    assert.equal(r.status,200);
    const b=await r.json();
    assert.equal(b.sources.length,1);
    assert.ok(b.reply.includes("[1]"));
  } finally { reset(); }
});
