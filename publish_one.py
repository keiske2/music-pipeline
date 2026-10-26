"""
publish_one.py — 드라이브 곡 1개 → 테크노 영상 → 유튜브 업로드
================================================================
사용법:
    python publish_one.py <곡 이름 일부> <메타 JSON> [--privacy private]

예:
    python publish_one.py Una_mas_version_1 meta/una_mas.json

업로드한 드라이브 파일 ID는 uploaded.json에 기록해 같은 곡을 두 번 올리지 않는다.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import drive_fetch
import techno_visual
import youtube_upload
from latin_styles import PALETTES, VISUAL_PATTERNS

WORK = Path(__file__).parent / "work"
UPLOADED = Path(__file__).parent / "uploaded.json"


def main():
    parser = argparse.ArgumentParser(description="드라이브 곡 1개를 영상으로 만들어 업로드")
    parser.add_argument("name", help="곡 파일 이름 일부")
    parser.add_argument("meta", type=Path, help="제목·설명·태그 JSON")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--bpm", type=float, default=128, help="영상 박자 펄스용 BPM")
    args = parser.parse_args()

    uploaded = json.loads(UPLOADED.read_text(encoding="utf-8")) if UPLOADED.exists() else {}

    songs = [s for s in drive_fetch.list_songs() if args.name in s["name"]]
    if not songs:
        raise RuntimeError(f"드라이브 Suno 폴더에서 '{args.name}' 곡을 찾지 못함")
    song = songs[0]
    if song["id"] in uploaded:
        raise RuntimeError(f"이미 업로드한 곡: {song['name']} → {uploaded[song['id']]}")
    print(f"곡: {song['folder']}/{song['name']}")

    job = WORK / Path(song["name"]).stem
    music = drive_fetch.download(song["id"], job / "music.mp3")

    pattern = random.choice(VISUAL_PATTERNS)
    palette = random.choice(PALETTES)
    print(f"영상 생성: {pattern} 패턴")
    loop = techno_visual.render_loop(job / "loop.mp4", pattern, palette, args.bpm)
    final = techno_visual.compose_final(loop, music, job / "final.mp4", palette)

    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    video_id = youtube_upload.upload(final, meta, args.privacy)
    url = f"https://youtu.be/{video_id}"

    uploaded[song["id"]] = url
    UPLOADED.write_text(json.dumps(uploaded, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"업로드 완료: {url} ({args.privacy})")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
