@echo off
cd /d %~dp0

echo ============================
echo   IR Agent Dev Launcher
echo ============================

:: Start Backend (FastAPI) - uses the ir-proj conda env, which has
:: psycopg2/dotenv/fastapi installed (the default "python"/"uvicorn" on
:: PATH does not).
start "Backend" cmd /k "%USERPROFILE%\miniconda3\envs\ir-proj\python.exe -m uvicorn backend.server:app --reload --port 8000"

:: Start Frontend (React/Vite)
start "Interface" cmd /k "cd interface && npm run dev"

echo.
echo Both services are starting...
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173 (or Vite port)
echo.

pause