@echo off
title PowerPlex CRM AI

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     PowerPlex CRM AI — Starting      ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── Check venv exists ─────────────────────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo  [ERROR] venv not found. Run this first:
    echo          python -m venv venv
    echo          venv\Scripts\activate
    echo          pip install -r requirements.txt
    pause
    exit /b 1
)

:: ── Activate venv ──────────────────────────────────────────────────────────
call venv\Scripts\activate.bat
echo  [OK] venv activated

:: ── Check .env ─────────────────────────────────────────────────────────────
if not exist ".env" (
    echo  [WARN] .env file not found — LLM and integrations will not work
) else (
    echo  [OK] .env found
)

:: ── Quick dependency check ─────────────────────────────────────────────────
python -c "import groq, fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo  [WARN] Some packages missing. Installing from requirements.txt...
    pip install -r requirements.txt --quiet
)
echo  [OK] Dependencies ready

:: ── Start server ───────────────────────────────────────────────────────────
echo.
echo  Starting server on http://localhost:8000
echo  Press Ctrl+C to stop
echo.

python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

pause
