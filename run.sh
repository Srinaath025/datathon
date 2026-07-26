#!/bin/bash
# KSP CrimeIQ — AI Crime Analytics Platform
# KSP Datathon 2026 — Challenge 02

set -e
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "  KSP CrimeIQ — AI Crime Analytics Platform"
echo "  KSP Datathon 2026 - Challenge 02"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "[ERROR] Python3 not found. Please install Python 3.10+"
  exit 1
fi

# Install dependencies
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt -q

# Generate data if not exists
if [ ! -f "data/crime_db.sqlite" ]; then
  echo "[2/3] Generating synthetic Karnataka crime dataset..."
  python3 generate_data.py
else
  echo "[2/3] Dataset already exists. Skipping generation."
fi

# Load environment variables from .env (if present)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "[ENV] Loaded environment from .env"
else
  echo "[WARN] .env file not found. Copy .env and fill in KSP_SECRET."
  echo "       The server will refuse to start without KSP_SECRET set."
fi

# Start server
echo "[3/3] Starting FastAPI server on http://localhost:8000"
echo ""
echo "Open your browser at: http://localhost:8000"
echo "API docs at:           http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

# Open browser (works on most Linux/Mac)
if command -v xdg-open &> /dev/null; then
  sleep 2 && xdg-open http://localhost:8000 &
elif command -v open &> /dev/null; then
  sleep 2 && open http://localhost:8000 &
fi

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
