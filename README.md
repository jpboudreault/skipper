# ⚾ Skipper

**Skipper** is a web app for baseball coaches to manage rosters, track player availability, optimize lineups, and analyze season statistics. It consists of a FastAPI backend and a SvelteKit frontend, deployed as a single container on [Fly.io](https://fly.io).

## Features

- Multi-team dashboard with recent stats and upcoming games
- Roster management (players, coaches, substitutes)
- Game scheduling, availability, lineup optimizer, and box scores
- Season batting, pitching, and position statistics
- Google Sign-In authentication with team-based access control

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
- Set `GOOGLE_CLIENT_ID` from the [Google Cloud Console](https://console.cloud.google.com)
- Add `http://localhost:5173` to **Authorized JavaScript Origins** for your OAuth client
- Keep `DEV_MODE=true` for local development (auto-provisions users on first login)

Edit `backend/app/tenants.json` with your team names and admin email addresses.

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
```

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Fly.io setup. Deploy with:

```bash
bash deploy.sh
```

## Project structure

```
backend/     FastAPI API, SQLite database, lineup optimizer
frontend/    SvelteKit UI
bootstrap/   Seed scripts and CSV templates
Dockerfile   Unified production image
fly.toml     Fly.io configuration
deploy.sh    Deployment helper (reads FLY_APP_NAME from backend/.env)
backup_db.sh Database backup helper (reads FLY_APP_NAME from backend/.env)
```

## License

MIT — see [LICENSE](LICENSE).
