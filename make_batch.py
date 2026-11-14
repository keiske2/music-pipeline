"""
make_batch.py — 한 달 치 곡 세트(batch/*.json)로 수노 입력·메타·영상 프롬프트·작업 도우미 페이지 만들기
=====================================================================================================
batch/<월>.json 의 곡마다 다음을 만든다 (이미 있는 파일은 건드리지 않음, --force면 덮어씀):
  - lyrics/<key>.md   수노 입력값 (Title / Style / Exclude Styles / Lyrics)
  - meta/<key>.json   유튜브 제목·설명(해시태그+가사)·태그·BPM — 업로드 때 파일 이름으로 자동 매칭
  - --page 경로를 주면 복사 버튼이 달린 작업 도우미 HTML

드라이브에 넣을 파일 이름은 제목에서 만든다. 예: "Uno, Dos, Chachachá" → Uno_Dos_Chachacha.mp3 / .mp4

사용법:
    python make_batch.py batch/2026-11.json [--page helper.html] [--force]
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

from publish_one import HASHTAGS_BOTTOM, TAGS

ROOT = Path(__file__).parent


def file_stem(title: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return "_".join(re.findall(r"[A-Za-z0-9]+", ascii_))


def video_prompt(v: dict) -> str:
    """부메랑 루프용 규칙(고정 카메라·제자리·한 컷·아래 1/3 어두운 바닥·글자 없음)을 담은 Veo 프롬프트."""
    return (
        f"Cinematic 16:9 music video shot, single continuous take, locked-off camera on a tripod at "
        f"{v['h']} height, medium-wide framing. {v['dancer']}, dances {v['dance']} in place at the center "
        f"of the frame: {v['moves']}. She stays centered the whole time. Setting: {v['setting']}. "
        f"The lower third of the frame is {v['floor']}. {v['look']}, 24fps film look. No cuts, no camera "
        f"movement, no text, no logos, no other people entering or leaving the frame."
    )


def plain_lyrics(lyrics: str) -> str:
    """[Verse] 같은 태그와 빈 줄을 뺀 화면용·설명란용 가사."""
    return "\n".join(l for l in lyrics.splitlines() if l.strip() and not re.fullmatch(r"\[.*\]", l.strip()))


def make_meta(s: dict) -> dict:
    if "channel" in s:   # 라틴 댄스가 아닌 곡(예: 블루스)은 곡 데이터의 제목 꼬리·해시태그·설명을 쓴다
        return make_custom_meta(s)
    tag = re.sub(r"[^A-Za-z]", "", unicodedata.normalize("NFKD", s["genre"]).encode("ascii", "ignore").decode())
    lyrics = plain_lyrics(s["lyrics"])
    description = (
        f"#LatinDance #{tag} #줌바\n"
        f"{s['title']} – {s['genre']} 라틴 댄스 운동 음악 | {s['genre']} dance workout with lyrics.\n"
        "따라 부르고 따라 추는 라틴 댄스! 화면 가사와 함께 즐겨 보세요.\n\n"
        "🎧 Music created with Suno AI\n\n"
        f"🎤 Lyrics / Letra\n{lyrics}\n\n"
        f"{HASHTAGS_BOTTOM.replace('#BailarLatino', f'#{tag}')}"
    )
    return {
        "title": f"{s['title']} | {s['genre']} Latin Dance Workout 2026"[:100],
        "description": description[:5000],
        "tags": TAGS + [s["genre"].lower(), f"{s['genre'].lower()} fitness", s["title"].lower()],
        "categoryId": "10",
        "lyrics": lyrics,
        "bpm": s["bpm"],
        "language": s.get("language", "es"),   # 가사 받아쓰기 언어 (삼바는 pt)
    }


def make_custom_meta(s: dict) -> dict:
    c = s["channel"]
    lyrics = plain_lyrics(s["lyrics"])
    description = (
        f"{c['hashtags_top']}\n{s['title']} – {c['blurb']}\n\n"
        "🎧 Music created with Suno AI\n\n"
        f"🎤 Lyrics\n{lyrics}\n\n{c['hashtags_bottom']}"
    )
    return {
        "title": f"{s['title']} | {c['title_suffix']}"[:100],
        "description": description[:5000],
        "tags": c["tags"] + [s["title"].lower()],
        "categoryId": "10",
        "lyrics": lyrics,
        "bpm": s["bpm"],
        "language": s.get("language", "en"),
    }


def lyrics_md(s: dict) -> str:
    return (
        f"# {s['title']} — {s['genre_ko']} ({s['genre']})\n\n## Suno 입력\n\n**Title**: {s['title']}\n\n"
        f"**Style of Music** (그대로 붙여넣기):\n```\n{s['style']}\n```\n\n"
        f"**Exclude Styles** (라이브 느낌 빼기, 그대로 붙여넣기):\n```\n{s['exclude']}\n```\n\n"
        f"**Lyrics** (그대로 붙여넣기):\n```\n{s['lyrics']}\n```\n\n"
        f"## 제미나이 영상 프롬프트 (부메랑용)\n```\n{s['video']}\n```\n\n"
        f"## 드라이브에 넣을 파일 이름\n`{file_stem(s['title'])}.mp3`, `{file_stem(s['title'])}.mp4`\n"
    )


PAGE = """<title>주말 곡 만들기 도우미</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Noto+Sans+KR:wght@400;500;700&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* layout: 곡 카드가 위에서 아래로, 각 카드 안에 수노 → 제미나이 → 저장 3단계. 위쪽 목차로 곡 이동 */
:root{
  --bg:#0d0716; --panel:#170d24; --line:#2f1d45; --fg:#f3ecfb; --muted:#a995c2;
  --pink:#ff3fb4; --cyan:#22e3ff; --ok:#46e08a; --chip:#24163a;
  --display:"Bebas Neue",Impact,"Arial Narrow",sans-serif;
  --body:"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
  color-scheme:dark;
}
body{background:var(--bg);color:var(--fg);font-family:var(--body);font-size:15px;line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding-block:28px 56px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:24px}
header h1{font-family:var(--display);font-weight:400;font-size:clamp(34px,7vw,52px);letter-spacing:.02em;line-height:1;margin:0}
header h1 span{color:var(--pink)}
header p{margin:8px 0 0;color:var(--muted);max-width:62ch}
nav{display:flex;flex-wrap:wrap;gap:8px}
nav a{color:var(--fg);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:13px;background:var(--chip)}
nav a b{color:var(--cyan);font-weight:500;margin-right:4px;font-family:var(--mono);font-size:12px}
nav a:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
#songs{display:flex;flex-direction:column;gap:22px}
.song{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:22px;display:flex;flex-direction:column;gap:18px;scroll-margin-top:12px}
.song-head{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px 16px}
.song-head h2{font-family:var(--display);font-weight:400;font-size:34px;letter-spacing:.03em;margin:0;line-height:1;text-wrap:balance}
.tag{font-size:12px;letter-spacing:.08em;color:var(--cyan);text-transform:uppercase}
.mood{color:var(--muted);font-size:13px}
.step{display:grid;grid-template-columns:30px 1fr;gap:12px;align-items:start}
.num{width:30px;height:30px;border-radius:50%;border:1px solid var(--pink);color:var(--pink);display:grid;place-items:center;font-family:var(--mono);font-size:13px}
.step-body{min-width:0;display:flex;flex-direction:column;gap:10px}
.step-body h3{margin:3px 0 0;font-size:15px;font-weight:700}
.row{display:flex;flex-wrap:wrap;gap:8px}
a.go,button{font:inherit;font-size:14px;border-radius:8px;padding:8px 14px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;min-height:38px}
a.go{background:var(--pink);color:#160616;font-weight:700;border:1px solid var(--pink)}
button{background:transparent;color:var(--fg);border:1px solid var(--line)}
button:hover,a.go:hover{filter:brightness(1.12)}
button:focus-visible,a.go:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
button.done{border-color:var(--ok);color:var(--ok)}
details{border:1px solid var(--line);border-radius:8px}
summary{cursor:pointer;padding:8px 12px;color:var(--muted);font-size:13px}
pre{margin:0;padding:12px;font-family:var(--mono);font-size:12.5px;white-space:pre-wrap;word-break:break-word;max-height:280px;overflow:auto;border-top:1px solid var(--line)}
code{font-family:var(--mono);font-size:13px;background:var(--chip);padding:2px 6px;border-radius:5px;color:var(--cyan);word-break:break-all}
.hint{color:var(--muted);font-size:13px;margin:0}
.final{border-left:3px solid var(--cyan);padding:4px 0 4px 16px;color:var(--muted);margin:0}
.final b{color:var(--fg)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
<div class="wrap">
  <header>
    <h1>이달의 <span>8곡</span></h1>
    <p>한 달에 한 번, 곡마다 수노와 제미나이에 복사해 붙여넣고 만든 파일을 드라이브에 넣으세요. 매주 토·일 한 곡씩 부메랑 영상, 화면 가사, 해시태그와 함께 자동으로 올라갑니다.</p>
  </header>
  <nav id="toc" aria-label="곡 목록"></nav>
  <div id="songs"></div>
  <p class="final"><b>마지막:</b> 파일을 모두 구글 드라이브 <code>Suno/날짜</code> 폴더에 넣으세요. 먼저 넣은 곡부터 토·일에 한 곡씩 올라가고, 문제가 생기면 메일로 알림이 옵니다.</p>
</div>
<script>
const SONGS = __DATA__;
function esc(s){return s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function copyBtn(label,text){return `<button type="button" data-copy="${esc(text)}">${esc(label)} 복사</button>`}
document.getElementById("toc").innerHTML = SONGS.map((s,i)=>`<a href="#${s.key}"><b>${i+1}</b>${esc(s.genre_ko)}</a>`).join("");
document.getElementById("songs").innerHTML = SONGS.map((s,i)=>`
<section class="song" id="${s.key}" aria-labelledby="h-${s.key}">
  <div class="song-head"><h2 id="h-${s.key}">${i+1}. ${esc(s.title)}</h2><span class="tag">${esc(s.genre_ko)} · ${s.bpm} BPM</span></div>
  <div class="mood">${esc(s.mood_ko)}</div>
  <div class="step"><div class="num">1</div><div class="step-body">
    <h3>수노에서 곡 만들기</h3>
    <p class="hint">Custom 모드를 켜고 각 칸에 붙여넣기 → Create</p>
    <div class="row"><a class="go" href="https://suno.com/create" target="_blank" rel="noopener">수노 열기 ↗</a>
      ${copyBtn("제목",s.title)}${copyBtn("스타일",s.style)}${copyBtn("제외 스타일",s.exclude)}${copyBtn("가사",s.lyrics)}</div>
    <details><summary>가사 보기</summary><pre>${esc(s.lyrics)}</pre></details>
  </div></div>
  <div class="step"><div class="num">2</div><div class="step-body">
    <h3>제미나이에서 댄스 영상 만들기</h3>
    <p class="hint">영상 만들기에 프롬프트를 붙여넣기 (가로 16:9)</p>
    <div class="row"><a class="go" href="https://gemini.google.com/app" target="_blank" rel="noopener">제미나이 열기 ↗</a>${copyBtn("영상 프롬프트",s.video)}</div>
    <details><summary>프롬프트 보기</summary><pre>${esc(s.video)}</pre></details>
  </div></div>
  <div class="step"><div class="num">3</div><div class="step-body">
    <h3>이 이름으로 저장해서 드라이브에 넣기</h3>
    <div class="row">${copyBtn(s.file+".mp3",s.file+".mp3")}${copyBtn(s.file+".mp4",s.file+".mp4")}<a class="go" href="https://drive.google.com/drive/my-drive" target="_blank" rel="noopener">드라이브 열기 ↗</a></div>
  </div></div>
</section>`).join("");
document.addEventListener("click",async e=>{
  const b=e.target.closest("button[data-copy]"); if(!b) return;
  const t=b.getAttribute("data-copy"), label=b.textContent;
  try{ await navigator.clipboard.writeText(t); b.textContent="복사됨 ✓"; b.classList.add("done"); }
  catch(_){ const ta=document.createElement("textarea"); ta.value=t; document.body.appendChild(ta); ta.select();
    try{document.execCommand("copy"); b.textContent="복사됨 ✓"; b.classList.add("done");}catch(__){b.textContent="직접 선택해 복사";} ta.remove(); }
  setTimeout(()=>{b.textContent=label;b.classList.remove("done")},1600);
});
</script>
"""


def main():
    parser = argparse.ArgumentParser(description="한 달 치 곡 세트 만들기")
    parser.add_argument("batch", type=Path)
    parser.add_argument("--page", type=Path, help="작업 도우미 HTML 저장 경로")
    parser.add_argument("--force", action="store_true", help="이미 있는 lyrics/meta 파일도 덮어쓰기")
    args = parser.parse_args()

    songs = json.loads(args.batch.read_text(encoding="utf-8"))
    for s in songs:
        s.setdefault("video", video_prompt(s["v"]) if "v" in s else "")
        s["file"] = file_stem(s["title"])
        for path, content in (
            (ROOT / "lyrics" / f"{s['key']}.md", lyrics_md(s)),
            (ROOT / "meta" / f"{s['key']}.json", json.dumps(make_meta(s), ensure_ascii=False, indent=2) + "\n"),
        ):
            if path.exists() and not args.force:
                print(f"건너뜀(이미 있음): {path.relative_to(ROOT)}")
                continue
            path.write_text(content, encoding="utf-8")
            print(f"작성: {path.relative_to(ROOT)}")
        print(f"  드라이브 파일: {s['file']}.mp3 / {s['file']}.mp4")

    if args.page:
        keys = ("key", "title", "genre_ko", "bpm", "mood_ko", "style", "exclude", "lyrics", "video", "file")
        data = json.dumps([{k: s[k] for k in keys} for s in songs], ensure_ascii=False).replace("</", "<\\/")
        args.page.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
        print(f"도우미 페이지: {args.page}")


if __name__ == "__main__":
    main()
