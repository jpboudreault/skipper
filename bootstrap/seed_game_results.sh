#!/usr/bin/env bash
# seed_game_results.sh — Bootstrap scores and batting stats for demo games

set -euo pipefail

URL="${1:-http://localhost:5173}"
TOKEN="${2:-}"

if [ -z "$TOKEN" ]; then
  echo "Error: Bearer token is required."
  echo "Usage: $0 [URL] <TOKEN>"
  echo "Example: $0 http://localhost:5173 eyJhbGci..."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/seed_game_results.py" "${URL%/}" "$TOKEN"
