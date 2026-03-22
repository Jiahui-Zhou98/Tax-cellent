#!/bin/bash
set -e

# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
cd ..

# Frontend
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev &
cd ..

echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop"

trap "kill 0" EXIT
wait
