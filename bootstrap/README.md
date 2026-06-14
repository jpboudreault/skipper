# Bootstrap Data

Scripts and CSV templates for seeding a fresh Skipper deployment.

## Prerequisites

1. Deploy the app and log in with a Google account listed in `backend/app/tenants.json`.
2. Copy your session JWT from browser devtools (cookie `session`) or from the network tab after login.

## Quick start with curl

Set your deployment URL and token:

```bash
export SKIPPER_URL="https://your-app.fly.dev"
export TOKEN="your_jwt_token_here"
```

**Add a player (team 1):**

```bash
curl -X POST "$SKIPPER_URL/api/players/" \
  -H "Content-Type: application/json" \
  -H "X-Active-Team-ID: 1" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Babe", "last_name": "Ruth", "jersey": 3, "active": true}'
```

**Add a game (team 1):**

```bash
curl -X POST "$SKIPPER_URL/api/games/" \
  -H "Content-Type: application/json" \
  -H "X-Active-Team-ID: 1" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"date": "2026-06-01", "opponent": "Rival Stars", "venue": "Home Field", "home_away": "H", "mode": "develop", "game_type": "season"}'
```

## Seed scripts

Run in order after logging in:

```bash
export SKIPPER_URL="http://localhost:5173"
export TOKEN="your_jwt_token_here"

bash bootstrap/seed_roster.sh "$SKIPPER_URL" "$TOKEN"
bash bootstrap/seed_games.sh "$SKIPPER_URL" "$TOKEN"
bash bootstrap/seed_game_results.sh "$SKIPPER_URL" "$TOKEN"
```

`seed_game_results.sh` fills in final scores and batting lines for the first three demo games (by date), so the dashboard and stats pages look populated for screenshots.

## CSV templates

- `rosters.csv.example` — sample players for teams 1 and 2
- `games.csv.example` — sample schedule entries
- `game_results.csv.example` — final scores for the first three demo games
- `game_batting.csv.example` — batting lines for those games

Copy to `rosters.csv` / `games.csv` / `game_results.csv` / `game_batting.csv` (gitignored) and adapt for your team.
