"""
tempo_from_beats.py — `hyperframes beats` 결과로 assets/tempo.js 생성
사용법: python shorts/tempo_from_beats.py <beats.json> <tempo.js>
"""

import json
import statistics
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
times = [b["time"] for b in data.get("beats", [])]
if len(times) >= 4:
    period = statistics.median(b - a for a, b in zip(times, times[1:]))
else:
    period = 0.5
# 너무 빠른 박(살사 180BPM 이상 등)은 두 박에 한 번 움직이게
while period < 0.34:
    period *= 2
offset = (times[0] % period) if times else 0.0
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write(f"window.__tempo = {{ beat: {period:.3f}, offset: {offset:.3f} }};\n")
print(f"박 길이 {period:.3f}s (약 {60 / period:.0f} BPM 동작), 첫 박 {offset:.3f}s")
