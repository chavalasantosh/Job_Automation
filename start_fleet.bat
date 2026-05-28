@echo off
title NowCurry Fleet Command Launch
echo ===================================================
echo   INITIALIZING JOB SEARCH NETWORK (FLEET COMMAND)
echo ===================================================

:: Start Master Command Center
echo [1/6] Starting Master Command Center (Port 7999)...
start "Fleet Manager" /min python fleet_manager.py

echo [2/6] Starting Naukri Dashboard (Port 8000)...
start "Naukri Dash" /min python NowCurry/web_server.py

echo [3/6] Starting LinkedIn Dashboard (Port 8001)...
start "LinkedIn Dash" /min python LinkieDin/web_server.py

echo [4/6] Starting Foundit Dashboard (Port 8002)...
start "Foundit Dash" /min python Foundit/web_server.py

echo [5/6] Starting Glassdoor Dashboard (Port 8003)...
start "Glassdoor Dash" /min python GallasuDooru/web_server.py

echo [6/6] Starting Indeed Dashboard (Port 8004)...
start "Indeed Dash" /min python InDeed/web_server.py

echo.
echo SUCCESS: Fleet is launching!
echo Visit: http://localhost:7999 to manage the fleet.
echo.
pause
