# ⚾ Skipper

**Skipper** is a coach-first web app for baseball teams. It handles the full game-day workflow — roster, availability, lineup optimization, official printouts, box scores, and season stats — in one place. FastAPI backend, SvelteKit frontend, deployed as a single container on [Fly.io](https://fly.io).

## Built for real coaching workflows

Skipper was originally built for **LFBQ** coaches who need to submit a lineup before each game, maintains statistics for their players , and respect **pitch-count and rest rules** across a busy weekly schedule.

**Baseball Québec is the default league format** — lineup printouts and AI scoresheet parsing use the Québec template out of the box. Other leagues can plug in their own formats via `tenants.json` (see [League formats](#league-formats) below).

## Why coaches use Skipper

- **Stop rebuilding lineups from scratch** — an optimizer assigns positions inning-by-inning from your ratings, respects absences and injuries, and balances bench time fairly.
- **Develop, compete, or go optimal** — pick game mode to chase fielding strength with multiple lineup choices, maximize position variety, or auto-apply the best-quality grid in one click.
- **Preview before you commit** — when the optimizer offers several lineups, switch tabs to see the full inning grid for each option before applying.
- **Game day, sorted** — track who's in, who's out, lock key positions, print the official batting-order card, and go.
- **Stats without the spreadsheet grind** — snap a photo of the scoresheet and let AI pre-fill the batting grid; review, tweak, and save.
- **Pitching rules enforced for you** — configurable pitch-count limits and rest days; separate tournament pitch-count buckets; eligibility checked before a player is sent to the mound.
- **One login, multiple teams** — manage several rosters (e.g. 13U and 15U) with isolated data and per-team league settings.
- **Season view that actually helps** — batting, pitching, and position stats filtered by game type so you can see trends, not just totals.
- **League schedule in sync** — pull season, playoff, and tournament games from Spordle (LFBQ); opponent W-L-D on every upcoming game before you even open the lineup tab.
- **English or French** — bilingual UI with per-team language defaults; lock to one language in production if you prefer.

## Features

| Area | What you get |
|------|----------------|
| **Dashboard** | Upcoming games with opponent record (W-L-D), recent results, quick links to lineup/availability, pitching plan shortcut |
| **Games** | Upcoming and past tabs; next-game hero cards; win/loss/draw pills on completed games; opponent overview on game detail |
| **Roster** | Players, substitutes, head/assistant coaches, jersey numbers, default batting order |
| **Position ratings** | Rate each player at every position; mark spots as forbidden |
| **Schedule** | Season, postseason, and tournament games with opponent, venue, home/away, and game-type badges; adjustable innings per game |
| **Spordle sync (LFBQ)** | One-click import from multiple Spordle schedules (regular season + playoffs + tournaments); links games to league IDs without overwriting your game mode |
| **Opponent intel** | Standing, W-L-D record, runs per game, last completed league games, and links to Spordle — season stats even when the upcoming game is a playoff or tourney |
| **Availability** | Per-game available / absent / late; drag on desktop, touch-drag or tap arrows on mobile |
| **Lineup optimizer** | CP-SAT solver with **compete**, **develop**, and **optimal** modes; up to five previewable options (compete/develop); locked cells; bench-fairness constraints; mid-game injury marking; pitcher re-entry and rest rules; add/remove innings; lineup history snapshots |
| **Batting order** | Drag-and-drop on desktop; touch-drag and ↑/↓ arrows on mobile; printable official lineup card and separate defensive-positions sheet |
| **Box scores** | Batting and pitching entry; photo-assisted scoresheet import with improved Baseball Québec OCR (two-pass transcribe + interpret, row cropping) |
| **Pitching plan** | Rolling view of pitcher innings across upcoming games; tournament pitch-count rest rules |
| **Stats** | Season batting, pitching, and position breakdowns (bench excluded from field-position %); development trends (cumulative OPS, position variety); standings support wins, losses, and draws |
| **Auth & teams** | Google or Microsoft sign-in; multiple isolated rosters per login; settings per team in `tenants.json` |

## Screenshots

Screenshots use **demo data only** — regenerate locally with [`bootstrap/`](bootstrap/README.md).

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard with recent games and top performers" width="720">
</p>
<p align="center"><em>Dashboard — recent results, upcoming games, and top performers</em></p>

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/availability.png" alt="Player availability board"></td>
    <td width="50%"><img src="docs/screenshots/lineup.png" alt="Lineup grid and batting order"></td>
  </tr>
  <tr>
    <td align="center"><em>Availability — drag or tap to set status</em></td>
    <td align="center"><em>Lineup — optimizer with visual option picker</em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/batting-scorecard.png" alt="Batting scorecard entry"></td>
    <td width="50%"><img src="docs/screenshots/pitching-scorecard.png" alt="Pitching scorecard entry"></td>
  </tr>
  <tr>
    <td align="center"><em>Batting scorecard — manual entry or photo upload</em></td>
    <td align="center"><em>Pitching appearances — IP, runs, strikeouts</em></td>
  </tr>
</table>

<p align="center">
  <img src="docs/screenshots/season-stats.png" alt="Season batting statistics table" width="720">
</p>
<p align="center"><em>Season stats — batting, pitching, and positions</em></p>

## League formats

Lineup printouts and scoresheet photo parsing are **league-specific**. Configure each tenant in `backend/app/tenants.json`:

```json
{
  "name": "Mon équipe 13U",
  "lineup_print_version": "baseball_quebec",
  "scoresheet_version": "baseball_quebec"
}
```

| Field | Purpose |
|-------|---------|
| `lineup_print_version` | Printable batting-order card layout (default: `baseball_quebec` — Ordre des Frappeurs) |
| `scoresheet_version` | AI prompt/legend for photo scoresheet import (default: `baseball_quebec` — feuille de pointage) |

To add a new league, register a backend prompt in `backend/app/league_formats/` and a frontend print component in `frontend/src/lib/league_formats/`. Existing tenants without these fields keep the Baseball Québec defaults.

### Spordle schedule sync (LFBQ)

Connect a team to [Spordle](https://page.spordle.com) to import games and show opponent scouting data. Configure `integration_version` and `integration_config` in `tenants.json`.

**Multiple schedules per team** — list every Spordle schedule your team plays on (regular season, playoffs, provincial tournament, etc.). Sync pulls them all; each imported game gets the right `game_type`. Opponent intel (standing, W-L-D, recent games) always comes from the **season** schedule, including when you're preparing for a playoff game.

```json
{
  "integration_version": "lfbq_spordle",
  "integration_config": {
    "our_spordle_team_id": 167215,
    "page_slug": "ligue-feminine-de-baseball-du-quebec",
    "page_id": "1ed21b23-724b-6b80-b13c-06bf14840f98",
    "locale": "fr",
    "schedules": [
      { "schedule_id": 193093, "game_type": "season", "label": "Regular season" },
      { "schedule_id": 195112, "game_type": "postseason", "label": "Playoffs" },
      { "schedule_id": 196000, "game_type": "tournament", "label": "Provincial" }
    ]
  }
}
```

On the **Games** page: **Sync from Spordle** imports/updates games; every upcoming card shows the opponent's **W-L-D** record when intel is available. The game overview adds standing, runs per game, recent results, and Spordle links.

Full field reference and URL parsing: [`docs/league-integrations.md`](docs/league-integrations.md).

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- WSL (recommended when developing on Windows)

## Quick start (local)

### 1. Configure environment

```bash
cp backend/.env.dist backend/.env
cp backend/app/tenants.json.example backend/app/tenants.json
```

Edit `backend/.env`:
- Set `GOOGLE_CLIENT_ID` from the [Google Cloud Console](https://console.cloud.google.com) and/or `MICROSOFT_CLIENT_ID` from [Azure Portal](https://portal.azure.com) (at least one is required for login; both supported)
- Add `http://localhost:5173` to **Authorized JavaScript Origins** (Google) and `http://localhost:5173/auth/callback/microsoft` to **SPA redirect URIs** (Microsoft)
- Keep `DEV_MODE=true` for local development (auto-provisions users on first login)
- Optional: set `SKIPPER_LOCALE=en` or `SKIPPER_LOCALE=fr` to lock the app to one language (also set the same variable when running the frontend dev server, or add it to `frontend/.env`)

Edit `backend/app/tenants.json` with your team names, league format versions, pitch-count rules, admin email addresses, and optional Spordle `schedules` (see [Spordle schedule sync](#spordle-schedule-sync-lfbq)).

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows/WSL
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`.

## Bootstrap data

After logging in, seed sample players and games. See [`bootstrap/README.md`](bootstrap/README.md).

```bash
export SKIPPER_URL="http://localhost:5173"
export TOKEN="your_jwt_token_here"

curl -X POST "$SKIPPER_URL/api/players/" \
  -H "Content-Type: application/json" \
  -H "X-Active-Team-ID: 1" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Babe", "last_name": "Ruth", "jersey": 3, "active": true}'
```

## Running tests

```bash
# Backend (from repo root, in WSL)
bash scripts/test_backend.sh

# Frontend type-check
cd frontend && npm run check

# Scoresheet OCR eval (manual; needs ANTHROPIC_API_KEY — see backend/tests/fixtures/scoresheets/README.md)
export ANTHROPIC_API_KEY=sk-ant-...
PYTHONPATH=./backend backend/.venv/bin/python backend/tools/eval_scoresheets.py
```

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Fly.io setup. Deploy with:

```bash
bash deploy.sh
```

## Project structure

```
backend/     FastAPI API, SQLite database, lineup optimizer, league format plugins, Spordle integrations
frontend/    SvelteKit UI, printable lineup formats, opponent intel panels
bootstrap/   Seed scripts and CSV templates
docs/        League integration guide, screenshot gallery (`docs/screenshots/`)
Dockerfile   Unified production image
fly.toml     Fly.io configuration
deploy.sh    Deployment helper (reads FLY_APP_NAME from backend/.env)
backup_db.sh Database backup helper (reads FLY_APP_NAME from backend/.env)
```

## License

MIT — see [LICENSE](LICENSE).
