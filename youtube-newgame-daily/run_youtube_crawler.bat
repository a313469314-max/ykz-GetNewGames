@echo off
cd /d %~dp0
python main.py
if errorlevel 1 exit /b %errorlevel%
python export_daily_history.py
