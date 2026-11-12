@echo off
setlocal
cd /d "%~dp0"
title FoodSafe - start

echo [1/5] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo Docker Desktop is NOT running.
  echo Open Docker Desktop, wait until it says "Engine running", then run start.bat again.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [2/5] Creating .env from .env.example
  copy /y ".env.example" ".env" >nul
) else (
  echo [2/5] .env found
)

set GATEWAY_PORT=9090
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"GATEWAY_PORT=" ".env"`) do set GATEWAY_PORT=%%b

echo [3/5] Cleaning up old FoodSafe containers...
docker rm -f safefood-gateway safefood-temperature-service safefood-food-service safefood-alert-service safefood-report-service safefood-temperature-db safefood-food-db >nul 2>&1
docker compose down --remove-orphans >nul 2>&1

netstat -ano | findstr /r /c:":%GATEWAY_PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo.
  echo Port %GATEWAY_PORT% is already used by another program or container.
  echo Run:  docker ps     to see which container, and  docker stop ^<name^>
  echo Or edit GATEWAY_PORT in the .env file ^(for example 9191^) and run start.bat again.
  pause
  exit /b 1
)

echo [4/5] Building and starting all services ^(first time takes a few minutes^)...
docker compose up -d --build --wait
if errorlevel 1 (
  echo.
  echo Something failed. Last log lines:
  docker compose logs --tail 40
  echo.
  echo Copy the text above and send it for help.
  pause
  exit /b 1
)

echo [5/5] Done. Opening http://localhost:%GATEWAY_PORT%
start "" "http://localhost:%GATEWAY_PORT%"
echo.
echo FoodSafe is running. Use stop.bat to stop it, status.bat to check it.
pause
