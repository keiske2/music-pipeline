"""
drive_fetch.py — 구글 드라이브에서 수노 음원 가져오기
======================================================
youtube_upload.py와 같은 OAuth 리프레시 토큰을 쓴다
(토큰에 drive.readonly 범위가 포함되어 있어야 함).

드라이브 구조:  내 드라이브/Suno/<날짜 폴더>/<곡>.mp3

사용법:
    python drive_fetch.py list                 # Suno 폴더의 mp3 목록
    python drive_fetch.py get <파일ID> <저장경로>
"""

import sys
from pathlib import Path

import requests

from youtube_upload import access_token

API = "https://www.googleapis.com/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"


def _query(token: str, q: str, fields: str = "files(id,name,mimeType,createdTime,parents)") -> list:
    files, page = [], None
    while True:
        params = {"q": q, "fields": f"nextPageToken,{fields}", "pageSize": 100,
                  "orderBy": "createdTime desc"}
        if page:
            params["pageToken"] = page
        resp = requests.get(API, headers={"Authorization": f"Bearer {token}"},
                            params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"드라이브 조회 실패 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        files += data.get("files", [])
        page = data.get("nextPageToken")
        if not page:
            return files


def list_songs(root_name: str = "Suno") -> list:
    """Suno 폴더 아래 날짜 폴더들의 mp3를 최신순으로 반환."""
    token = access_token()
    roots = _query(token, f"name = '{root_name}' and mimeType = '{FOLDER_MIME}' and trashed = false")
    if not roots:
        raise RuntimeError(f"드라이브에 '{root_name}' 폴더가 없음")
    songs = []
    for root in roots:
        for day in _query(token, f"'{root['id']}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"):
            for f in _query(token, f"'{day['id']}' in parents and mimeType = 'audio/mpeg' and trashed = false"):
                songs.append({**f, "folder": day["name"]})
    return sorted(songs, key=lambda s: s["createdTime"], reverse=True)


def find_video(name: str) -> dict:
    """드라이브 전체에서 이름에 name이 들어간 영상 파일 1개 (최신순)."""
    token = access_token()
    safe = name.replace("'", "\\'")
    files = _query(token, f"name contains '{safe}' and mimeType contains 'video/' and trashed = false")
    if not files:
        raise RuntimeError(f"드라이브에서 '{name}' 영상 파일을 찾지 못함")
    return files[0]


def download(file_id: str, dest: Path) -> Path:
    token = access_token()
    with requests.get(f"{API}/{file_id}", params={"alt": "media"},
                      headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=120) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"다운로드 실패 ({resp.status_code}): {resp.text[:300]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                f.write(chunk)
    return dest


if __name__ == "__main__":
    try:
        if len(sys.argv) >= 2 and sys.argv[1] == "list":
            for s in list_songs():
                print(f"{s['folder']}  {s['name']}  ({s['id']})")
        elif len(sys.argv) == 4 and sys.argv[1] == "get":
            print(f"저장: {download(sys.argv[2], Path(sys.argv[3]))}")
        else:
            print(__doc__)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
