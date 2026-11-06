# AI Stayl — Research Agent v2

## What it actually does

The Agent is a read-only research assistant. One question invokes `POST / {action:"research"}`:
1. When the user explicitly imported browser tabs or manually added sources, use those only.
2. Otherwise search the public web: **Brave Search API** when the server-side `BRAVE_SEARCH_API_KEY` secret exists, or best-effort Bing RSS without a key.
3. Try to read up to four HTTPS HTML pages; no redirect follows, no cookies, no form submissions.
4. If a result cannot be read, label it as a search *snippet only*, not a verified page.
5. Summarize the supplied evidence with numbered links. Store question, response, and citations in `public.agent_runs` under per-owner Supabase RLS.

The user can also manually search, read a public HTTPS page, or import selected Chrome/Edge tabs using Browser Bridge.

## Live components

- Frontend: `https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html`
- API: the same Worker, with `/health` and authenticated `POST /`.
- Repository source: `ai-stayl-app/backend/agent-worker.js`, bundled with UI by `node build-agent-bundle.mjs`.
- Source UI: `ai-stayl-app/agent.html`, `agent.css`, `agent.js`.
- User data: Supabase project `ruosabdszffqdobeqgmz`, table `public.agent_runs` with owner-based RLS.
- Chrome extension: `ai-stayl-app/browser-extension`, installed by **Load unpacked** after user consent.

## Required Worker bindings

| Name | Type | Visibility |
| --- | --- | --- |
| `AI` | Workers AI binding | Server-side |
| `SUPABASE_URL` | Text (Supabase project URL) | Public project metadata |
| `SUPABASE_PUBLISHABLE_KEY` | Text (publishable/anon key only) | Public value |
| `BRAVE_SEARCH_API_KEY` | **Optional secret** | Server-only; never commit this |

Brave Search uses the documented `https://api.search.brave.com/res/v1/web/search` endpoint and `X-Subscription-Token` server-side header. If it is not configured, the Agent uses a public RSS fallback; availability and quality are not guaranteed. To configure the token later: Cloudflare dashboard → Workers → agent-ai-stayl → Settings → Variables and Secrets → Add Secret, name `BRAVE_SEARCH_API_KEY`. The key needs to come from a separate Brave Search subscription. Existing chat AI binding is not modified.

## Test and deployment

In `ai-stayl-app/backend`, run `npm test` on Node.js 22+. This builds a standalone deployable module, syntax-checks the bundle, and runs mocked network tests for auth, private host rejection, source reading, search, citations, failed provider, and UI static serving. GitHub Actions runs these checks on PRs before merge.

The standalone Worker is deployed separately through Cloudflare; **merging a PR does not redeploy that Worker by itself**. Deploy `backend/dist/agent-bundle.mjs`, keeping the three existing bindings. Never upload service role keys or tokens to the static UI.

## Trust, privacy and limitations

- The browser extension enumerates open **HTTPS** tabs and reads only tabs explicitly selected and granted permission. Tabs without Chrome permission cannot be read.
- The extension captures rendered text, not form values or HTTP cookies; sensitive text rendered by a site can still be included. Inspect before asking the Agent about personal data.
- It supports a maximum of five selected sources per question. Automatic web research reads at most four public results.
- Web content is untrusted evidence. The model must ignore embedded instructions, but protections against prompt injection are not absolute.
- Public HTML is supported; login walls, CAPTCHAs, scripts that require interaction, and PDFs are not automatically handled. A browser snapshot may help with dynamic pages.
- The Agent cannot operate *every* open tab without explicit browser permission. It does not click links, submit forms, modify accounts, or perform active vulnerability scans.
- Do not use it to collect credentials, private tokens, or secrets from third-party sites.
- Public URL validation denies explicit IP literals/internal hostnames and redirects. For stronger SSRF guarantees (including DNS rebinding protection), route fetching through a network-isolated service and enforce DNS/egress policy there.
- No automatic background execution: each user question triggers a bounded request. If a search provider is down, the Agent reports that rather than inventing sources.

## Useful health checks

```bash
curl -fsS https://agent-ai-stayl.abdulstarzeki001.workers.dev/health
curl -I https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html
```

A healthy /health response demonstrates the Worker responds and has an AI binding. It **does not** prove successful login, search, or model output; those require an authenticated integration test.
