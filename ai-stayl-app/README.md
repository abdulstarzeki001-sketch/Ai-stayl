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
