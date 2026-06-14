#!/bin/bash
# Script to run backend tests in WSL

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Running Backend Tests..."
PYTHONPATH=./backend ./backend/.venv/bin/pytest backend/tests/
