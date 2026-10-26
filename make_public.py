"""
make_public.py — uploaded.json에 기록된 영상을 모두 공개(public)로 전환
=======================================================================
토큰에 https://www.googleapis.com/auth/youtube 범위가 있어야 한다.

사용법:
    python make_public.py
"""

import json
import sys
from pathlib import Path

from youtube_upload import set_privacy

UPLOADED = Path(__file__).parent / "uploaded.json"


def main():
    uploaded = json.loads(UPLOADED.read_text(encoding="utf-8")) if UPLOADED.exists() else {}
    failed = 0
    for url in uploaded.values():
        video_id = url.rsplit("/", 1)[-1]
        try:
            print(f"{url} → {set_privacy(video_id, 'public')}")
        except RuntimeError as e:
            failed += 1
            print(f"❌ {url}: {e}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
