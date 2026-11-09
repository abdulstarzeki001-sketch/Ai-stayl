# AI Stayl

A clean Arabic-first AI chat app with Supabase Auth, per-user conversation storage, Row Level Security, Cloudflare Pages, and Cloudflare Workers AI.

## Components
- `index.html`: responsive frontend and Supabase Auth/chat client.
- `backend/worker.js`: authenticated AI endpoint.
- Supabase tables: `public.conversations`, `public.messages` (RLS enabled).

## Cloudflare Worker bindings
Create an AI binding named `AI`, plus plain-text bindings:
- `SUPABASE_URL`: your Supabase project URL.
- `SUPABASE_PUBLISHABLE_KEY`: your Supabase publishable key.

Deploy `backend/worker.js` as a Worker and enable its `workers.dev` subdomain. The frontend currently calls the deployed Worker endpoint.

Never put Supabase secret/service-role keys in the browser or repository. The browser only uses a publishable key; RLS scopes all saved data to the signed-in user.

## Safety scope
The assistant is intended for general help and authorized defensive security. No credential theft, phishing, or unauthorized data access functionality is included.

## Research Agent (new)
- **UI:** `/agent.html` — Arabic-first multi-source research workspace. Linked from the chat header.
- **Worker:** `backend/agent-worker.js` — separately deployed to `agent-ai-stayl.abdulstarzeki001.workers.dev`; does not modify the existing chat Worker.
- **Authentication:** reuses this app's Supabase Auth session; verifies every POST token against `/auth/v1/user`.
- **AI:** Cloudflare Workers AI binding `AI` (Llama 3.1 8B fast). No AI secret stored in the frontend.
- **Research:** add public HTTPS page, Bing RSS search (best-effort), choose up to five text sources, ask questions with numbered source citations.
- **History:** `public.agent_runs` in Supabase with per-user Row Level Security. Stored history contains questions, replies and sanitized source links, **not** full page text or cookies.
- **Browser extension:** `browser-extension/` is a Chrome MV3 extension. In Chrome, open `chrome://extensions`, enable Developer mode, choose *Load unpacked*, select the `browser-extension` directory, and open the extension popup. Select the desired tabs and explicitly approve the site access request. Then open `/agent.html` to import the selected snapshots. Chrome's privileged pages and sites that deny permission are not accessible.
- **Worker settings:** `AI` (AI binding), `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (public value). Never insert a `service_role` or `sb_secret_` key.
- **Tests:** `cd ai-stayl-app/backend && npm test` with Node 22. CI runs the tests on Worker changes.

### Trust boundaries and limitations
Read-only in v1: no login bypass, no form submissions, no account changes, no vulnerability scans on third-party production systems. The extension excludes input fields and cookies; visible page text is nevertheless shared with Workers AI **only when you select the tabs and submit a question**. Treat imported content as untrusted evidence. Public page fetching accepts HTTPS and rejects private/IP/localhost hostnames and redirects; DNS rebinding needs additional platform-level network controls before treating this as a general-purpose fetch proxy. Search uses a public RSS endpoint that can become unavailable; when this happens, the UI offers a search-engine fallback. The existing chat continues to use `chat-ai-stayl` unchanged.

### Live fallback (Cloudflare Pages queue)
The independently deployed Agent UI is available at https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html. Its Worker serves the same HTML/CSS/JS while the GitHub-connected Pages build is queued. The Chrome extension targets this live Worker and also supports the Pages origin once it deploys.
