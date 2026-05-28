"""
login_all.py — 최초 1회 로그인 스크립트
========================================
각 서비스에 브라우저를 열어서 직접 로그인합니다.
로그인 세션이 sessions/ 폴더에 저장되어 이후 자동으로 재사용됩니다.

사용법:
    python login_all.py
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
import time

WORK_DIR = Path.home() / "music_pipeline"
SESSION_DIR = WORK_DIR / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

SERVICES = [
    {
        "name": "ChatGPT",
        "url": "https://chatgpt.com",
        "session_file": "chatgpt_session.json",
    },
    {
        "name": "Suno",
        "url": "https://suno.com",
        "session_file": "suno_session.json",
    },
    {
        "name": "Gemini",
        "url": "https://gemini.google.com",
        "session_file": "gemini_session.json",
    },
    {
        "name": "YouTube Studio",
        "url": "https://studio.youtube.com",
        "session_file": "youtube_session.json",
    },
]


def login_service(service: dict):
    """서비스에 로그인하고 세션을 저장합니다."""
    name = service["name"]
    session_path = SESSION_DIR / service["session_file"]

    print(f"\n{'='*50}")
    print(f"  {name} 로그인")
    print(f"{'='*50}")
    print(f"  브라우저가 열리면 직접 로그인하세요.")
    print(f"  로그인 완료 후 터미널에서 Enter를 누르세요.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        page = context.new_page()
        page.goto(service["url"], wait_until="domcontentloaded")

        input(f"  ➡️  {name}에 로그인한 후 Enter를 누르세요... ")

        # 세션 저장
        context.storage_state(path=str(session_path))
        print(f"  ✅ {name} 세션 저장 완료: {session_path}")

        browser.close()


def main():
    print()
    print("═══════════════════════════════════════════════")
    print("  🔐 서비스 로그인 (최초 1회)")
    print("═══════════════════════════════════════════════")
    print()
    print("  4개 서비스에 순서대로 로그인합니다.")
    print("  각 서비스 브라우저가 열리면 직접 로그인하고,")
    print("  완료 후 터미널에서 Enter를 누르세요.")
    print()

    for service in SERVICES:
        login_service(service)

    print()
    print("═══════════════════════════════════════════════")
    print("  ✅ 모든 서비스 로그인 완료!")
    print("═══════════════════════════════════════════════")
    print()
    print("  이제 서버를 시작하세요:")
    print("    python server.py")
    print()


if __name__ == "__main__":
    main()
