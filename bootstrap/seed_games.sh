#!/usr/bin/env bash
# seed_games.sh — Bootstrap sample games from games.csv.example

set -euo pipefail

URL="${1:-http://localhost:5173}"
TOKEN="${2:-}"

if [ -z "$TOKEN" ]; then
  echo "Error: Bearer token is required."
  echo "Usage: $0 [URL] <TOKEN>"
  echo "Example: $0 https://your-app.fly.dev eyJhbGci..."
  exit 1
fi

URL="${URL%/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV="${SCRIPT_DIR}/games.csv"

if [ ! -f "$CSV" ]; then
  echo "No games.csv found — using games.csv.example"
  CSV="${SCRIPT_DIR}/games.csv.example"
fi

strip_cr() { printf '%s' "$1" | tr -d '\r'; }

echo "Seeding games to: $URL"

tail -n +2 "$CSV" | while IFS=, read -r team_id date opponent venue home_away mode game_type; do
  team_id=$(strip_cr "$team_id")
  date=$(strip_cr "$date")
  opponent=$(strip_cr "$opponent")
  venue=$(strip_cr "$venue")
  home_away=$(strip_cr "$home_away")
  mode=$(strip_cr "$mode")
  game_type=$(strip_cr "$game_type")

  echo " -> Adding game on $date vs $opponent (team $team_id)"
  http_code=$(curl -s -o /tmp/skipper_seed_resp.txt -w "%{http_code}" \
    -X POST "$URL/api/games/" \
    -H "Content-Type: application/json" \
    -H "X-Active-Team-ID: $team_id" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"date\": \"$date\", \"opponent\": \"$opponent\", \"venue\": \"$venue\", \"home_away\": \"$home_away\", \"mode\": \"$mode\", \"game_type\": \"$game_type\"}")

  if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
    echo "    Error ($http_code): $(cat /tmp/skipper_seed_resp.txt)"
  fi
done

echo "Game seeding complete."
