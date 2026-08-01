# Incident Commander UI

React dashboard for triaging Kubernetes incidents: evidence timeline, ranked hypotheses, worker runs, and human-approved rollbacks.

## Prerequisites

- Node.js 20+ or Bun
- Incident Commander API running (`incident-commander serve` on port 8080)

## Development

```sh
cd frontendUI
bun install   # or npm install
bun run dev   # http://localhost:3000
```

Vite proxies `/api` → `http://localhost:8080/api`.

Optional env (see `.env.example`):

- `VITE_API_URL` — API base URL (default `/api`)
- `VITE_API_PROXY_TARGET` — backend URL for the dev proxy (default `http://localhost:8080`)

## Production build

```sh
bun run build
```

When a static build exists in `frontendUI/dist/client/`, `frontendUI/dist/`, or `frontendUI/.output/public/`, `incident-commander serve` serves it at `/` and `/ui` (otherwise the legacy HTML UI).

## Stack

- TanStack Start + Router + React Query
- TypeScript, Tailwind CSS, shadcn/ui
