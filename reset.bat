@echo off
cd /d "%~dp0"
echo This deletes ALL FoodSafe data (readings and food items) and rebuilds from scratch.
set /p ok=Type YES to continue: 
if /i not "%ok%"=="YES" exit /b
docker compose down -v --remove-orphans
call start.bat
