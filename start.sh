#!/bin/bash
# start.sh

# 1. Start the FastAPI backend on localhost port 8000
echo "Starting Python FastAPI backend..."
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 2. Start the SvelteKit Node frontend on public port 8080
echo "Starting Node SvelteKit frontend..."
cd /app/frontend
node build/index.js &
FRONTEND_PID=$!

# 3. Monitor both processes
echo "Monitoring background processes (FastAPI: $BACKEND_PID, SvelteKit: $FRONTEND_PID)..."
wait -n $BACKEND_PID $FRONTEND_PID

# Exit if either server crashes
echo "One of the servers terminated. Shutting down container..."
exit $?
