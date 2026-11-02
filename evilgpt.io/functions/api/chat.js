/**
 * Same-origin chat API bridge.
 * The browser bundle posts to /api/chat; forward the authenticated request
 * to the existing chat-ai-stayl Worker without exposing any server secret.
 */
const UPSTREAM = "https://chat-ai-stayl.abdulstarzeki001.workers.dev/";

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export async function onRequest({ request }) {
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers": "Authorization, Content-Type",
        "access-control-max-age": "86400",
      },
    });
  }

  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  if (!request.headers.get("authorization")) {
    return json({ error: "Authentication required" }, 401);
  }

  try {
    const headers = new Headers(request.headers);
    headers.delete("host");

    const upstream = await fetch(UPSTREAM, {
      method: "POST",
      headers,
      body: request.body,
      redirect: "manual",
    });

    // Do not let the client fall back to the retired Supabase project.
    if (upstream.status === 404 || upstream.status === 502) {
      return json({ error: "Chat backend unavailable" }, 503);
    }

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("cache-control", "no-store");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return json({ error: "Chat backend connection failed" }, 503);
  }
}
