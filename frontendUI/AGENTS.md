# Incident Commander UI

React + TanStack Start frontend for the Incident Commander API.

## Development

1. Start the API: `incident-commander serve` (port 8080)
2. Start the UI: `cd frontendUI && bun install && bun run dev` (port 3000)

The Vite dev server proxies `/api` and `/webhooks` to the backend.

## API wiring

- Client calls use `src/lib/api.ts` with `VITE_API_URL` defaulting to `/api`
- Backend responses are normalized in `src/lib/api-mapper.ts` to match UI types
