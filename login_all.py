"""
login_all.py — 최초 1회 로그인 스크립트
========================================
전용 프로필로 '일반 Chrome'을 열어 직접 로그인합니다.
자동화 도구가 붙지 않은 상태라 Google 로그인이 차단되지 않습니다.
로그인 정보는 ~/music_pipeline/chrome_profile 에 남아 이후 자동으로 재사용됩니다.

  - Google 계정 1번 로그인 → YouTube Studio, Gemini 자동 로그인
  - Suno: 'Sign in' → 'Continue with Google' → 같은 Google 계정 선택
  - ChatGPT: 평소 로그인 방식대로

사용법:
    python login_all.py
"""

import os
import sys

from dotenv import load_dotenv

import browser_profile

load_dotenv(browser_profile.WORK_DIR / ".env")

SERVICES = [
    ("Google 계정", "https://accounts.google.com"),
    ("Suno (Continue with Google)", "https://suno.com"),
    ("ChatGPT", "https://chatgpt.com"),
    ("YouTube Studio", "https://studio.youtube.com"),
    ("Gemini (VIDEO_MODE=gemini일 때만 필요)", "https://gemini.google.com"),
]


def main():
    print()
    print("═══════════════════════════════════════════════")
    print("  🔐 서비스 로그인 (최초 1회)")
    print("═══════════════════════════════════════════════")

    if not os.path.exists(browser_profile.chrome_path()):
        print(f"\n  ❌ Chrome을 찾을 수 없습니다: {browser_profile.chrome_path()}")
        print("     Google Chrome을 설치하거나 .env에 CHROME_PATH를 지정하세요.")
        sys.exit(1)

    if browser_profile.is_running():
        print("\n  ⚠️  파이프라인용 Chrome이 이미 실행 중입니다.")
        print("     그 Chrome 창을 모두 닫은 뒤(Cmd+Q) 다시 실행하세요.")
        sys.exit(1)

    print()
    print("  Chrome 창에 아래 탭들이 열립니다. 순서대로 로그인하세요:")
    for i, (name, url) in enumerate(SERVICES, 1):
        print(f"   {i}. {name}  —  {url}")
    print()
    print("  ※ 'Google 계정' 탭에서 먼저 로그인하면 나머지가 쉬워집니다.")
    print()

    proc = browser_profile.launch_chrome([url for _, url in SERVICES], debug=False)

    print("  로그인을 모두 마쳤으면 Chrome을 Cmd+Q로 완전히 종료하세요.")
    print("  (정상 종료해야 로그인 정보가 프로필에 확실히 저장됩니다)")
    input("  ➡️  Chrome 종료 후 Enter를 누르세요... ")

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except Exception:
        proc.kill()

    print()
    print("═══════════════════════════════════════════════")
    print("  ✅ 로그인 완료! (프로필: chrome_profile)")
    print("═══════════════════════════════════════════════")
    print()
    print("  이제 서버를 시작하세요:")
    print("    python server.py")
    print()


if __name__ == "__main__":
    main()
