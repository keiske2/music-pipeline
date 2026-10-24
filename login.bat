@echo off
chcp 65001 >nul
rem 최초 1회 로그인 (Google 계정 → Suno, ChatGPT, YouTube Studio)
set PYTHONUTF8=1
cd /d "%USERPROFILE%\music_pipeline"
"venv\Scripts\python.exe" login_all.py
pause
