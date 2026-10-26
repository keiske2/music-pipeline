"""
latin_styles.py — 줌바용 라틴 음악 스타일 로테이션
=================================================
매일 다른 라틴 장르/분위기/보컬/악기 조합을 골라 파이프라인 payload를 만든다.

- 장르 카탈로그(STYLES)를 한 바퀴 다 돌기 전에는 같은 장르를 다시 고르지 않는다.
- 보컬·분위기·테마·영상 패턴까지 함께 바꿔서 매번 색다른 결과가 나오게 한다.
- 사용 기록은 WORK_DIR/style_history.json 에 저장 (업로드 성공 시 기록).

BPM 값은 사실 데이터가 아니라 Suno 프롬프트에 넣을 '목표 설정값'이다.
채널 운영하면서 자유롭게 조정하면 된다.

사용법:
    python latin_styles.py            # 다음에 나올 payload 미리보기 (기록 안 함)
"""

import json
import random
from datetime import datetime
from pathlib import Path

WORK_DIR = Path.home() / "music_pipeline"
HISTORY_FILE = WORK_DIR / "style_history.json"

# ═══════════════════════════════════════════════════════════════
# 장르 카탈로그
# ═══════════════════════════════════════════════════════════════
# bpm: 프롬프트용 목표 범위 (조정 가능)
# lang: 가사 언어 후보
STYLES = [
    {
        "id": "salsa",
        "name": "Salsa",
        "tags": "salsa dura, fitness dance, piano montuno, brass section, clave",
        "bpm": (180, 200),
        "instruments": "piano montuno, trumpets, trombones, congas, timbales, bongos, bass tumbao",
        "lang": ["spanish"],
    },
    {
        "id": "merengue",
        "name": "Merengue",
        "tags": "merengue, high energy dance, tambora, güira, accordion",
        "bpm": (130, 160),
        "instruments": "tambora, güira, accordion, saxophones, bass",
        "lang": ["spanish"],
    },
    {
        "id": "cumbia",
        "name": "Cumbia",
        "tags": "cumbia, festive latin dance, accordion, guacharaca",
        "bpm": (95, 110),
        "instruments": "accordion, guacharaca, caja vallenata, bass, gaita flute",
        "lang": ["spanish"],
    },
    {
        "id": "reggaeton",
        "name": "Reggaeton",
        "tags": "reggaeton, dembow beat, latin urban, fitness anthem",
        "bpm": (90, 100),
        "instruments": "dembow drums, 808 bass, synth plucks, vocal chops",
        "lang": ["spanish", "spanglish"],
    },
    {
        "id": "bachata",
        "name": "Bachata (upbeat)",
        "tags": "modern bachata, upbeat, requinto guitar, bongo",
        "bpm": (125, 140),
        "instruments": "requinto guitar, rhythm guitar, bongos, güira, bass",
        "lang": ["spanish"],
    },
    {
        "id": "samba",
        "name": "Samba",
        "tags": "samba batucada, carnival, brazilian percussion, whistle",
        "bpm": (100, 115),
        "instruments": "surdo, repinique, tamborim, agogô, cavaquinho, apito whistle",
        "lang": ["portuguese"],
    },
    {
        "id": "axe",
        "name": "Axé",
        "tags": "axé music, bahia carnival, brazilian pop, horns",
        "bpm": (120, 135),
        "instruments": "timbau, surdo, electric guitar, horns, synth",
        "lang": ["portuguese"],
    },
    {
        "id": "dembow",
        "name": "Dominican Dembow",
        "tags": "dominican dembow, aggressive dance, fast dembow riddim",
        "bpm": (115, 125),
        "instruments": "dembow drums, sub bass, synth stabs, chant vocals",
        "lang": ["spanish"],
    },
    {
        "id": "chacha",
        "name": "Cha-cha-chá",
        "tags": "cha cha cha, latin ballroom groove, güiro, flute",
        "bpm": (115, 125),
        "instruments": "güiro, flute, violins, piano, congas, timbales",
        "lang": ["spanish"],
    },
    {
        "id": "mambo",
        "name": "Mambo",
        "tags": "mambo, big band latin, powerful brass riffs",
        "bpm": (180, 200),
        "instruments": "trumpets, saxophones, piano, congas, timbales, upright bass",
        "lang": ["spanish"],
    },
    {
        "id": "soca",
        "name": "Soca",
        "tags": "soca, caribbean carnival, power soca, steelpan",
        "bpm": (150, 160),
        "instruments": "steelpan, soca drums, horns, synth bass",
        "lang": ["english", "spanglish"],
    },
    {
        "id": "moombahton",
        "name": "Moombahton",
        "tags": "moombahton, latin EDM, dutch house meets reggaeton",
        "bpm": (105, 110),
        "instruments": "reggaeton drums, big synth leads, latin percussion, risers",
        "lang": ["spanish", "spanglish"],
    },
    {
        "id": "latinhouse",
        "name": "Latin House",
        "tags": "latin house, tech house, four on the floor, latin percussion",
        "bpm": (124, 128),
        "instruments": "four-on-the-floor kick, congas, timbales, piano stabs, bassline",
        "lang": ["spanish"],
    },
    {
        "id": "guaracha",
        "name": "Guaracha (Aleteo)",
        "tags": "guaracha aleteo, colombian electronic, tribal percussion",
        "bpm": (128, 135),
        "instruments": "tribal drums, cowbell, latin percussion loops, synth stabs",
        "lang": ["spanish"],
    },
    {
        "id": "champeta",
        "name": "Champeta",
        "tags": "champeta, afro-colombian, soukous guitar, picó sound",
        "bpm": (110, 125),
        "instruments": "soukous guitar, electronic percussion, bass, synth",
        "lang": ["spanish"],
    },
    {
        "id": "tribal",
        "name": "Tribal Guarachero",
        "tags": "tribal guarachero, mexican tribal, pre-hispanic flutes, cumbia rhythm",
        "bpm": (130, 140),
        "instruments": "pre-hispanic flutes, tribal drums, cumbia bass, synth",
        "lang": ["spanish"],
    },
]

VOCALS = [
    "energetic male lead vocal with crowd chants",
    "powerful female lead vocal with call-and-response chorus",
    "male & female duet",
    "group chant vocals (coro), shout-outs like 'vamos!'",
    "mostly instrumental with short vocal hooks",
]

MOODS = [
    "sunny beach party", "neon night club", "carnival street parade",
    "sweaty fiesta peak", "playful and flirty", "triumphant and empowering",
    "tropical sunrise warm-up", "fiery and intense",
]

THEMES = [
    "fiesta bajo el sol", "mueve la cintura", "fuego en la pista",
    "noche de carnaval", "baila sin parar", "corazón tropical",
    "sudor y alegría", "la ola latina", "ritmo de la ciudad",
    "verano eterno", "energía total", "brillo de neón",
]

# 줌바 수업용 곡 구조 (짧고 반복적인 훅, 동작 전환이 쉬운 8카운트 단위)
STRUCTURE = (
    "Intro (8 counts x4) → Verse → Pre-Chorus build → Big Chorus with simple chant hook → "
    "Percussion break → Verse 2 → Chorus → Breakdown (clap along) → Final Chorus → Outro. "
    "Clear 8-count phrasing, steady tempo, no tempo changes, 3-4 minutes."
)

VISUAL_PATTERNS = ["grid", "tunnel", "plasma"]

# 팔레트 (메인 네온색, 보조 네온색) — RGB 0~255
PALETTES = [
    ((255, 40, 180), (0, 230, 255)),   # 핑크 / 시안
    ((255, 140, 0), (255, 0, 90)),     # 오렌지 / 레드
    ((0, 255, 140), (120, 60, 255)),   # 그린 / 퍼플
    ((255, 220, 0), (255, 50, 120)),   # 옐로 / 마젠타
    ((0, 160, 255), (0, 255, 200)),    # 블루 / 민트
    ((200, 0, 255), (255, 120, 0)),    # 바이올렛 / 오렌지
]


# ═══════════════════════════════════════════════════════════════
# 기록 관리
# ═══════════════════════════════════════════════════════════════

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def record_used(rotation: dict):
    """업로드에 성공한 조합을 기록."""
    history = load_history()
    history.append({**rotation, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history[-365:], ensure_ascii=False, indent=2), encoding="utf-8")


def _pick_avoiding(options: list, recent: list, rng: random.Random):
    """최근 사용한 값을 피해서 고른다. 다 썼으면 전체에서 고른다."""
    fresh = [o for o in options if o not in recent]
    return rng.choice(fresh or options)


# ═══════════════════════════════════════════════════════════════
# payload 생성
# ═══════════════════════════════════════════════════════════════

def next_payload(seed: int = None) -> dict:
    """오늘 올릴 곡의 payload를 생성 (기록은 하지 않음)."""
    rng = random.Random(seed)
    history = load_history()

    # 장르: 카탈로그 한 바퀴 돌 때까지 중복 없음, 바퀴마다 순서는 새로 섞임
    used_in_cycle = len(history) % len(STYLES)
    avoid_ids = {h["style_id"] for h in history[len(history) - used_in_cycle:]}
    if history:
        avoid_ids.add(history[-1]["style_id"])   # 새 바퀴 첫 곡이 어제와 겹치지 않게
    style = _pick_avoiding(STYLES, [s for s in STYLES if s["id"] in avoid_ids], rng)

    recent = history[-5:]
    vocal = _pick_avoiding(VOCALS, [h.get("vocal") for h in recent], rng)
    mood = _pick_avoiding(MOODS, [h.get("mood") for h in recent], rng)
    theme = _pick_avoiding(THEMES, [h.get("theme") for h in history[-len(THEMES) + 1:]], rng)
    pattern = _pick_avoiding(VISUAL_PATTERNS, [h.get("pattern") for h in history[-1:]], rng)
    palette_idx = _pick_avoiding(
        list(range(len(PALETTES))), [h.get("palette") for h in history[-2:]], rng
    )
    bpm = rng.randint(*style["bpm"])
    language = rng.choice(style["lang"])

    rotation = {
        "style_id": style["id"],
        "vocal": vocal,
        "mood": mood,
        "theme": theme,
        "pattern": pattern,
        "palette": palette_idx,
        "bpm": bpm,
    }

    suno_style = (
        f"{style['tags']}, {bpm} BPM, {mood}, {vocal}, "
        f"zumba-style latin dance fitness, punchy modern mix, loud and clear percussion"
    )

    return {
        "core": {
            "keyword": theme,
            "style": suno_style,
        },
        "details": {
            "vocal_style": vocal,
            "tempo_bpm": bpm,
            "mood": mood,
            "language": language,
            "instruments": style["instruments"],
        },
        "suno_params": {"weirdness": rng.randint(15, 35)},
        "prompt_extra": (
            f"- 장르: {style['name']} (라틴 댄스 피트니스용)\n"
            f"- 곡 구조: {STRUCTURE}\n"
            f"- 가사는 따라 외치기 쉬운 짧은 훅 위주로, 운동 동작을 유도하는 표현 포함\n"
            f"- 제목에는 장르명({style['name']})과 {bpm} BPM을 넣어줘. "
            f"'Zumba'는 등록상표이므로 제목·해시태그에 쓰지 말고 "
            f"'Latin Dance Workout', 'Dance Fitness' 같은 표현을 써줘\n"
        ),
        "video": {
            "mode": "techno",
            "pattern": pattern,
            "palette": [list(c) for c in PALETTES[palette_idx]],
            "bpm": bpm,
        },
        "rotation": rotation,
    }


if __name__ == "__main__":
    print(json.dumps(next_payload(), ensure_ascii=False, indent=2))
