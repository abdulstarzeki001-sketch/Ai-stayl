import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = file => readFileSync(join(here, file), "utf8");
const files = {
  "/agent.html": src("../agent.html"),
  "/agent.css": src("../agent.css"),
  "/agent.js": src("../agent.js")
};
let api = src("agent-worker.js");
if (!api.includes("export default {")) throw new Error("Worker export marker missing");
api = api.replace("export default {", "const agentApi = {");

const out = api + "\nconst STATIC_PAGES = " + JSON.stringify(files) + `;\n
export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      const pathname = new URL(request.url).pathname;
      if (pathname === "/") return Response.redirect(new URL("/agent.html", request.url).toString(), 302);
      if (Object.prototype.hasOwnProperty.call(STATIC_PAGES, pathname)) {
        const type = pathname.endsWith(".html") ? "text/html" : pathname.endsWith(".css") ? "text/css" : "application/javascript";
        return new Response(STATIC_PAGES[pathname], {status:200,headers:{"content-type":type+"; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
      }
    }
    return agentApi.fetch(request, env);
  }
};
`;
mkdirSync(join(here, "dist"), { recursive: true });
writeFileSync(join(here, "dist/agent-bundle.mjs"), out);
console.log("Bundled research Worker (" + out.length + " bytes)");
