@echo off
setlocal
cd /d "%~dp0"
python judge_material.py %*
