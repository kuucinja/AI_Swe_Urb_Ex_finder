@echo off
cd /d %~dp0

echo ============================
echo   IR Agent Dev Launcher
echo ============================

:: Start Backend (FastAPI)
start "Backend" cmd /k "uvicorn backend.server:app --reload --port 8000"

:: Start Frontend (React/Vite)
start "Interface" cmd /k "cd interface && npm run dev"

echo.
echo Both services are starting...
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173 (or Vite port)
echo.

pause