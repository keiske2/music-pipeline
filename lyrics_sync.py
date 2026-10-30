"""
lyrics_sync.py — 노래 음성에서 가사 타이밍을 뽑아 화면 자막으로 만든다
=====================================================================
faster-whisper로 보컬을 받아쓰기(스페인어)해서 줄 단위 시간표를 만든다.
직접 쓴 가사(meta JSON의 "lyrics")를 힌트로 주면 철자가 그 가사에 가깝게 나온다.

- 본편(가로 영상): ASS 자막 파일 → techno_visual.compose_final(subtitles=...)
- 쇼츠(HyperFrames): compositions/lyrics.html 장면 파일

사용법:
    python lyrics_sync.py <음원.mp3> <출력.ass> [--meta meta/x.json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

MAX_CHARS = 38       # 한 줄 최대 글자 수 (넘으면 단어 경계에서 나눔)
MODEL = "small"


def transcribe(audio: Path, prompt: str = "", language: str = "es") -> list:
    """[{start, end, text}] 줄 목록. faster-whisper가 없으면 ImportError."""
    from faster_whisper import WhisperModel

    import numpy as np

    # faster-whisper 내장 디코더(PyAV)는 버전 궁합 문제가 있어 ffmpeg로 16kHz 모노 PCM을 직접 만든다
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0

    model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        samples,
        language=language,
        initial_prompt=prompt[:800] or None,
        word_timestamps=True,
        vad_filter=True,
    )
    lines = []
    for seg in segments:
        words = [w for w in (seg.words or []) if w.word.strip()]
        if not words:
            continue
        cur, start = "", words[0].start
        for i, w in enumerate(words):
            piece = w.word.strip()
            if cur and len(cur) + 1 + len(piece) > MAX_CHARS:
                lines.append({"start": start, "end": words[i - 1].end, "text": cur})
                cur, start = piece, w.start
            else:
                cur = f"{cur} {piece}".strip()
        lines.append({"start": start, "end": words[-1].end, "text": cur})
    # 너무 짧게 깜빡이지 않도록 최소 0.8초, 다음 줄과 겹치지 않게
    for a, b in zip(lines, lines[1:] + [None]):
        a["end"] = max(a["end"], a["start"] + 0.8)
        if b:
            a["end"] = min(a["end"], b["start"] - 0.05)
    return [l for l in lines if l["end"] > l["start"]]


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def to_ass(lines: list, out: Path, width: int = 1920, height: int = 1080, margin_v: int = 300):
    """네온 스타일 ASS 자막 (흰 글자 + 분홍 테두리 + 그림자)."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,DejaVu Sans,64,&H00FFFFFF,&H00FFFFFF,&H00D62BFF,&H8017020B,1,0,0,0,100,100,1,0,1,5,3,2,120,120,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for l in lines:
        text = l["text"].replace("{", "(").replace("}", ")")
        events.append(
            f"Dialogue: 0,{_ass_time(l['start'])},{_ass_time(l['end'])},Lyric,,0,0,0,,{{\\fad(120,120)}}{text}"
        )
    out.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out


def to_shorts_scene(lines: list, out: Path, clip_start: float, clip_len: float = 15.0):
    """쇼츠용 HyperFrames 장면. clip_start초부터 clip_len초 구간의 줄만, 시간은 0 기준으로."""
    items = []
    for i, l in enumerate(lines):
        s, e = l["start"] - clip_start, l["end"] - clip_start
        if e <= 0.1 or s >= clip_len - 0.1:
            continue
        s, e = max(0.0, s), min(clip_len, e)
        text = (l["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        items.append(
            f'      <div id="ly-{i}" class="ly-line clip" data-start="{s:.2f}" '
            f'data-duration="{e - s:.2f}"><span>{text}</span></div>'
        )
    out.write_text(
        """<template>
  <style>
    #root {
      position: absolute;
      inset: 0;
    }
    .ly-line {
      position: absolute;
      left: 60px;
      right: 60px;
      top: 1180px;
      text-align: center;
    }
    .ly-line span {
      display: inline-block;
      padding: 14px 28px;
      border-radius: 22px;
      background: rgba(11, 2, 23, 0.82);
      border: 3px solid #ff2bd6;
      font-family: "Oswald", sans-serif;
      font-size: 50px;
      line-height: 1.2;
      color: #ffffff;
      text-shadow: 0 0 12px rgba(255, 43, 214, 0.9);
    }
  </style>
  <div id="root" data-composition-id="lyrics" data-width="1080" data-height="1920">
"""
        + "\n".join(items)
        + "\n  </div>\n</template>\n",
        encoding="utf-8",
    )
    return len(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--meta", type=Path)
    parser.add_argument("--shorts-start", type=float, help="쇼츠 장면(.html)으로 출력, 원곡 기준 시작 초")
    parser.add_argument("--json", type=Path, help="줄 목록을 JSON으로도 저장")
    args = parser.parse_args()

    prompt = ""
    if args.meta and args.meta.exists():
        prompt = json.loads(args.meta.read_text(encoding="utf-8")).get("lyrics", "")
    lines = transcribe(args.audio, prompt)
    if args.json:
        args.json.write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.shorts_start is not None:
        n = to_shorts_scene(lines, args.out, args.shorts_start)
        print(f"쇼츠 가사 {n}줄 → {args.out}")
    else:
        to_ass(lines, args.out)
        print(f"가사 {len(lines)}줄 → {args.out}")


if __name__ == "__main__":
    try:
        main()
    except ImportError:
        print("❌ faster-whisper가 설치되지 않음: pip install faster-whisper", file=sys.stderr)
        sys.exit(1)
