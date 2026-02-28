@echo off
cd /d "%~dp0"
start "Gregory Debug UI" cmd /k "cd /d %~dp0debug && py -m http.server 8080"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
) else (
    py -3.12 -m uvicorn gregory.main:app --reload --host 0.0.0.0 --port 8000
)
pause
