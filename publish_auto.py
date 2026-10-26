"""
publish_auto.py — 아직 안 올린 드라이브 곡 중 가장 오래된 1곡을 자동 업로드
============================================================================
GitHub Actions 예약 실행(하루 3번)에서 쓴다. 새 곡이 없으면 아무것도 하지 않고 끝난다.

사용법:
    python publish_auto.py [--privacy private]
"""

import argparse
import sys

import drive_fetch
from publish_one import load_uploaded, make_meta, publish_song


def main():
    parser = argparse.ArgumentParser(description="새 곡 1개 자동 업로드")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    uploaded = load_uploaded()
    pending = [s for s in drive_fetch.list_songs() if s["id"] not in uploaded]
    if not pending:
        print("새로 올릴 곡이 없음 — 종료")
        return

    song = min(pending, key=lambda s: s["createdTime"])   # 오래된 곡부터
    print(f"대기 중인 곡 {len(pending)}개 중 1곡 업로드")
    publish_song(song, make_meta(song["name"]), args.privacy)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
