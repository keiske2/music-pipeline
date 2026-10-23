#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🎵 Music Pipeline — 맥북 초기 세팅 (1회만 실행)
# ═══════════════════════════════════════════════════════════════
# 사용법:
#   1. 터미널 열기
#   2. chmod +x setup.sh
#   3. ./setup.sh
# ═══════════════════════════════════════════════════════════════

set -e
echo ""
echo "═══════════════════════════════════════════════"
echo "  🎵 Music Pipeline 설치 시작"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. Homebrew 확인 ───────────────────────────────────────────
if ! command -v brew &> /dev/null; then
    echo "📦 Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✅ Homebrew 이미 설치됨"
fi

# ── 2. Python 3 확인 ──────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "📦 Python 3 설치 중..."
    brew install python
else
    echo "✅ Python 3: $(python3 --version)"
fi

# ── 3. FFmpeg 설치 ────────────────────────────────────────────
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 FFmpeg 설치 중..."
    brew install ffmpeg
else
    echo "✅ FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
fi

# ── 4. 작업 디렉토리 생성 ─────────────────────────────────────
WORK="$HOME/music_pipeline"
mkdir -p "$WORK"/{outputs,logs,queue,sessions}
echo "✅ 작업 디렉토리: $WORK"

# ── 5. Python 가상환경 ────────────────────────────────────────
if [ ! -d "$WORK/venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv "$WORK/venv"
fi
source "$WORK/venv/bin/activate"

# ── 6. Python 패키지 설치 ─────────────────────────────────────
echo "📦 Python 패키지 설치 중..."
pip install --upgrade pip -q
pip install -q \
    playwright \
    flask \
    flask-cors \
    requests \
    python-dotenv \
    Pillow \
    numpy

# ── 7. Playwright 브라우저 설치 ───────────────────────────────
echo "📦 Playwright Chromium 설치 중..."
playwright install chromium

# ── 8. .env 파일 생성 (없는 경우) ─────────────────────────────
if [ ! -f "$WORK/.env" ]; then
    cat > "$WORK/.env" << 'ENVEOF'
# ═══════════════════════════════════════════════
# Music Pipeline 설정
# ═══════════════════════════════════════════════

# Telegram 알림 (선택)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 스케줄 시간 (24시간 형식) — 2번을 비우면 하루 1회
SCHEDULE_TIME_1=10:00
SCHEDULE_TIME_2=

# 큐가 비어 있으면 매일 다른 라틴 댄스 곡 자동 생성 (1=켜기, 0=끄기)
AUTO_LATIN_DAILY=1

# 영상 방식: techno(로컬 네온 루프, 기본) / gemini(DALL-E 이미지 + Gemini 영상)
VIDEO_MODE=techno
ENVEOF
    echo "⚠️  $WORK/.env 파일 생성됨 — Telegram 설정을 입력하세요"
fi

# ── 9. 완료 ───────────────────────────────────────────────────
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "확인불가")
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ 설치 완료!"
echo "═══════════════════════════════════════════════"
echo ""
echo "  다음 단계:"
echo ""
echo "  1️⃣  최초 로그인 (1회만):"
echo "     cd $WORK"
echo "     source venv/bin/activate"
echo "     python login_all.py"
echo ""
echo "  2️⃣  서버 시작:"
echo "     python server.py"
echo ""
echo "  3️⃣  iPhone에서 접속:"
echo "     http://${LOCAL_IP}:8080"
echo ""
echo "═══════════════════════════════════════════════"
