import test from "node:test";
import assert from "node:assert/strict";
import chat from "./worker.js";

test("chat Worker respects rate limiter before running model", async () => {
  const previous = globalThis.fetch;
  let aiCalls = 0;
  globalThis.fetch = async (url) => {
    assert.ok(String(url).includes("/auth/v1/user"));
    return new Response(JSON.stringify({id:"test-user"}),{status:200});
  };
  try {
    const request = new Request("https://chat-ai-stayl.example/", {
      method:"POST",
      headers:{"authorization":"Bearer test","content-type":"application/json"},
      body:JSON.stringify({messages:[{role:"user",content:"test"}]})
    });
    const env={
      SUPABASE_URL:"https://example.supabase.co",
      SUPABASE_PUBLISHABLE_KEY:"test-public-key",
      AI_RATE_LIMITER:{limit:async ({key})=>{assert.equal(key,"test-user");return {success:false};}},
      AI:{run:async ()=>{aiCalls++;return {response:"unwanted"}}}
    };
    const r=await chat.fetch(request,env);
    assert.equal(r.status,429);
    assert.equal(aiCalls,0);
  } finally {globalThis.fetch=previous;}
});
