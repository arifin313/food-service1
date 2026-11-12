@echo off
cd /d "%~dp0"
docker compose down --remove-orphans
echo Stopped. Your data is kept. Run start.bat to start again.
pause
