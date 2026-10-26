"""
browser_profile.py — 실제 Chrome + 전용 프로필 연결
====================================================
Google 계정 로그인(Suno 'Continue with Google', YouTube, Gemini)은
자동화 도구가 띄운 브라우저에서 차단될 수 있다.
그래서 로그인은 '일반 Chrome'으로 직접 하고, 자동화할 때만
Playwright가 원격 디버깅 포트(CDP)로 그 Chrome에 붙는다.

- 프로필 폴더: ~/music_pipeline/chrome_profile (평소 쓰는 Chrome 프로필과 분리)
- Google에 한 번 로그인하면 Suno·YouTube·Gemini가 같은 로그인을 공유

.env 설정 (선택, 비우면 OS별 기본 설치 경로를 자동 탐색):
    CHROME_PATH=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe
    CHROME_CDP_PORT=9222
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WORK_DIR = Path.home() / "music_pipeline"
PROFILE_DIR = WORK_DIR / "chrome_profile"
IS_WINDOWS = sys.platform == "win32"


def _default_chrome_candidates() -> list:
    if IS_WINDOWS:
        return [
            os.path.join(os.environ.get(v, ""), r"Google\Chrome\Application\chrome.exe")
            for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
            if os.environ.get(v)
        ]
    return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def chrome_path() -> str:
    if os.getenv("CHROME_PATH"):
        return os.getenv("CHROME_PATH")
    candidates = _default_chrome_candidates()
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


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


def close_chrome(proc: subprocess.Popen, timeout: int = 15):
    """Chrome을 정상 종료 (로그인 쿠키가 디스크에 저장되도록)."""
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        # /F 없이 → 창 닫기 신호(정상 종료). 이 Chrome 인스턴스만 대상
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()


def connect(playwright):
    """실행 중인 Chrome에 연결 (없으면 실행). 로그인 상태가 유지된 컨텍스트를 반환."""
    if not is_running():
        launch_chrome()
    browser = playwright.chromium.connect_over_cdp(cdp_url())
    return browser.contexts[0] if browser.contexts else browser.new_context()
