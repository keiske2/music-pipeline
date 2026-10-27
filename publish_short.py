"""
publish_short.py — HyperFrames 쇼츠용 음원 가져오기 + 완성 영상 업로드
======================================================================
사용법:
    python publish_short.py fetch <곡 이름 일부> <저장 경로>
    python publish_short.py upload <영상.mp4> <곡 제목>      # 공개 쇼츠로 업로드
"""

import sys
from pathlib import Path

import drive_fetch
import youtube_upload
from publish_one import HASHTAGS_BOTTOM, TAGS


def fetch(name: str, dest: Path):
    songs = [s for s in drive_fetch.list_songs() if name in s["name"]]
    if not songs:
        raise RuntimeError(f"드라이브 Suno 폴더에서 '{name}' 곡을 찾지 못함")
    print(f"곡: {songs[0]['folder']}/{songs[0]['name']}")
    drive_fetch.download(songs[0]["id"], dest)


def upload(video: Path, title: str):
    meta = {
        "title": f"{title} 💃 #Shorts | Latin Dance Workout"[:100],
        "description": (
            "#Shorts #LatinDance #줌바\n"
            f"{title} – 전체 곡은 채널에서 들어보세요! Full song on the channel.\n"
            "🎧 Music created with Suno AI\n\n"
            f"{HASHTAGS_BOTTOM}"
        ),
        "tags": TAGS + ["shorts", title.lower()],
        "categoryId": "10",
    }
    video_id = youtube_upload.upload(video, meta, "public")
    print(f"쇼츠 업로드 완료: https://youtube.com/shorts/{video_id}")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "fetch":
            fetch(sys.argv[2], Path(sys.argv[3]))
        elif len(sys.argv) == 4 and sys.argv[1] == "upload":
            upload(Path(sys.argv[2]), sys.argv[3])
        else:
            print(__doc__)
            sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
