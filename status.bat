@echo off
setlocal
cd /d "%~dp0"
set GATEWAY_PORT=9090
if exist ".env" for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"GATEWAY_PORT=" ".env"`) do set GATEWAY_PORT=%%b
echo ---- containers ----
docker compose ps
echo.
echo ---- website and each service, through the gateway ----
curl.exe -s -o nul -w "website              HTTP %%{http_code}\n" http://localhost:%GATEWAY_PORT%/
curl.exe -s -o nul -w "temperature-service   HTTP %%{http_code}\n" http://localhost:%GATEWAY_PORT%/api/temperature/health
curl.exe -s -o nul -w "food-service          HTTP %%{http_code}\n" http://localhost:%GATEWAY_PORT%/api/food/items
curl.exe -s -o nul -w "alert-service         HTTP %%{http_code}\n" http://localhost:%GATEWAY_PORT%/api/alerts/health
curl.exe -s -o nul -w "report-service        HTTP %%{http_code}\n" http://localhost:%GATEWAY_PORT%/api/reports/health
echo.
echo All lines should say HTTP 200.
pause
