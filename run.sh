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

# Check Python (Removed for Catalyst AppSail compatibility)

# Install dependencies (Handled by Catalyst build phase automatically)
echo "[1/3] Dependencies handled by Catalyst..."

# Generate data if not exists
if [ ! -f "data/crime_db.sqlite" ]; then
  echo "[2/3] Generating synthetic Karnataka crime dataset..."
  python generate_data.py
else
  echo "[2/3] Dataset already exists. Skipping generation."
fi

# Load environment variables from .env (if present)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
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

PORT=${X_ZOHO_CATALYST_LISTEN_PORT:-9000}
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
