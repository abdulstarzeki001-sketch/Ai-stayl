import test from "node:test";
import assert from "node:assert/strict";
import worker from "./dist/agent-bundle.mjs";

test("standalone Worker root redirects to its own Agent page", async () => {
  const response = await worker.fetch(new Request("https://agent-ai-stayl.example.workers.dev/"), {});
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("location"), "https://agent-ai-stayl.example.workers.dev/agent.html");
});

test("Agent HTML, CSS, and JS are served from Worker", async () => {
  for (const [path, type, expected] of [
    ["/agent.html", "text/html", "AI Research Workspace"],
    ["/agent.css", "text/css", ".layout"],
    ["/agent.js", "application/javascript", "SUPABASE_URL"]
  ]) {
    const response = await worker.fetch(new Request("https://agent.example" + path), {});
    assert.equal(response.status, 200);
    assert.match(response.headers.get("content-type"), new RegExp(type));
    assert.match(await response.text(), new RegExp(expected));
  }
});