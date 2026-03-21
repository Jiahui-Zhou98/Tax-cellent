#!/bin/bash
set -e

echo "=== Tax-cellent — Dev Start ==="
echo ""

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "⚠️  Ollama is not running. Start it with: ollama serve"
  echo "   Then pull the model: ollama pull deepseek-r1:7b"
  echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8000 ..."
cd backend
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

sleep 2

# Start frontend
echo "Starting frontend on http://localhost:3000 ..."
cd frontend
npm install -q
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Running:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo "   API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
