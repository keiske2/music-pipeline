@echo off
chcp 65001 >nul
setlocal
rem ═══════════════════════════════════════════════════════════════
rem  Music Pipeline — Windows 초기 세팅 (1회만 실행)
rem  사용법: 이 폴더에서 setup_windows.bat 더블클릭
rem ═══════════════════════════════════════════════════════════════

set "SRC=%~dp0"
set "WORK=%USERPROFILE%\music_pipeline"

echo.
echo ═══════════════════════════════════════════════
echo   Music Pipeline 설치 시작 (Windows)
echo ═══════════════════════════════════════════════
echo.

rem ── 1. Python 확인 ────────────────────────────────────────────
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY ( py -3 --version >nul 2>&1 && set "PY=py -3" )
if not defined PY (
    echo Python이 없습니다.
    echo    https://www.python.org/downloads/ 에서 설치하세요.
    echo    설치 첫 화면에서 "Add python.exe to PATH" 를 꼭 체크하세요.
    goto :fail
)
for /f "delims=" %%v in ('%PY% --version') do echo %%v

rem ── 2. FFmpeg 확인 ────────────────────────────────────────────
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo FFmpeg 설치 시도: winget install -e --id Gyan.FFmpeg
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo winget 설치 실패. https://www.gyan.dev/ffmpeg/builds/ 에서 받아
        echo    bin 폴더를 PATH에 추가한 뒤 다시 실행하세요.
        goto :fail
    )
    echo  FFmpeg 설치됨 — 이 창을 닫고 새 명령 프롬프트에서 다시 실행하세요.
    goto :end
)
echo FFmpeg 설치됨

rem ── 3. Google Chrome 확인 ─────────────────────────────────────
set "CHROME_OK="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_OK=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_OK=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_OK=1"
if defined CHROME_OK (
    echo Google Chrome 설치됨
) else (
    echo  Google Chrome을 찾지 못했습니다. 설치하거나 .env에 CHROME_PATH를 지정하세요.
)

rem ── 4. 작업 폴더 + 파일 복사 ──────────────────────────────────
for %%d in (outputs logs queue sessions) do if not exist "%WORK%\%%d" mkdir "%WORK%\%%d"
copy /Y "%SRC%*.py" "%WORK%\" >nul
copy /Y "%SRC%pipeline_commander.html" "%WORK%\" >nul
copy /Y "%SRC%start_server.bat" "%WORK%\" >nul
copy /Y "%SRC%login.bat" "%WORK%\" >nul
echo 작업 폴더: %WORK%

rem ── 5. 가상환경 + 패키지 ──────────────────────────────────────
if not exist "%WORK%\venv\Scripts\python.exe" (
    echo 가상환경 생성 중...
    %PY% -m venv "%WORK%\venv" || goto :fail
)
echo Python 패키지 설치 중...
"%WORK%\venv\Scripts\python.exe" -m pip install --upgrade pip -q
"%WORK%\venv\Scripts\python.exe" -m pip install -q playwright flask flask-cors requests python-dotenv Pillow numpy || goto :fail
rem BROWSER_MODE=chrome 은 설치된 Chrome을 쓰므로 Playwright 브라우저 다운로드 불필요

rem ── 6. .env 생성 (없는 경우) ──────────────────────────────────
if not exist "%WORK%\.env" (
    > "%WORK%\.env" (
        echo # Telegram 알림 ^(선택^)
        echo TELEGRAM_BOT_TOKEN=
        echo TELEGRAM_CHAT_ID=
        echo.
        echo # 스케줄 시간 ^(24시간 형식^) — 2번을 비우면 하루 1회. PC가 켜져 있는 시간으로!
        echo SCHEDULE_TIME_1=10:00
        echo SCHEDULE_TIME_2=
        echo.
        echo AUTO_LATIN_DAILY=1
        echo VIDEO_MODE=techno
        echo BROWSER_MODE=chrome
        echo # CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
        echo # CHROME_CDP_PORT=9222
    )
    echo  %WORK%\.env 생성됨
)

echo.
echo ═══════════════════════════════════════════════
echo   설치 완료!
echo ═══════════════════════════════════════════════
echo.
echo   1. 최초 로그인 ^(1회^):  %WORK%\login.bat
echo   2. 서버 시작:          %WORK%\start_server.bat
echo   3. 로그인 시 자동 시작: autostart_windows.bat
echo.
goto :end

:fail
echo.
echo 설치 중단
:end
pause
endlocal
