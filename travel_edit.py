"""
travel_edit.py — 드라이브 여행 폴더(영상·사진·bgm.mp3) → 한 편의 여행 영상 → 유튜브 업로드
==========================================================================================
드라이브 구조:  Chile/<날짜>_<도시>/  (영상 mp4·mov, 사진 jpg·heic·png, 배경음악 bgm.mp3)

편집 규칙 (사람 대신 정해 둔 기준):
  - 영상·사진을 찍은 시간 순서로 배치 (영상: 메타데이터 creation_time, 사진: EXIF 촬영 시각)
  - 영상은 앞뒤 흔들리는 0.6초를 자르고 최대 MAX_CLIP초까지, 사진은 PHOTO_SEC초씩 천천히 확대
  - 세로 영상·사진은 흐린 배경 위에 가운데 배치 (1920×1080)
  - 원래 소리는 살리고(바람 소리 줄이는 저역 차단), 현장 소리가 클 때만 배경음악이 자동으로 작아짐
  - 배경음악은 영상 길이만큼 반복, 처음 한 바퀴에는 노래 가사 자막
  - travel/captions/<폴더이름>.json 이 있으면 장면 설명 자막 ({"파일이름": "Cerro Dragón", ...})
  - 맨 앞 4초에 도시 이름 제목

사용법:
    python travel_edit.py frames <폴더이름 일부>              # 장면 분석용 대표 화면 모음 (sheets/)
    python travel_edit.py build  <폴더이름 일부> [--privacy public] [--title "..."] [--no-upload]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import drive_fetch
import youtube_upload

ROOT = Path(__file__).parent
W, H, FPS = 1920, 1080, 30
MAX_CLIP = 20.0      # 영상 한 개에서 쓰는 최대 길이(초) — 긴 버전
TRIM = 0.6           # 영상 앞뒤에서 버리는 길이(초)
PHOTO_SEC = 4.0      # 사진 한 장 기본 길이(초)
PHOTO_MAX = 18.0     # 자료가 적어 노래를 채워야 할 때 사진 한 장 최대 길이(초)
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def run(cmd: list):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(cmd[:6])} …\n{r.stderr[-800:]}")
    return r.stdout


def probe(path: Path) -> dict:
    return json.loads(run(["ffprobe", "-v", "quiet", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)]))


def city_name(folder: str) -> str:
    """'2026-11-16_Iquique' → 'Iquique'"""
    return re.sub(r"^\d{4}-\d{2}-\d{2}[_ -]*", "", folder).replace("_", " ").strip() or folder


# ── 받기·정렬 ──────────────────────────────────────────────────────────────────

def fetch(name: str, work: Path):
    folder = drive_fetch.find_folder(name)
    print(f"폴더: {folder['name']}")
    media, bgm, seen = [], None, set()
    for f in drive_fetch.list_children(folder["id"]):
        ext = Path(f["name"]).suffix.lower()
        if f["name"] in seen:   # 같은 파일을 여러 번 올린 경우 한 번만 사용
            continue
        seen.add(f["name"])
        if f["name"].lower() == "bgm.mp3" or (ext == ".mp3" and bgm is None):
            bgm = drive_fetch.download(f["id"], work / "bgm.mp3")
        elif ext in VIDEO_EXT or ext in PHOTO_EXT:
            dest = drive_fetch.download(f["id"], work / "src" / f["name"])
            media.append({"path": dest, "name": f["name"], "kind": "video" if ext in VIDEO_EXT else "photo",
                          "drive_time": f.get("createdTime", "")})
    if not media:
        raise RuntimeError("폴더에 영상·사진이 없음")
    print(f"영상 {sum(m['kind'] == 'video' for m in media)}개, 사진 {sum(m['kind'] == 'photo' for m in media)}장, "
          f"배경음악 {'있음' if bgm else '없음'}")
    return folder["name"], media, bgm


def shot_time(m: dict) -> str:
    """찍은 시각(ISO 문자열). 못 읽으면 드라이브에 올린 시각."""
    try:
        if m["kind"] == "video":
            t = probe(m["path"]).get("format", {}).get("tags", {}).get("creation_time")
            if t:
                return t
        else:
            from PIL import Image
            import pillow_heif
            pillow_heif.register_heif_opener()
            with Image.open(m["path"]) as im:
                exif = im.getexif()
                t = exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if t:
                return datetime.strptime(t, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return m["drive_time"]


# ── 조각 만들기 ────────────────────────────────────────────────────────────────

def photo_frame(src: Path, out: Path) -> Path:
    """사진을 흐린 배경 + 가운데 원본의 3840×2160 이미지로 (확대 효과 때 계단 현상 줄이려 2배 크기)."""
    from PIL import Image, ImageFilter, ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener()
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        big = (W * 2, H * 2)
        bg = ImageOps.fit(im, big).filter(ImageFilter.GaussianBlur(40))
        fg = ImageOps.contain(im, big)
        bg.paste(fg, ((big[0] - fg.width) // 2, (big[1] - fg.height) // 2))
        bg.save(out, quality=92)
    return out


def photo_clip(m: dict, out: Path, i: int, sec: float = PHOTO_SEC) -> float:
    img = photo_frame(m["path"], out.with_suffix(".jpg"))
    frames = int(sec * FPS)
    zoom_in = i % 2 == 0   # 번갈아 확대/축소
    rate = 0.15 / frames   # 길이와 상관없이 끝까지 천천히 1.15배 확대(또는 축소)
    z = f"min(1+{rate:.6f}*on,1.15)" if zoom_in else f"max(1.15-{rate:.6f}*on,1)"
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex",
         f"[0:v]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
         f"fade=in:d=0.4,fade=out:st={sec - 0.4:.2f}:d=0.4,setsar=1[v]",
         "-map", "[v]", "-map", "1:a", "-t", f"{sec:.2f}", *ENC, str(out)])
    return sec


def usable_len(m: dict) -> float:
    return float(probe(m["path"])["format"].get("duration", 0)) - 2 * TRIM


def video_clip(m: dict, out: Path, dur: float | None = None) -> float:
    info = probe(m["path"])
    length = float(info["format"].get("duration", 0))
    usable = length - 2 * TRIM
    if usable < 1.5:
        return 0.0
    dur = min(usable, dur or MAX_CLIP)
    start = TRIM + (usable - dur) / 2           # 가운데 구간
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:4[bg];"
          f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS},setsar=1,"
          f"fade=in:d=0.4,fade=out:st={dur - 0.4:.2f}:d=0.4[v]")
    if has_audio:
        af = f";[0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=120,afade=in:d=0.4,afade=out:st={dur - 0.4:.2f}:d=0.4[a]"
        inputs, amap = [], "[a]"
    else:
        af, inputs, amap = "", ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"], "1:a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(m["path"]),
         *inputs, "-filter_complex", vf + af, "-map", "[v]", "-map", amap, "-t", f"{dur:.2f}", *ENC, str(out)])
    return dur


def plan_durations(media: list, target: float) -> list:
    """조각마다 쓸 길이. 전체가 target(배경음악 길이)에 맞도록 늘리거나 줄인다.
    영상은 실제 길이·MAX_CLIP을, 사진은 2.5~8초를 넘지 않는다."""
    lo = {"video": 2.0, "photo": 2.5}
    hi = [min(usable_len(m), MAX_CLIP) if m["kind"] == "video" else PHOTO_MAX for m in media]
    base = [min(h, MAX_CLIP if m["kind"] == "video" else PHOTO_SEC) for m, h in zip(media, hi)]
    durs = base[:]
    for _ in range(6):   # 상한·하한에 걸린 조각을 빼고 나머지로 다시 나눠 맞춤
        total = sum(durs)
        if abs(total - target) < 0.5:
            break
        free = [i for i, d in enumerate(durs)
                if (total < target and d < hi[i] - 0.01) or (total > target and d > lo[media[i]["kind"]] + 0.01)]
        if not free:
            break
        f = (target - (total - sum(durs[i] for i in free))) / sum(durs[i] for i in free)
        for i in free:
            durs[i] = max(lo[media[i]["kind"]], min(hi[i], durs[i] * f))
    return durs


# ── 자막 ───────────────────────────────────────────────────────────────────────

def ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(out: Path, title: str, captions: list, lyrics: list):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,DejaVu Sans,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,4,0,1,4,4,5,60,60,0,1
Style: Place,DejaVu Sans,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,2,0,1,3,2,7,70,70,60,1
Style: Lyric,DejaVu Sans,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,1,0,0,100,100,1,0,1,3,2,2,120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    clean = lambda s: s.replace("{", "(").replace("}", ")")
    ev = [f"Dialogue: 1,{ass_time(0.3)},{ass_time(4.3)},Title,,0,0,0,,{{\\fad(600,600)}}{clean(title)}"]
    for start, end, text in captions:
        ev.append(f"Dialogue: 0,{ass_time(start + 0.3)},{ass_time(min(end, start + 5))},Place,,0,0,0,,{{\\fad(300,300)}}{clean(text)}")
    for l in lyrics:
        ev.append(f"Dialogue: 0,{ass_time(l['start'])},{ass_time(l['end'])},Lyric,,0,0,0,,{{\\fad(150,150)}}{clean(l['text'])}")
    out.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return out


# ── 명령 ───────────────────────────────────────────────────────────────────────

def cmd_frames(name: str):
    """장면마다 대표 화면을 뽑아 파일 이름과 함께 모음 이미지로 저장 (Claude가 보고 장면 설명을 씀)."""
    from PIL import Image, ImageDraw, ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener()
    work = ROOT / "work" / "travel"
    folder, media, _ = fetch(name, work)
    thumbs = []
    for m in media:
        t = work / "thumbs" / (m["name"] + ".jpg")
        t.parent.mkdir(parents=True, exist_ok=True)
        if m["kind"] == "video":
            d = float(probe(m["path"])["format"].get("duration", 2))
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{d / 2:.2f}", "-i", str(m["path"]),
                 "-frames:v", "1", "-vf", "scale=480:-2", str(t)])
        else:
            with Image.open(m["path"]) as im:
                ImageOps.exif_transpose(im).convert("RGB").save(t)
        thumbs.append((m["name"], t))
    out_dir = ROOT / "sheets" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    cell, cols = (480, 300), 4
    for n in range(0, len(thumbs), 12):
        part = thumbs[n:n + 12]
        rows = (len(part) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell[0], rows * (cell[1] + 30)), "black")
        d = ImageDraw.Draw(sheet)
        for i, (fname, t) in enumerate(part):
            x, y = i % cols * cell[0], i // cols * (cell[1] + 30)
            with Image.open(t) as im:
                sheet.paste(ImageOps.contain(im, cell), (x, y))
            d.text((x + 6, y + cell[1] + 6), fname[:60], fill="white")
        sheet.save(out_dir / f"sheet_{n // 12 + 1:02d}.jpg", quality=85)
    print(f"대표 화면 {len(thumbs)}개 → {out_dir}")


def cmd_build(name: str, privacy: str, title: str, upload: bool, lyrics_hint: str):
    work = ROOT / "work" / "travel"
    folder, media, bgm = fetch(name, work)
    if not bgm:
        raise RuntimeError("배경음악(bgm.mp3)이 폴더에 없음")
    city = city_name(folder)
    title = title or f"{city}, Chile"
    for m in media:
        m["time"] = shot_time(m)
    media.sort(key=lambda m: (m["time"], m["name"]))

    # 편집 계획: travel/captions/<폴더>.json  {"order": [파일이름…], "captions": {파일이름: 글}}
    # (예전 형식 {파일이름: 글} 도 읽음). order에 없는 파일은 촬영 시간순으로 뒤에 붙인다.
    cap_file = ROOT / "travel" / "captions" / f"{folder}.json"
    plan = json.loads(cap_file.read_text(encoding="utf-8")) if cap_file.exists() else {}
    if "order" not in plan and "captions" not in plan:
        plan = {"captions": plan}
    cap_map = plan.get("captions", {})
    rank = {n: i for i, n in enumerate(plan.get("order", []))}
    skip = set(plan.get("skip", []))
    media = [m for m in media if m["name"] not in skip]
    media.sort(key=lambda m: (rank.get(m["name"], len(rank)), m["time"], m["name"]))

    for m in media:
        if m["kind"] == "video" and usable_len(m) < 1.5:
            m["drop"] = True
    media = [m for m in media if not m.get("drop")]
    music_len = float(probe(bgm)["format"]["duration"])
    durs = plan_durations(media, music_len)
    print(f"배경음악 {music_len / 60:.1f}분에 맞춤 (조각 {len(media)}개)")

    parts, captions, t = [], [], 0.0
    for i, (m, want) in enumerate(zip(media, durs)):
        out = work / "parts" / f"{i:04d}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            dur = video_clip(m, out, want) if m["kind"] == "video" else photo_clip(m, out, i, want)
        except RuntimeError as e:
            print(f"⚠️ 건너뜀 {m['name']}: {str(e)[:200]}")
            continue
        if dur <= 0:
            continue
        if m["name"] in cap_map:
            captions.append((t, t + dur, cap_map[m["name"]]))
        parts.append(out)
        t += dur
        print(f"  {m['kind']:5s} {dur:5.1f}s  {m['name']}")
    if not parts:
        raise RuntimeError("쓸 수 있는 영상·사진이 없음")
    total = t
    print(f"총 길이 {total / 60:.1f}분, 조각 {len(parts)}개")

    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    joined = work / "joined.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])

    # 노래 가사 자막 (배경음악 첫 바퀴)
    lyrics = []
    try:
        import lyrics_sync
        lyrics = lyrics_sync.transcribe(bgm, lyrics_hint, "es")
        lyrics = [l for l in lyrics if l["end"] <= total]
        print(f"가사 자막 {len(lyrics)}줄")
    except Exception as e:
        print(f"⚠️ 가사 자막 생략: {e}")
    ass = write_ass(work / "subs.ass", title, captions, lyrics)

    # 배경음악 반복 + 현장 소리가 클 때 음악 자동 줄임 + 끝 페이드
    final = work / "final.mp4"
    fade_st = max(total - 5, 0)
    sub_path = str(ass).replace(":", "\\:")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(bgm),
         "-filter_complex",
         f"[0:v]subtitles='{sub_path}',fade=out:st={fade_st:.2f}:d=4[v];"
         f"[0:a]asplit=2[orig][sc];"
         f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.85,atrim=0:{total:.2f}[m];"
         f"[m][sc]sidechaincompress=threshold=0.04:ratio=6:attack=80:release=900[md];"
         f"[md][orig]amix=inputs=2:normalize=0,afade=out:st={fade_st:.2f}:d=5[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-movflags", "+faststart",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", str(final)])
    print(f"완성: {final} ({final.stat().st_size / 1e6:.0f}MB)")
    if not upload:
        return None

    meta = {
        "title": f"{title} | Travel Film 2026"[:100],
        "description": (f"#Chile #{city.replace(' ', '')} #칠레여행\n"
                        f"{city}, Chile 여행 영상 | Travel film of {city}, Chile.\n"
                        "직접 찍은 영상과 사진에 수노(Suno)로 만든 배경음악을 입혔습니다.\n\n"
                        "🎧 Music created with Suno AI\n\n"
                        f"#칠레 #남미여행 #여행브이로그 #TravelChile #SouthAmerica #{city.replace(' ', '')}Chile #TravelFilm"),
        "tags": ["chile", "chile travel", city.lower(), f"{city.lower()} chile", "칠레", "칠레 여행",
                 "남미 여행", "여행 브이로그", "travel film", "south america travel"],
        "categoryId": "19",   # 여행 및 이벤트
    }
    video_id = youtube_upload.upload(final, meta, privacy)
    url = f"https://youtu.be/{video_id}"
    if privacy == "public":
        print(f"공개 범위 확인: {youtube_upload.set_privacy(video_id, 'public')}")
    result = youtube_upload.verify(video_id, privacy, timeout=1800)
    print(f"업로드 완료: {meta['title']} → {url}")
    print(f"검수 통과: {result['privacy']}, 길이 {result['duration']}")
    rec = ROOT / "travel_uploaded.json"
    data = json.loads(rec.read_text(encoding="utf-8")) if rec.exists() else {}
    data[folder] = url
    rec.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return url


def main():
    ap = argparse.ArgumentParser(description="여행 영상 편집·업로드")
    ap.add_argument("mode", choices=["frames", "build"])
    ap.add_argument("folder", help="드라이브 폴더 이름 일부 (예: Iquique)")
    ap.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    ap.add_argument("--title", default="")
    ap.add_argument("--lyrics", type=Path, help="가사 힌트 파일 (travel/<도시>.md)")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    if a.mode == "frames":
        cmd_frames(a.folder)
    else:
        hint = ""
        if a.lyrics and a.lyrics.exists():
            m = re.search(r"\*\*Lyrics\*\*:\s*```\n(.*?)```", a.lyrics.read_text(encoding="utf-8"), re.S)
            hint = re.sub(r"\[.*?\]", "", m.group(1)) if m else ""
        cmd_build(a.folder, a.privacy, a.title, not a.no_upload, hint)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
