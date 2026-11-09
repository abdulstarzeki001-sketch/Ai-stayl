export default {
  async fetch(request, env) {
    const headers = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Content-Type": "application/json; charset=utf-8"
    };
    if (request.method === "OPTIONS") return new Response(null, { headers });
    if (request.method !== "POST") return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers });
    try {
      const auth = request.headers.get("Authorization") || "";
      if (!auth.startsWith("Bearer ")) return new Response(JSON.stringify({ error: "سجّل الدخول أولاً" }), { status: 401, headers });
      const verified = await fetch(env.SUPABASE_URL + "/auth/v1/user", {
        headers: { apikey: env.SUPABASE_PUBLISHABLE_KEY, Authorization: auth }
      });
      if (!verified.ok) return new Response(JSON.stringify({ error: "جلسة غير صالحة" }), { status: 401, headers });
      const body = await request.json();
      const messages = Array.isArray(body.messages) ? body.messages.slice(-16) : [];
      if (!messages.length || messages.some(m => !["user", "assistant"].includes(m.role) || typeof m.content !== "string" || m.content.length > 12000)) {
        return new Response(JSON.stringify({ error: "رسائل غير صحيحة" }), { status: 400, headers });
      }
      const result = await env.AI.run("@cf/meta/llama-3.1-8b-instruct-fast", {
        messages: [{ role: "system", content: "You are AI Stayl, a multilingual assistant for software, learning, productivity and authorized defensive cybersecurity." }, ...messages],
        max_tokens: 1200
      });
      return new Response(JSON.stringify({ reply: result.response || "لم يصل رد" }), { headers });
    } catch (error) {
      return new Response(JSON.stringify({ error: "تعذر تنفيذ الطلب", detail: String(error).slice(0, 180) }), { status: 500, headers });
    }
  }
};