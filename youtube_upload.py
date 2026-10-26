"""
youtube_upload.py — 공식 YouTube Data API v3로 영상 업로드
============================================================
브라우저 자동화 없이 OAuth 리프레시 토큰으로 업로드한다.

필요한 환경 변수 (채팅에 붙여넣지 말고 환경 설정에 저장):
    YT_CLIENT_ID       OAuth 클라이언트 ID
    YT_CLIENT_SECRET   OAuth 클라이언트 보안 비밀번호
    YT_REFRESH_TOKEN   채널 업로드 권한이 있는 리프레시 토큰

API 프로젝트가 심사를 통과하기 전에는 공개로 올려도 비공개로 잠기므로
기본값은 private 이다.

사용법:
    python youtube_upload.py final.mp4 meta.json [--privacy private|unlisted|public]

meta.json 예시:
    {"title": "...", "description": "...", "tags": ["..."], "categoryId": "10"}
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK = 8 * 1024 * 1024
MUSIC_CATEGORY = "10"   # YouTube 카테고리 'Music'


def access_token() -> str:
    """리프레시 토큰으로 액세스 토큰 발급."""
    missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"환경 변수 없음: {', '.join(missing)}")
    resp = requests.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"토큰 발급 실패 ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["access_token"]


def upload(video_path: Path, meta: dict, privacy: str = "private") -> str:
    """재개 가능한(resumable) 업로드로 영상 업로드 후 영상 ID 반환."""
    token = access_token()
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta.get("description", "")[:5000],
            "tags": meta.get("tags", []),
            "categoryId": meta.get("categoryId", MUSIC_CATEGORY),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    size = video_path.stat().st_size

    # 1) 업로드 세션 생성
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        data=json.dumps(body),
        timeout=60,
    )
    if init.status_code != 200 or "Location" not in init.headers:
        raise RuntimeError(f"업로드 세션 생성 실패 ({init.status_code}): {init.text[:300]}")
    session_url = init.headers["Location"]

    # 2) 조각 단위 전송
    with open(video_path, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(CHUNK)
            end = offset + len(chunk) - 1
            resp = requests.put(
                session_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end}/{size}",
                },
                data=chunk,
                timeout=300,
            )
            if resp.status_code in (200, 201):
                video = resp.json()
                # 유튜브가 실제로 적용한 공개 범위 (미심사 API 프로젝트는 private으로 잠길 수 있음)
                actual = video.get("status", {}).get("privacyStatus")
                print(f"요청 공개 범위: {privacy} / 유튜브 적용 결과: {actual}")
                return video["id"]
            if resp.status_code != 308:
                raise RuntimeError(f"업로드 실패 ({resp.status_code}): {resp.text[:300]}")
            # 308: 서버가 받은 위치부터 이어서 전송
            received = resp.headers.get("Range")
            offset = int(received.split("-")[1]) + 1 if received else 0
            f.seek(offset)

    raise RuntimeError("업로드가 완료 응답 없이 끝남")


def main():
    parser = argparse.ArgumentParser(description="YouTube 업로드")
    parser.add_argument("video", type=Path)
    parser.add_argument("meta", type=Path)
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    video_id = upload(args.video, meta, args.privacy)
    print(f"업로드 완료: https://youtu.be/{video_id} ({args.privacy})")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
