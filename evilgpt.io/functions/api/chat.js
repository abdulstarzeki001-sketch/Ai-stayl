/**
 * Authenticated same-origin AI-Stayl chat proxy.
 * Authorize with the current project's Supabase Auth server before forwarding.
 */
const UPSTREAM = "https://chat-ai-stayl.abdulstarzeki001.workers.dev/";
const AUTH_ENDPOINT = "https://ruosabdszffqdobeqgmz.supabase.co/auth/v1/user";
const PUBLISHABLE_KEY = "sb_publishable_1PPYe8Tod6yDvegWzv5p-g_EIgu9zgE";
const ALLOWED_EMAIL = "abdulstarzeki001@gmail.com";

function json(body, status) {
  return new Response(JSON.stringify(body), {status, headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff"
  }});
}

export async function onRequest({request}) {
  if(request.method === "OPTIONS") return new Response(null, {status:204, headers:{
    "access-control-allow-methods":"POST, OPTIONS",
    "access-control-allow-headers":"Authorization, Content-Type",
    "access-control-max-age":"86400"
  }});
  if(request.method !== "POST") return json({error:"Method not allowed"},405);
  const authHeader = request.headers.get("authorization") || "";
  if(!/^Bearer\s+\S+$/.test(authHeader)) return json({error:"Authentication required"},401);
  try {
    const verify = await fetch(AUTH_ENDPOINT, {
      method:"GET",
      headers:{"authorization":authHeader,"apikey":PUBLISHABLE_KEY,"accept":"application/json"},
      redirect:"error",
      signal:AbortSignal.timeout(8000)
    });
    if(verify.status===401||verify.status===403) return json({error:"Invalid or expired session"},401);
    if(!verify.ok) return json({error:"Authentication service unavailable"},503);
    const user = await verify.json();
    if(user?.email?.toLowerCase() !== ALLOWED_EMAIL || user?.is_anonymous) return json({error:"Account not authorized"},403);
  } catch {
    return json({error:"Authentication validation unavailable"},503);
  }
  try {
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("cookie");
    const upstream = await fetch(UPSTREAM, {method:"POST",headers,body:request.body,redirect:"manual"});
    if(upstream.status === 404 || upstream.status === 502) return json({error:"Chat backend unavailable"},503);
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("cache-control","no-store");
    responseHeaders.set("x-content-type-options","nosniff");
    return new Response(upstream.body,{status:upstream.status,headers:responseHeaders});
  } catch {
    return json({error:"Chat backend connection failed"},503);
  }
}
