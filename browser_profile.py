"""
browser_profile.py — 실제 Chrome + 전용 프로필 연결
====================================================
Google 계정 로그인(Suno 'Continue with Google', YouTube, Gemini)은
자동화 도구가 띄운 브라우저에서 차단될 수 있다.
그래서 로그인은 '일반 Chrome'으로 직접 하고, 자동화할 때만
Playwright가 원격 디버깅 포트(CDP)로 그 Chrome에 붙는다.

- 프로필 폴더: ~/music_pipeline/chrome_profile (평소 쓰는 Chrome 프로필과 분리)
- Google에 한 번 로그인하면 Suno·YouTube·Gemini가 같은 로그인을 공유

.env 설정 (선택):
    CHROME_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
    CHROME_CDP_PORT=9222
"""

import os
import subprocess
import time
import urllib.request
from pathlib import Path

WORK_DIR = Path.home() / "music_pipeline"
PROFILE_DIR = WORK_DIR / "chrome_profile"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def chrome_path() -> str:
    return os.getenv("CHROME_PATH", DEFAULT_CHROME)


def cdp_port() -> int:
    return int(os.getenv("CHROME_CDP_PORT", "9222"))


def cdp_url() -> str:
    return f"http://127.0.0.1:{cdp_port()}"


def is_running() -> bool:
    """원격 디버깅 포트로 Chrome이 응답하는지 확인."""
    try:
        with urllib.request.urlopen(f"{cdp_url()}/json/version", timeout=2):
            return True
    except OSError:
        return False


def launch_chrome(urls=(), debug: bool = True) -> subprocess.Popen:
    """
    전용 프로필로 일반 Chrome 실행.
    debug=False: 로그인 전용 (자동화 포트 없이 완전한 일반 브라우저)
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        chrome_path(),
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if debug:
        args += [f"--remote-debugging-port={cdp_port()}",
                 "--remote-debugging-address=127.0.0.1"]
    args += list(urls)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if debug:
        for _ in range(60):
            if is_running():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"Chrome 원격 디버깅 포트({cdp_port()}) 연결 실패")
    return proc


def connect(playwright):
    """실행 중인 Chrome에 연결 (없으면 실행). 로그인 상태가 유지된 컨텍스트를 반환."""
    if not is_running():
        launch_chrome()
    browser = playwright.chromium.connect_over_cdp(cdp_url())
    return browser.contexts[0] if browser.contexts else browser.new_context()
