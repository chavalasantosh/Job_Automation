@echo off
setlocal enabledelayedexpansion

echo ########################################################
echo # NOWCURRY INFINITY V2 - NATIVE BOOTSTRAP (WINDOWS)    #
echo ########################################################

:: 1. Setup Environment
set PYTHONPATH=%CD%
set DATABASE_URL=sqlite:///./nowcurry_native.db
set RELAY_URL=http://localhost:8000
set MISSION_STORAGE=.\missions

:: 2. Ensure Storage exists
if not exist "%MISSION_STORAGE%" mkdir "%MISSION_STORAGE%"

:: 3. Launch the Control Plane (API & Relay)
echo [1/3] Launching Infinity Control Plane...
start "Infinity API" cmd /k "python -m uvicorn server:app --host 0.0.0.0 --port 8000"

:: 4. Launch the Mission Dashboard
echo [2/3] Launching Command Center Dashboard...
cd dashboard
:: We assume node_modules is already installed or user will run npm install
start "Infinity Dashboard" cmd /k "npm run dev"
cd ..

:: 5. Launch the Worker Hive (Solo Mode for Windows)
echo [3/3] Launching Distributed Worker Hive...
echo WARNING: Redis must be running for Celery. 
echo If you don't have Redis, missions will be queued but not executed.
start "Infinity Worker" cmd /k "celery -A NowCurry.tasks worker --loglevel=info -P solo"

echo.
echo ########################################################
echo # SYSTEMS ONLINE. ACCESS DASHBOARD: http://localhost:5173 #
echo ########################################################
echo.
pause
