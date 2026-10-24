@echo off
chcp 65001 >nul
rem 서버 실행 (꺼지면 10초 후 자동 재시작)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%USERPROFILE%\music_pipeline"
if not exist logs mkdir logs

:loop
echo [%date% %time%] 서버 시작
"venv\Scripts\python.exe" server.py >> logs\stdout.log 2>&1
echo [%date% %time%] 서버 종료됨 — 10초 후 재시작 (끝내려면 이 창을 닫으세요)
timeout /t 10 /nobreak >nul
goto loop
