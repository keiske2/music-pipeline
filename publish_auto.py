"""
publish_auto.py — 아직 안 올린 드라이브 곡 중 가장 오래된 1곡을 자동 업로드
============================================================================
GitHub Actions 예약 실행(토·일 1곡씩)에서 쓴다. 새 곡이 없으면 아무것도 하지 않고 끝난다.

사용법:
    python publish_auto.py [--privacy private]
"""

import argparse
import sys

import drive_fetch
from publish_one import find_bg_video, find_meta, load_meta, load_uploaded, make_meta, publish_song


def main():
    parser = argparse.ArgumentParser(description="새 곡 1개 자동 업로드")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    uploaded = load_uploaded()
    pending = [s for s in drive_fetch.list_songs() if s["id"] not in uploaded]
    if not pending:
        # 알림을 받도록 실패로 끝낸다 (GitHub가 실패 메일을 보냄)
        raise RuntimeError("이번 주말에 올릴 새 곡이 드라이브 Suno 폴더에 없음 — 곡을 넣어 주세요")

    song = min(pending, key=lambda s: s["createdTime"])   # 오래된 곡부터
    print(f"대기 중인 곡 {len(pending)}개 중 1곡 업로드")
    meta_path = find_meta(song["name"])
    meta = load_meta(meta_path, song["name"]) if meta_path else make_meta(song["name"])
    bg = find_bg_video(song["name"])
    publish_song(song, meta, args.privacy, bg_video=bg)
    if not bg:
        # 업로드는 됐지만 제미나이 영상이 없어 테크노 영상으로 올렸음을 알림
        raise RuntimeError(f"업로드는 완료, 단 드라이브에 '{song['name'].rsplit('.', 1)[0]}' 영상이 없어 테크노 영상으로 올림")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
