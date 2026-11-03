# MIITHII Dashboard

Next.js dashboard (static export) for the MIITHII engine — ticket queue,
reply drafts with receipts, knowledge management, usage, team seats.

Architecture decisions: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Build-time environment

`.env.local` (gitignored) must set — these bake into the export at build time:

```
NEXT_PUBLIC_ENGINE_URL=https://miithii-engine.onrender.com
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

A missing `NEXT_PUBLIC_ENGINE_URL` ships a dashboard that calls
`localhost:8000` — check the signup footer if data silently stops loading.

## Commands

```bash
pnpm install
pnpm dev          # dev server (dev-mode hydration can stall; trust builds)
pnpm build        # static export into out/
pnpm lint
```

## Deploy

```bash
pnpm exec wrangler pages deploy out --project-name miithii-dashboard
```

Production is the main domain; per-deploy `*.pages.dev` hash URLs are
throwaway previews (stale content possible, not in the engine's CORS
allowlist). Verify deploys by content marker (grep the served bundle), not
by status code.
