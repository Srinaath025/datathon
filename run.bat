@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
echo.
echo ============================================================
echo ============================================================
echo   KSP CrimeIQ -- AI Crime Analytics Platform
echo ============================================================
echo.

cd /d "%~dp0"

REM Check Python
python --version > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3.10+
  pause
  exit /b 1
)

REM Install dependencies
echo [1/3] Installing Python dependencies...
pip install -r requirements.txt -q

REM Generate synthetic data if not exists
if not exist "data\crime_db.sqlite" (
  echo [2/3] Generating synthetic Karnataka crime dataset...
  set PYTHONIOENCODING=utf-8
  python generate_data.py
) else (
  echo [2/3] Dataset already exists. Skipping generation.
)

REM Load environment variables from .env (skip comment lines and blank lines)
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
  echo [ENV] Loaded environment from .env
) else (
  echo [WARN] .env file not found. Copy .env.example, rename to .env, and fill in KSP_SECRET.
  echo        The server will refuse to start without KSP_SECRET set.
)

REM Start server
echo [3/3] Starting FastAPI server on http://localhost:8000
echo.
echo  Open your browser at: http://localhost:8000/login
echo  API docs at:          http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo.

timeout /t 2 /nobreak > nul
start "" "http://localhost:8000/login"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
