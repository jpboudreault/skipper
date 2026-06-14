#!/usr/bin/env bash
# deploy.sh — Deploy Skipper to Fly.io
#
# Reads FLY_APP_NAME from backend/.env so the app name stays out of version control.
# Usage: ./deploy.sh

set -e

# Load FLY_APP_NAME from backend/.env
if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.dist and fill in your values."
  exit 1
fi

export $(grep -v '^#' backend/.env | xargs)

if [ -z "$FLY_APP_NAME" ]; then
  echo "ERROR: FLY_APP_NAME is not set in backend/.env"
  exit 1
fi

echo "==> Deploying to Fly.io app: $FLY_APP_NAME"
fly deploy --app "$FLY_APP_NAME"
