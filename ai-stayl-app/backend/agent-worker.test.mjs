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


test("automated research reads search results and cites actual pages", async () => {
  const reset=stubFetch((url, opts)=>{
    if(url.includes("/auth/v1/user")) return authenticated(url,opts);
    if(url.includes("bing.com/search?format=rss")) return new Response(
      '<rss><channel><item><title>Official Guide</title><link>https://www.example.org/guide</link><description>Guide snippet</description></item></channel></rss>',
      {status:200}
    );
    if(url==="https://www.example.org/guide") return new Response(
      '<html><head><title>Official Guide</title></head><body><main>Audited source text</main></body></html>',
      {status:200,headers:{"content-type":"text/html"}}
    );
    throw new Error("unexpected outbound URL " + url);
  });
  try {
    const response=await agent.fetch(req({action:"research",question:"ما مضمون الدليل؟",pages:[]}),base);
    assert.equal(response.status,200);
    const result=await response.json();
    assert.equal(result.provider,"bing_rss");
    assert.equal(result.sources.length,1);
    assert.equal(result.sources[0].url,"https://www.example.org/guide");
    assert.equal(result.steps.at(-1).action,"answer");
  } finally { reset(); }
});

test("research with user-selected tabs does not search the web",async()=>{
  let requests=0;
  const reset=stubFetch((url,opts)=>{
    requests++;
    return authenticated(url,opts);
  });
  try{
    const response=await agent.fetch(req({action:"research",question:"لخص الصفحة",pages:[{
      url:"https://www.example.org/readme",title:"Readme",text:"Sample text"
    }]}),base);
    assert.equal(response.status,200);
    const body=await response.json();
    assert.equal(body.provider,"selected_pages");
    assert.equal(body.sources.length,1);
    assert.equal(requests,1);
  }finally{reset();}
});

test("Brave Search uses server-side key and returns only sanitized public URLs",async()=>{
  let calls=0;
  const reset=stubFetch((url,opts)=>{
    calls++;
    if(url.includes("/auth/v1/user")) return authenticated(url,opts);
    assert.ok(url.startsWith("https://api.search.brave.com/res/v1/web/search?"));
    assert.equal(opts.headers["X-Subscription-Token"],"secret-for-tests-only");
    return new Response(JSON.stringify({web:{results:[
      {title:"Trusted site",url:"https://www.example.org/guide?session=private",description:"Summary"},
      {title:"Private",url:"https://127.0.0.1/admin",description:"Should be removed"}
    ]}}),{status:200,headers:{"content-type":"application/json"}});
  });
  try{
    const response=await agent.fetch(req({action:"search",query:"security guidelines"}),{
      ...base,BRAVE_SEARCH_API_KEY:"secret-for-tests-only"
    });
    assert.equal(response.status,200);
    const body=await response.json();
    assert.equal(body.results.length,1);
    assert.equal(body.results[0].url,"https://www.example.org/guide");
    assert.ok(!JSON.stringify(body).includes("secret-for-tests-only"));
    assert.equal(calls,2);
  }finally{reset();}
});

test("research handles search failure without fabricated citations",async()=>{
  const reset=stubFetch((url,opts)=>{
    if(url.includes("/auth/v1/user")) return authenticated(url,opts);
    return new Response("Unavailable",{status:503});
  });
  try{
    const response=await agent.fetch(req({action:"research",question:"Latest developments"}),base);
    assert.equal(response.status,200);
    const data=await response.json();
    assert.deepEqual(data.sources,[]);
    assert.equal(data.steps[0].status,"unavailable");
  }finally{reset();}
});
