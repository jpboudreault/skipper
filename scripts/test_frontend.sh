#!/bin/bash
# Script to run frontend E2E tests (Playwright) in WSL

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/frontend"

echo "Running Frontend E2E Tests..."
# Load profile to ensure npm/npx are available
bash -i -c "npx playwright test"
