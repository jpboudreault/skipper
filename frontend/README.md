# Skipper Frontend

SvelteKit 2 + Svelte 5 application. Uses DaisyUI/Tailwind for styling.

## Development

```bash
npm install
npm run dev
```

Runs at `http://localhost:5173` and proxies `/api/*` requests to the FastAPI backend at `http://127.0.0.1:8000`.

## Scripts

| Command               | Description                    |
| --------------------- | ------------------------------ |
| `npm run dev`         | Start dev server               |
| `npm run build`       | Production build               |
| `npm run check`       | TypeScript + Svelte type check |
| `npx playwright test` | Run E2E tests                  |

## Key paths

- `src/routes/` — pages (dashboard, roster, games, stats, matrix)
- `src/lib/api.ts` — authenticated API fetch helper
- `src/hooks.server.ts` — session cookie auth + API proxy in dev
