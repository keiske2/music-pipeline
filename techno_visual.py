"""
techno_visual.py — 테크노 스타일 반복 영상 생성
================================================
외부 서비스 없이 numpy + FFmpeg로 '끊김 없이 반복되는' 네온 루프 영상을 만들고,
음악에 맞춰 반응하는 파형을 덧씌워 최종 영상을 합성한다.

모든 움직임은 루프 길이(LOOP_SEC)의 정수 배 주기로 설계되어
마지막 프레임 → 첫 프레임이 자연스럽게 이어진다.

패턴:
  grid   — 지평선을 향해 달리는 네온 그리드 바닥 + 박자에 맞춰 뛰는 링
  tunnel — 회전하며 빨려 들어가는 네온 터널
  plasma — 간섭 무늬 등고선 (홀로그램 느낌)

사용법 (테스트):
    python techno_visual.py grid out.mp4
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

LOOP_SEC = 8
FPS = 30
RENDER_W, RENDER_H = 960, 540   # 렌더 해상도 (출력 시 1920x1080으로 업스케일)


def _glow(dist: np.ndarray, width: float) -> np.ndarray:
    """선까지의 거리 → 네온 발광 세기 (선명한 코어 + 퍼지는 빛)."""
    core = np.exp(-(dist / width) ** 2)
    halo = 0.35 * np.exp(-(dist / (width * 4)) ** 2)
    return core + halo


def _frac_dist(v: np.ndarray) -> np.ndarray:
    """가장 가까운 정수까지의 거리 (0~0.5)."""
    return np.abs(v - np.round(v))


def _beats_per_loop(bpm: float) -> int:
    """루프 안에 정수 개의 박자가 들어가도록 반올림."""
    return max(1, int(round(bpm * LOOP_SEC / 60)))


class Renderer:
    def __init__(self, pattern: str, palette, bpm: float):
        self.pattern = pattern
        self.c1 = np.array(palette[0], dtype=np.float32) / 255
        self.c2 = np.array(palette[1], dtype=np.float32) / 255
        self.beats = _beats_per_loop(bpm)

        ys, xs = np.mgrid[0:RENDER_H, 0:RENDER_W].astype(np.float32)
        self.nx = (xs - RENDER_W / 2) / (RENDER_H / 2)   # 세로 기준 정규화 좌표
        self.ny = (ys - RENDER_H / 2) / (RENDER_H / 2)

        # 공통 오버레이: 스캔라인 + 비네팅
        scan = 0.85 + 0.15 * (np.sin(ys * np.pi / 2) ** 2)
        vignette = np.clip(1.15 - 0.22 * (self.nx ** 2 + self.ny ** 2), 0, 1)
        self.overlay = (scan * vignette)[..., None]

        # 배경 그라데이션
        bg_top = np.array([0.02, 0.0, 0.06], dtype=np.float32)
        bg_bot = np.array([0.0, 0.01, 0.03], dtype=np.float32)
        t = ((self.ny + 1) / 2)[..., None]
        self.bg = bg_top * (1 - t) + bg_bot * t

    def pulse(self, phase: float) -> float:
        """박자 펄스 (0~1, 박자 시작에 최대)."""
        p = (phase * self.beats) % 1.0
        return float(np.exp(-p * 6))

    def frame(self, phase: float) -> np.ndarray:
        """phase: 0 이상 1 미만, 루프 내 위치."""
        a, b = getattr(self, f"_{self.pattern}")(phase)
        img = self.bg + a[..., None] * self.c1 + b[..., None] * self.c2
        img = np.clip(img * self.overlay, 0, 1)
        return (img * 255).astype(np.uint8)

    # ── 패턴들 ────────────────────────────────────────────────
    def _grid(self, phase):
        nx, ny = self.nx, self.ny
        horizon = -0.05
        below = ny > horizon
        depth = 1.0 / np.maximum(ny - horizon, 1e-3)

        # 바닥 그리드: 루프당 정확히 4칸 전진 → 이음매 없음
        z = depth * 0.6 + phase * 4
        x = nx * depth * 0.6
        fade = np.clip((ny - horizon) * 3, 0, 1)
        lines = (_glow(_frac_dist(z), 0.04) * np.clip(1 / depth * 2, 0, 1)
                 + _glow(_frac_dist(x) / np.maximum(depth, 1), 0.012))
        floor = np.where(below, lines * fade, 0)

        # 하늘: 박자에 맞춰 퍼지는 링 + 수평선 글로우
        pulse = self.pulse(phase)
        cy = horizon - 0.35
        r = np.sqrt(nx ** 2 + (ny - cy) ** 2)
        ring = _glow(np.abs(r - (0.28 + 0.06 * pulse)), 0.012) * (0.6 + 0.8 * pulse)
        ring2 = _glow(np.abs(r - (0.28 + 0.25 * ((phase * self.beats) % 1.0))), 0.01) \
            * (1 - (phase * self.beats) % 1.0) * 0.6
        sky = np.where(below, 0, ring + ring2)
        horizon_glow = _glow(np.abs(ny - horizon), 0.015) * (0.7 + 0.5 * pulse)

        return floor * 0.9 + horizon_glow * 0.5, sky + horizon_glow * 0.6

    def _tunnel(self, phase):
        nx, ny = self.nx, self.ny
        r = np.sqrt(nx ** 2 + ny ** 2) + 1e-3
        theta = np.arctan2(ny, nx) / (2 * np.pi)   # -0.5~0.5
        depth = 0.5 / r

        # 루프당 링 6칸 전진, 스포크(12개)는 1칸 회전 → 이음매 없음
        rings = _glow(_frac_dist(depth * 2 - phase * 6), 0.05)
        spokes = _glow(_frac_dist(theta * 12 + phase), 0.03 * r + 0.004)
        fade = np.clip(r * 1.6, 0, 1)
        pulse = self.pulse(phase)
        center = _glow(r, 0.08) * (0.4 + 0.8 * pulse)
        return rings * fade * (0.7 + 0.4 * pulse), spokes * fade * 0.7 + center

    def _plasma(self, phase):
        nx, ny = self.nx, self.ny
        tau = 2 * np.pi * phase
        # 각 항의 시간 주파수가 정수 → 루프 끝에서 원래 상태로 복귀
        v = (np.sin(nx * 4.0 + tau)
             + np.sin(ny * 5.0 - 2 * tau)
             + np.sin((nx + ny) * 3.0 + tau)
             + np.sin(np.sqrt(nx ** 2 + ny ** 2) * 8.0 - 3 * tau))
        pulse = self.pulse(phase)
        contour_a = _glow(_frac_dist(v * 1.5), 0.05)
        contour_b = _glow(_frac_dist(v * 1.5 + 0.5), 0.03)
        return contour_a * (0.6 + 0.5 * pulse), contour_b * 0.5


def render_loop(out_path: Path, pattern: str = "grid",
                palette=((255, 40, 180), (0, 230, 255)), bpm: float = 128) -> Path:
    """LOOP_SEC 길이의 무한 반복용 1920x1080 영상을 생성."""
    renderer = Renderer(pattern, palette, bpm)
    n_frames = LOOP_SEC * FPS

    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{RENDER_W}x{RENDER_H}", "-r", str(FPS), "-i", "-",
        "-vf", "scale=1920:1080:flags=bicubic,gblur=sigma=0.6",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ], stdin=subprocess.PIPE)

    try:
        for i in range(n_frames):
            proc.stdin.write(renderer.frame(i / n_frames).tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("루프 영상 인코딩 실패")
    return out_path


def compose_final(loop_path: Path, music_path: Path, out_path: Path,
                  palette=((255, 40, 180), (0, 230, 255)), subtitles: Path | None = None) -> Path:
    """루프 영상을 음악 길이만큼 반복 + 음악 반응형 네온 파형을 합성. subtitles(ASS)가 있으면 가사를 입힌다."""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(music_path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(probe.stdout.strip())
    wave_color = "0x{:02X}{:02X}{:02X}".format(*palette[1])

    # 파형(검정 배경)을 화면 하단에 놓고 screen 블렌드 → 검정은 투명처럼 보임
    filter_complex = (
        f"[1:a]showwaves=s=1920x260:mode=cline:rate={FPS}:colors={wave_color}:scale=sqrt,"
        f"format=gbrp,pad=1920:1080:0:800:black[wave];"
        f"[0:v]fps={FPS},format=gbrp[bg];"
        # YUV에서 screen 블렌드하면 색이 틀어지므로 반드시 RGB(gbrp)에서 블렌드
        f"[bg][wave]blend=all_mode=screen"
    )
    if subtitles:
        path = str(subtitles).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        filter_complex += f",subtitles='{path}'"
    filter_complex += ",format=yuv420p[v]"

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(loop_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ], check=True)
    return out_path


def extract_cover(video_path: Path, out_path: Path, at_sec: float = 1.0) -> Path:
    """영상에서 한 프레임을 뽑아 대표 이미지로 저장."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(at_sec), "-i", str(video_path),
        "-frames:v", "1", str(out_path),
    ], check=True)
    return out_path


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "grid"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else f"loop_{pattern}.mp4")
    render_loop(out, pattern)
    print(f"생성 완료: {out}")
