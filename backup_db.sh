#!/usr/bin/env bash
# backup_db.sh — Download production SQLite database from Fly.io
#
# Reads FLY_APP_NAME from backend/.env so the app name stays out of version control.
# Backups are written to backup_private/ (gitignored).
#
# Usage:
#   ./backup_db.sh              # download database only
#   ./backup_db.sh --snapshot   # download database + create Fly volume snapshot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.dist and fill in your values."
  exit 1
fi

export $(grep -v '^#' backend/.env | xargs)

if [ -z "$FLY_APP_NAME" ]; then
  echo "ERROR: FLY_APP_NAME is not set in backend/.env"
  exit 1
fi

DATABASE_PATH="${DATABASE_PATH:-/data/database.db}"
BACKUP_DIR="backup_private"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/${FLY_APP_NAME}-${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

echo "==> Backing up database from Fly.io app: $FLY_APP_NAME"
echo "    Remote path: $DATABASE_PATH"
echo "    Local file:  $BACKUP_FILE"

fly ssh sftp get "$DATABASE_PATH" "$BACKUP_FILE" --app "$FLY_APP_NAME"

if [ ! -s "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file is missing or empty: $BACKUP_FILE"
  exit 1
fi

BYTES="$(wc -c < "$BACKUP_FILE" | tr -d ' ')"
echo "==> Backup saved ($BYTES bytes): $BACKUP_FILE"

if [ "${1:-}" = "--snapshot" ]; then
  echo "==> Creating on-demand Fly volume snapshot..."
  VOLUME_ID="$(fly volumes list --app "$FLY_APP_NAME" | awk '/skipper_data/ {print $1; exit}')"
  if [ -z "$VOLUME_ID" ]; then
    echo "ERROR: No volume named skipper_data found for app $FLY_APP_NAME"
    exit 1
  fi
  fly volumes snapshots create "$VOLUME_ID" --app "$FLY_APP_NAME"
  echo "==> Snapshot created for volume: $VOLUME_ID"
fi
