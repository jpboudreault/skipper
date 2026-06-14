#!/usr/bin/env bash
# seed_roster.sh — Bootstrap sample players from rosters.csv.example

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
CSV="${SCRIPT_DIR}/rosters.csv"

if [ ! -f "$CSV" ]; then
  echo "No rosters.csv found — using rosters.csv.example"
  CSV="${SCRIPT_DIR}/rosters.csv.example"
fi

strip_cr() { printf '%s' "$1" | tr -d '\r'; }

echo "Seeding rosters to: $URL"

tail -n +2 "$CSV" | while IFS=, read -r team_id first last jersey; do
  team_id=$(strip_cr "$team_id")
  first=$(strip_cr "$first")
  last=$(strip_cr "$last")
  jersey=$(strip_cr "$jersey")

  echo " -> Adding $first $last (#$jersey) to team $team_id"
  http_code=$(curl -s -o /tmp/skipper_seed_resp.txt -w "%{http_code}" \
    -X POST "$URL/api/players/" \
    -H "Content-Type: application/json" \
    -H "X-Active-Team-ID: $team_id" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"first_name\": \"$first\", \"last_name\": \"$last\", \"jersey\": $jersey, \"active\": true}")

  if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
    echo "    Error ($http_code): $(cat /tmp/skipper_seed_resp.txt)"
  fi
done

echo "Roster seeding complete."
