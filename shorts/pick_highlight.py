"""
pick_highlight.py — 곡에서 에너지가 가장 큰 구간을 골라 쇼츠용 음원으로 자른다
==============================================================================
사용법:
    python shorts/pick_highlight.py <원곡.mp3> <출력.mp3> [--seconds 15]

앞 15%·뒤 10%(인트로·아웃트로)는 건너뛰고, 0.5초 단위 음량(RMS)의 평균이
가장 큰 구간을 고른다. 페이드는 HyperFrames <audio>의 data-fade-in/out이 처리한다.
"""

import argparse
import subprocess
import sys

import numpy as np

RATE = 22050
STEP = 0.5


def loudest_window(path: str, seconds: float) -> float:
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    hop = int(RATE * STEP)
    n = len(samples) // hop
    if n * STEP < seconds:
        return 0.0
    rms = np.sqrt((samples[: n * hop].reshape(n, hop) ** 2).mean(axis=1))

    win = int(seconds / STEP)
    sums = np.convolve(rms, np.ones(win), mode="valid")       # 각 시작 위치의 구간 합
    first = int(n * 0.15)
    last = max(first, min(len(sums) - 1, int(n * 0.90) - win))
    best = first + int(np.argmax(sums[first : last + 1]))
    return best * STEP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dest")
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args()

    start = loudest_window(args.src, args.seconds)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", str(args.seconds),
         "-i", args.src, "-c:a", "libmp3lame", "-b:a", "192k", args.dest],
        check=True,
    )
    print(f"하이라이트 구간: {start:.1f}s ~ {start + args.seconds:.1f}s → {args.dest}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"❌ ffmpeg 실패: {e}", file=sys.stderr)
        sys.exit(1)
