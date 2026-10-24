@echo off
chcp 65001 >nul
rem ═══════════════════════════════════════════════════════════════
rem  Windows 로그인 시 서버 자동 시작 등록 (관리자 권한 불필요)
rem  '시작프로그램' 폴더에 실행 파일을 넣는 방식
rem  해제: 아래 STARTUP 폴더의 music_pipeline_server.bat 삭제
rem ═══════════════════════════════════════════════════════════════

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "WORK=%USERPROFILE%\music_pipeline"

if not exist "%WORK%\start_server.bat" (
    echo %WORK%\start_server.bat 이 없습니다. 먼저 setup_windows.bat 을 실행하세요.
    pause
    exit /b 1
)

> "%STARTUP%\music_pipeline_server.bat" (
    echo @echo off
    echo start "Music Pipeline" /min "%WORK%\start_server.bat"
)

echo 자동시작 등록 완료
echo    위치: %STARTUP%\music_pipeline_server.bat
echo    다음 Windows 로그인부터 서버가 최소화 창으로 자동 실행됩니다.
pause
