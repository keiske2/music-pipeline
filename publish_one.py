"""
publish_one.py — 드라이브 곡 1개 → 테크노 영상 → 유튜브 업로드
================================================================
사용법:
    python publish_one.py <곡 이름 일부> [메타 JSON] [--privacy private]

예:
    python publish_one.py Una_mas_version_1 meta/una_mas.json
    python publish_one.py Una_mas_version_2            # 메타 JSON 없으면 자동 생성

업로드한 드라이브 파일 ID는 uploaded.json에 기록해 같은 곡을 두 번 올리지 않는다.
"""

import argparse
import json
import random
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import drive_fetch
import techno_visual
import youtube_upload
from latin_styles import PALETTES, VISUAL_PATTERNS

ROOT = Path(__file__).parent
WORK = ROOT / "work"
UPLOADED = ROOT / "uploaded.json"

HASHTAGS_TOP = "#LatinDance #줌바 #Zumba"
HASHTAGS_BOTTOM = ("#라틴음악 #라틴댄스 #LatinMusic #BailarLatino #LatinWorkout "
                   "#DanceFitness #홈트 #댄스다이어트")
TAGS = ["latin dance", "latin music", "zumba", "줌바", "라틴음악", "라틴댄스", "latin workout",
        "dance fitness", "baile latino", "bailar", "latin dance workout", "홈트", "댄스 다이어트",
        "latin party music"]


def load_uploaded() -> dict:
    return json.loads(UPLOADED.read_text(encoding="utf-8")) if UPLOADED.exists() else {}


def save_uploaded(uploaded: dict):
    UPLOADED.write_text(json.dumps(uploaded, ensure_ascii=False, indent=2), encoding="utf-8")


def make_meta(file_name: str) -> dict:
    """파일 이름으로 제목·설명·태그를 만든다. 예: Una_mas_version_2.mp3 → Una Mas (Ver. 2)"""
    stem = Path(file_name).stem
    version = re.search(r"_version_(\d+)$", stem, re.IGNORECASE)
    song = re.sub(r"_version_\d+$", "", stem, flags=re.IGNORECASE)
    song = re.sub(r"[_\-]+", " ", song).strip().title()
    tag = song.lower()
    if version and version.group(1) != "1":
        song = f"{song} (Ver. {version.group(1)})"

    title = f"{song} | Latin Dance Workout Music {datetime.now().year}"
    description = (
        f"{HASHTAGS_TOP}\n"
        f"{song} – 라틴 댄스 운동 음악 | Latin dance workout music to move, sweat and smile.\n"
        "따라 추기 좋은 라틴 리듬으로 운동과 홈트, 파티 분위기를 즐겨 보세요!\n\n"
        "🎧 Music created with Suno AI\n\n"
        f"{HASHTAGS_BOTTOM}"
    )
    return {"title": title[:100], "description": description,
            "tags": TAGS + [tag], "categoryId": "10"}


def find_meta(file_name: str) -> Path | None:
    """meta/*.json 중 제목 앞부분(| 앞)이 곡 파일 이름과 같은 것. 예: Fuego_en_la_Pista.mp3 ↔ "Fuego en la Pista | ..." """
    def norm(t: str) -> str:
        t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]", "", t)

    stem = norm(re.sub(r"_version_\d+$", "", Path(file_name).stem, flags=re.IGNORECASE))
    for p in sorted((ROOT / "meta").glob("*.json")):
        title = json.loads(p.read_text(encoding="utf-8")).get("title", "")
        if stem and norm(title.split("|")[0]) == stem:
            return p
    return None


def publish_song(song: dict, meta: dict, privacy: str = "private", bpm: float = 128) -> str:
    """드라이브 곡 1개를 영상으로 만들어 업로드하고 영상 URL을 반환."""
    uploaded = load_uploaded()
    if song["id"] in uploaded:
        raise RuntimeError(f"이미 업로드한 곡: {song['name']} → {uploaded[song['id']]}")
    print(f"곡: {song['folder']}/{song['name']}")

    job = WORK / Path(song["name"]).stem
    music = drive_fetch.download(song["id"], job / "music.mp3")

    pattern = random.choice(VISUAL_PATTERNS)
    palette = random.choice(PALETTES)
    print(f"영상 생성: {pattern} 패턴")
    loop = techno_visual.render_loop(job / "loop.mp4", pattern, palette, meta.get("bpm", bpm))
    subs = None
    try:
        import lyrics_sync
        print("가사 타이밍 추출 (faster-whisper)")
        lines = lyrics_sync.transcribe(music, meta.get("lyrics", ""))
        if lines:
            subs = lyrics_sync.to_ass(lines, job / "lyrics.ass")
            print(f"화면 가사 {len(lines)}줄")
    except Exception as e:  # 가사 실패해도 영상은 올린다
        print(f"⚠️ 가사 자막 생략: {e}")
    final = techno_visual.compose_final(loop, music, job / "final.mp4", palette, subs)

    video_id = youtube_upload.upload(final, meta, privacy)
    url = f"https://youtu.be/{video_id}"
    if privacy == "public":
        # 업로드 직후 유튜브가 비공개로 잠갔으면 공개로 다시 시도
        try:
            print(f"공개 범위 확인: {youtube_upload.set_privacy(video_id, 'public')}")
        except RuntimeError as e:
            print(f"⚠️ 공개 전환 실패 (업로드는 완료): {e}")
    uploaded[song["id"]] = url
    save_uploaded(uploaded)
    print(f"업로드 완료: {meta['title']} → {url} ({privacy})")
    return url


def main():
    parser = argparse.ArgumentParser(description="드라이브 곡 1개를 영상으로 만들어 업로드")
    parser.add_argument("name", help="곡 파일 이름 일부")
    parser.add_argument("meta", type=Path, nargs="?", help="제목·설명·태그 JSON (없으면 자동 생성)")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--bpm", type=float, default=128, help="영상 박자 펄스용 BPM")
    args = parser.parse_args()

    songs = [s for s in drive_fetch.list_songs() if args.name in s["name"]]
    if not songs:
        raise RuntimeError(f"드라이브 Suno 폴더에서 '{args.name}' 곡을 찾지 못함")
    song = songs[0]
    meta_path = args.meta or find_meta(song["name"])
    if meta_path:
        print(f"메타: {meta_path}")
    meta = (json.loads(meta_path.read_text(encoding="utf-8")) if meta_path
            else make_meta(song["name"]))
    publish_song(song, meta, args.privacy, args.bpm)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
