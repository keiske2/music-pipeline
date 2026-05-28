"""
pipeline.py — 메인 자동화 엔진
================================
Playwright로 GPT Plus, Suno, Gemini, YouTube를 브라우저 자동화.
이미 결제된 웹 계정을 그대로 사용하므로 추가 비용 0원.

각 단계:
  1. ChatGPT → 가사 + 해시태그 + 이미지 프롬프트 생성
  2. Suno → 음악 생성 + MP3 다운로드
  3. ChatGPT DALL-E → 대표 이미지 생성 + 다운로드
  4. Gemini → 이미지로 8초 영상 생성 + 다운로드
  5. FFmpeg → 음악 + 영상 합성
  6. YouTube Studio → 자동 업로드
  7. Telegram → 완료 알림
"""

import json
import time
import subprocess
import logging
import re
import requests
import os
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, BrowserContext

logger = logging.getLogger("pipeline")

WORK_DIR = Path.home() / "music_pipeline"
SESSION_DIR = WORK_DIR / "sessions"
OUTPUT_DIR = WORK_DIR / "outputs"


# ═══════════════════════════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════════════════════════

def create_context(playwright, session_file: str) -> BrowserContext:
    """저장된 세션으로 브라우저 컨텍스트 생성."""
    session_path = SESSION_DIR / session_file
    browser = playwright.chromium.launch(headless=True)

    if session_path.exists():
        context = browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
    else:
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )

    return context


def wait_and_click(page: Page, selector: str, timeout: int = 15000):
    """요소가 나타나면 클릭."""
    page.wait_for_selector(selector, timeout=timeout)
    page.click(selector)


def wait_for_download(page: Page, action_fn, download_dir: Path, timeout: int = 120000) -> Path:
    """다운로드를 트리거하고 파일 경로를 반환."""
    with page.expect_download(timeout=timeout) as download_info:
        action_fn()
    download = download_info.value
    dest = download_dir / download.suggested_filename
    download.save_as(str(dest))
    return dest


# ═══════════════════════════════════════════════════════════════
# Step 1: ChatGPT — 가사 + 메타데이터 생성
# ═══════════════════════════════════════════════════════════════

def step1_chatgpt_generate(playwright, payload: dict, job_dir: Path) -> dict:
    """
    ChatGPT에 프롬프트를 보내서 가사, 해시태그, 이미지 프롬프트를 받아옴.
    """
    logger.info("Step 1: ChatGPT 가사 생성 중...")

    context = create_context(playwright, "chatgpt_session.json")
    page = context.new_page()

    try:
        # ChatGPT 새 대화 열기
        page.goto("https://chatgpt.com", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 프롬프트 구성
        core = payload["core"]
        details = payload.get("details", {})
        suno = payload.get("suno_params", {})

        prompt = f"""다음 조건으로 노래 관련 콘텐츠를 생성해줘. 반드시 아래 JSON 형식으로만 답변해:

조건:
- 키워드: {core.get('keyword', '')}
- 스타일: {core.get('style', '')}
- 보컬: {details.get('vocal_style', '자동')}
- BPM: {details.get('tempo_bpm', '자동')}
- 분위기: {details.get('mood', '')}
- 등장인물: {details.get('character', '')}
- 언어: {details.get('language', 'korean')}
- 악기: {details.get('instruments', '')}
- Weirdness: {suno.get('weirdness', 23)}%

JSON 형식:
{{
  "lyrics": "순수 가사만 (메타태그 제외, 줄바꿈으로 구분)",
  "lyrics_with_tags": "Suno용 가사 ([Verse], [Chorus] 등 포함)",
  "suno_style_prompt": "Suno 스타일 프롬프트 (영문)",
  "image_prompt": "DALL-E 이미지 프롬프트 (영문, 16:9, cinematic)",
  "title": "YouTube 영상 제목 (한국어)",
  "hashtags": ["#해시태그1", "#해시태그2"],
  "description_hashtags": "설명란용 해시태그 문자열"
}}"""

        # 입력창 찾기 & 입력
        input_selector = 'div[id="prompt-textarea"]'
        page.wait_for_selector(input_selector, timeout=15000)
        page.click(input_selector)
        page.keyboard.type(prompt, delay=5)

        # 전송
        page.keyboard.press("Enter")

        # 응답 대기 (GPT가 응답을 완료할 때까지)
        page.wait_for_timeout(5000)

        # 응답이 완료되었는지 확인 (전송 버튼이 다시 활성화될 때)
        for _ in range(60):  # 최대 5분 대기
            page.wait_for_timeout(5000)
            # 응답 완료 여부 체크: 새 메시지 입력이 가능한 상태
            try:
                is_ready = page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button[data-testid="send-button"]');
                        return btns.length > 0;
                    }
                """)
                if is_ready:
                    break
            except:
                continue

        # 마지막 응답 텍스트 추출
        response_text = page.evaluate("""
            () => {
                const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (msgs.length === 0) return '';
                return msgs[msgs.length - 1].innerText;
            }
        """)

        # JSON 파싱
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            raise RuntimeError("ChatGPT 응답에서 JSON을 찾을 수 없음")

        # 세션 저장
        context.storage_state(path=str(SESSION_DIR / "chatgpt_session.json"))

        # 결과 저장
        (job_dir / "gpt_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        logger.info(f"Step 1 완료: {result.get('title', 'N/A')}")
        return result

    finally:
        context.close()


# ═══════════════════════════════════════════════════════════════
# Step 2: Suno — 음악 생성
# ═══════════════════════════════════════════════════════════════

def step2_suno_generate(playwright, payload: dict, gpt_result: dict, job_dir: Path) -> Path:
    """
    Suno 웹에서 가사+스타일을 입력하고 음악을 생성, 다운로드.
    """
    logger.info("Step 2: Suno 음악 생성 중...")

    context = create_context(playwright, "suno_session.json")
    page = context.new_page()

    try:
        page.goto("https://suno.com/create", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Custom Mode 활성화 (가사 직접 입력)
        try:
            custom_btn = page.locator('text=Custom')
            if custom_btn.is_visible():
                custom_btn.click()
                page.wait_for_timeout(1000)
        except:
            pass

        # 가사 입력
        lyrics_input = page.locator('textarea').first
        if lyrics_input.is_visible():
            lyrics_input.fill(gpt_result["lyrics_with_tags"])
            page.wait_for_timeout(500)

        # 스타일 프롬프트 입력
        style_inputs = page.locator('input[placeholder*="Style"], input[placeholder*="style"], textarea').all()
        for inp in style_inputs:
            placeholder = inp.get_attribute("placeholder") or ""
            if "style" in placeholder.lower() or "genre" in placeholder.lower():
                inp.fill(gpt_result["suno_style_prompt"])
                break

        # 제목 입력
        title_inputs = page.locator('input[placeholder*="Title"], input[placeholder*="title"]').all()
        for inp in title_inputs:
            inp.fill(gpt_result["title"][:80])
            break

        page.wait_for_timeout(1000)

        # Create 버튼 클릭
        create_btn = page.locator('button:has-text("Create")')
        if create_btn.is_visible():
            create_btn.click()

        # 생성 완료 대기 (최대 5분)
        logger.info("  음악 생성 대기 중...")
        for attempt in range(60):
            page.wait_for_timeout(5000)
            # 생성 완료된 트랙이 있는지 확인
            try:
                download_btns = page.locator('[data-testid="download-button"], button:has-text("Download"), a[download]')
                if download_btns.count() > 0:
                    logger.info("  음악 생성 완료!")
                    break
            except:
                continue

        # 다운로드
        page.wait_for_timeout(2000)

        # 최신 트랙의 ... 메뉴 → Download 클릭
        music_path = job_dir / "music.mp3"

        # 방법 1: 직접 다운로드 버튼
        try:
            dl_btn = page.locator('button:has-text("Download")').first
            if dl_btn.is_visible():
                with page.expect_download(timeout=60000) as dl_info:
                    dl_btn.click()
                download = dl_info.value
                download.save_as(str(music_path))
        except:
            # 방법 2: 오디오 소스에서 직접 다운로드
            audio_url = page.evaluate("""
                () => {
                    const audio = document.querySelector('audio source, audio');
                    return audio ? (audio.src || audio.querySelector('source')?.src) : null;
                }
            """)
            if audio_url:
                import urllib.request
                urllib.request.urlretrieve(audio_url, str(music_path))

        context.storage_state(path=str(SESSION_DIR / "suno_session.json"))
        logger.info(f"Step 2 완료: {music_path}")
        return music_path

    finally:
        context.close()


# ═══════════════════════════════════════════════════════════════
# Step 3: ChatGPT DALL-E — 이미지 생성
# ═══════════════════════════════════════════════════════════════

def step3_generate_image(playwright, gpt_result: dict, job_dir: Path) -> Path:
    """
    ChatGPT에서 DALL-E로 이미지를 생성하고 다운로드.
    """
    logger.info("Step 3: DALL-E 이미지 생성 중...")

    context = create_context(playwright, "chatgpt_session.json")
    page = context.new_page()

    try:
        page.goto("https://chatgpt.com", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        prompt = f"이 프롬프트로 이미지를 생성해줘: {gpt_result['image_prompt']}"

        input_selector = 'div[id="prompt-textarea"]'
        page.wait_for_selector(input_selector, timeout=15000)
        page.click(input_selector)
        page.keyboard.type(prompt, delay=5)
        page.keyboard.press("Enter")

        # 이미지 생성 대기 (최대 3분)
        logger.info("  이미지 생성 대기 중...")
        image_url = None
        for _ in range(36):
            page.wait_for_timeout(5000)
            image_url = page.evaluate("""
                () => {
                    const imgs = document.querySelectorAll('[data-message-author-role="assistant"] img');
                    for (const img of imgs) {
                        if (img.src && img.src.startsWith('http') && !img.src.includes('avatar')) {
                            return img.src;
                        }
                    }
                    return null;
                }
            """)
            if image_url:
                break

        image_path = job_dir / "cover_image.png"

        if image_url:
            import urllib.request
            urllib.request.urlretrieve(image_url, str(image_path))
            logger.info(f"Step 3 완료: {image_path}")
        else:
            raise RuntimeError("이미지 생성 실패")

        context.storage_state(path=str(SESSION_DIR / "chatgpt_session.json"))
        return image_path

    finally:
        context.close()


# ═══════════════════════════════════════════════════════════════
# Step 4: Gemini — 이미지 → 8초 영상
# ═══════════════════════════════════════════════════════════════

def step4_gemini_video(playwright, gpt_result: dict, image_path: Path, job_dir: Path) -> Path:
    """
    Gemini에 이미지를 업로드하고 8초 영상 생성을 요청.
    """
    logger.info("Step 4: Gemini 영상 생성 중...")

    context = create_context(playwright, "gemini_session.json")
    page = context.new_page()

    try:
        page.goto("https://gemini.google.com", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 이미지 업로드
        # 파일 입력 찾기
        file_input = page.locator('input[type="file"]').first
        if file_input.is_visible() or file_input.count() > 0:
            file_input.set_input_files(str(image_path))
            page.wait_for_timeout(2000)

        # 영상 생성 프롬프트 입력
        prompt = (
            "이 이미지를 기반으로 8초짜리 생동감 넘치는 부메랑 스타일 영상을 만들어줘. "
            "카메라가 천천히 움직이고, 입자 효과와 빛의 변화가 있는 시네마틱한 느낌으로. "
            "음악 비디오 썸네일이 살아 움직이는 것 같은 느낌으로 만들어줘."
        )

        input_area = page.locator('[contenteditable="true"], textarea').first
        if input_area.is_visible():
            input_area.fill(prompt)
            page.wait_for_timeout(500)

        # 전송
        page.keyboard.press("Enter")

        # 영상 생성 대기 (최대 5분)
        logger.info("  영상 생성 대기 중...")
        video_url = None
        for _ in range(60):
            page.wait_for_timeout(5000)
            video_url = page.evaluate("""
                () => {
                    const videos = document.querySelectorAll('video source, video');
                    for (const v of videos) {
                        const src = v.src || v.querySelector('source')?.src;
                        if (src && src.startsWith('http')) return src;
                    }
                    // blob URL인 경우
                    const blobs = document.querySelectorAll('video');
                    for (const v of blobs) {
                        if (v.src && v.src.startsWith('blob:')) return 'blob';
                    }
                    return null;
                }
            """)
            if video_url:
                break

        video_path = job_dir / "boomerang.mp4"

        if video_url and video_url != 'blob':
            import urllib.request
            urllib.request.urlretrieve(video_url, str(video_path))
        elif video_url == 'blob':
            # blob URL인 경우: 다운로드 버튼 찾기
            try:
                dl_btn = page.locator('button:has-text("Download"), button[aria-label*="download"]').first
                if dl_btn.is_visible():
                    with page.expect_download(timeout=60000) as dl_info:
                        dl_btn.click()
                    download = dl_info.value
                    download.save_as(str(video_path))
            except Exception as e:
                logger.warning(f"  영상 다운로드 실패: {e}")
                raise RuntimeError("Gemini 영상 다운로드 실패")
        else:
            raise RuntimeError("Gemini 영상 생성 실패")

        context.storage_state(path=str(SESSION_DIR / "gemini_session.json"))
        logger.info(f"Step 4 완료: {video_path}")
        return video_path

    finally:
        context.close()


# ═══════════════════════════════════════════════════════════════
# Step 5: FFmpeg — 음악 + 영상 합성
# ═══════════════════════════════════════════════════════════════

def step5_ffmpeg_merge(music_path: Path, video_path: Path, job_dir: Path) -> Path:
    """FFmpeg로 음악과 영상을 합성. 영상을 음악 길이만큼 루프."""
    logger.info("Step 5: FFmpeg 영상 합성 중...")

    # 음악 길이 확인
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(music_path)],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    logger.info(f"  음악 길이: {duration:.1f}초")

    # YouTube용 (16:9)
    final_path = job_dir / "final.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(video_path),
        "-i", str(music_path),
        "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(final_path),
    ], check=True, capture_output=True)

    logger.info(f"Step 5 완료: {final_path}")
    return final_path


# ═══════════════════════════════════════════════════════════════
# Step 6: YouTube — 자동 업로드
# ═══════════════════════════════════════════════════════════════

def step6_youtube_upload(
    playwright, gpt_result: dict, video_path: Path, image_path: Path, job_dir: Path
) -> str:
    """YouTube Studio에서 Playwright로 영상 업로드."""
    logger.info("Step 6: YouTube 업로드 중...")

    context = create_context(playwright, "youtube_session.json")
    page = context.new_page()

    try:
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 업로드 버튼 클릭
        upload_btn = page.locator('#upload-icon, button:has-text("만들기"), button:has-text("Create")')
        if upload_btn.is_visible():
            upload_btn.click()
            page.wait_for_timeout(1000)

        # "동영상 업로드" 선택
        upload_video = page.locator('text=동영상 업로드, text=Upload videos, tp-yt-paper-item:has-text("Upload")')
        if upload_video.first.is_visible():
            upload_video.first.click()
            page.wait_for_timeout(2000)

        # 파일 선택
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(video_path))
        page.wait_for_timeout(5000)

        # 제목 입력
        title = gpt_result["title"]
        top_tags = " ".join(gpt_result.get("hashtags", [])[:3])
        full_title = f"{title} {top_tags}"[:100]

        title_input = page.locator('#textbox[aria-label*="제목"], #textbox[aria-label*="Title"]').first
        if title_input.is_visible():
            title_input.fill("")
            page.wait_for_timeout(300)
            title_input.fill(full_title)

        # 설명란 입력: 순수 가사 + 해시태그 배치
        lyrics = gpt_result["lyrics"]
        hashtags = gpt_result.get("hashtags", [])
        desc_hashtags = gpt_result.get("description_hashtags", "")

        # 가사 사이에 해시태그 배치
        lines = lyrics.strip().split("\n")
        desc_parts = []
        tag_idx = 0
        for i, line in enumerate(lines):
            desc_parts.append(line)
            if (i + 1) % 4 == 0 and tag_idx < len(hashtags):
                desc_parts.append(f"\n{' '.join(hashtags[tag_idx:tag_idx+2])}\n")
                tag_idx += 2

        if tag_idx < len(hashtags):
            desc_parts.append(f"\n{' '.join(hashtags[tag_idx:])}")

        description = "\n".join(desc_parts)

        desc_input = page.locator('#textbox[aria-label*="설명"], #textbox[aria-label*="Description"]').first
        if desc_input.is_visible():
            desc_input.fill(description)

        page.wait_for_timeout(2000)

        # "아니요, 어린이용이 아닙니다" 선택
        not_for_kids = page.locator('tp-yt-paper-radio-button:has-text("아니요"), tp-yt-paper-radio-button:has-text("No")')
        if not_for_kids.first.is_visible():
            not_for_kids.first.click()

        # "다음" 버튼 3번 클릭 (세부정보 → 동영상 요소 → 검토 → 공개)
        for step in range(3):
            page.wait_for_timeout(1500)
            next_btn = page.locator('#next-button, button:has-text("다음"), button:has-text("Next")')
            if next_btn.is_visible():
                next_btn.click()

        page.wait_for_timeout(2000)

        # 공개 설정
        public_radio = page.locator('tp-yt-paper-radio-button:has-text("공개"), tp-yt-paper-radio-button:has-text("Public")')
        if public_radio.first.is_visible():
            public_radio.first.click()

        page.wait_for_timeout(1000)

        # 게시 버튼 클릭
        publish_btn = page.locator('#done-button, button:has-text("게시"), button:has-text("Publish")')
        if publish_btn.is_visible():
            publish_btn.click()

        # 업로드 완료 대기
        page.wait_for_timeout(5000)

        # 영상 URL 추출
        video_url = ""
        try:
            link = page.locator('a[href*="youtu"]').first
            if link.is_visible():
                video_url = link.get_attribute("href")
        except:
            video_url = "업로드 완료 (URL 확인 필요)"

        context.storage_state(path=str(SESSION_DIR / "youtube_session.json"))
        logger.info(f"Step 6 완료: {video_url}")
        return video_url

    finally:
        context.close()


# ═══════════════════════════════════════════════════════════════
# Step 7: Telegram 알림
# ═══════════════════════════════════════════════════════════════

def step7_telegram_notify(
    job_id: str, gpt_result: dict, youtube_url: str,
    image_path: Path = None, error: str = None
):
    """텔레그램으로 결과 알림."""
    from dotenv import load_dotenv
    load_dotenv(WORK_DIR / ".env")

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.info("Telegram 미설정 — 알림 건너뜀")
        return

    if error:
        text = f"❌ 파이프라인 실패\n작업: {job_id}\n오류: {error}"
    else:
        text = (
            f"✅ 발행 완료!\n"
            f"🎵 {gpt_result.get('title', '')}\n"
            f"▶ {youtube_url}\n"
            f"🏷 {gpt_result.get('description_hashtags', '')}\n"
            f"⏰ {datetime.now().strftime('%H:%M')}"
        )

    try:
        if image_path and image_path.exists() and not error:
            with open(image_path, "rb") as photo:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text},
                    files={"photo": photo}, timeout=30,
                )
        else:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": text}, timeout=30,
            )
    except Exception as e:
        logger.error(f"Telegram 알림 실패: {e}")


# ═══════════════════════════════════════════════════════════════
# 메인 파이프라인 실행
# ═══════════════════════════════════════════════════════════════

def run_pipeline(payload: dict):
    """전체 파이프라인을 순차 실행."""
    job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2)
    )

    gpt_result = {}
    youtube_url = ""
    image_path = None

    with sync_playwright() as playwright:
        try:
            # Step 1: GPT 가사 생성
            gpt_result = step1_chatgpt_generate(playwright, payload, job_dir)

            # Step 2: Suno 음악 생성
            music_path = step2_suno_generate(playwright, payload, gpt_result, job_dir)

            # Step 3: DALL-E 이미지 생성
            image_path = step3_generate_image(playwright, gpt_result, job_dir)

            # Step 4: Gemini 영상 생성
            video_path = step4_gemini_video(playwright, gpt_result, image_path, job_dir)

            # Step 5: FFmpeg 합성
            final_path = step5_ffmpeg_merge(music_path, video_path, job_dir)

            # Step 6: YouTube 업로드
            youtube_url = step6_youtube_upload(
                playwright, gpt_result, final_path, image_path, job_dir
            )

            # Step 7: Telegram 알림
            step7_telegram_notify(job_id, gpt_result, youtube_url, image_path)

            logger.info(f"═══ 파이프라인 완료: {job_id} ═══")

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"파이프라인 실패: {error_msg}")
            logger.error(traceback.format_exc())
            step7_telegram_notify(job_id, gpt_result, "", image_path, error=error_msg)
