"""
server.py — Flask 서버 + 스케줄러
==================================
iPhone Pipeline Commander UI에서 명령을 받고,
매일 정해진 시간에 자동으로 파이프라인을 실행.

사용법:
    cd ~/music_pipeline
    source venv/bin/activate
    python server.py
"""

import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from threading import Thread
import time

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from pipeline import run_pipeline, WORK_DIR, OUTPUT_DIR
from latin_styles import next_payload

# ── 설정 ──────────────────────────────────────────────────────
load_dotenv(WORK_DIR / ".env")

LOG_DIR = WORK_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

QUEUE_DIR = WORK_DIR / "queue"
QUEUE_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "server.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("server")

app = Flask(__name__)
CORS(app)  # iPhone에서 접속 허용


# ═══════════════════════════════════════════════════════════════
# API 엔드포인트
# ═══════════════════════════════════════════════════════════════

@app.route("/api/pipeline", methods=["POST"])
def api_pipeline():
    """iPhone UI에서 즉시 실행 명령을 받음."""
    payload = request.get_json()
    if not payload or not payload.get("core", {}).get("keyword"):
        return jsonify({"error": "키워드 필수"}), 400

    thread = Thread(target=run_pipeline, args=(payload,), daemon=True)
    thread.start()

    keyword = payload["core"]["keyword"]
    logger.info(f"즉시 실행: '{keyword}'")
    return jsonify({
        "status": "started",
        "keyword": keyword,
        "time": datetime.now().strftime("%H:%M:%S"),
    }), 202


@app.route("/api/queue", methods=["POST"])
def api_queue_add():
    """작업을 큐에 추가 (스케줄 실행용)."""
    payload = request.get_json()
    if not payload or not payload.get("core", {}).get("keyword"):
        return jsonify({"error": "키워드 필수"}), 400

    # 큐에 저장
    queue_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    queue_file = QUEUE_DIR / f"{queue_id}.json"
    queue_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    logger.info(f"큐 추가: '{payload['core']['keyword']}' → {queue_file.name}")
    return jsonify({
        "status": "queued",
        "queue_id": queue_id,
        "keyword": payload["core"]["keyword"],
    }), 201


@app.route("/api/queue", methods=["GET"])
def api_queue_list():
    """큐 목록 조회."""
    items = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        items.append({
            "queue_id": f.stem,
            "keyword": data.get("core", {}).get("keyword", ""),
            "style": data.get("core", {}).get("style", ""),
        })
    return jsonify({"queue": items})


@app.route("/api/queue/<queue_id>", methods=["DELETE"])
def api_queue_delete(queue_id):
    """큐에서 항목 삭제."""
    queue_file = QUEUE_DIR / f"{queue_id}.json"
    if queue_file.exists():
        queue_file.unlink()
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/latin/preview", methods=["GET"])
def api_latin_preview():
    """다음에 자동 생성될 라틴 댄스 곡 설정 미리보기 (기록 안 함)."""
    return jsonify(next_payload())


@app.route("/api/latin/run", methods=["POST"])
def api_latin_run():
    """오늘의 라틴 댄스 곡을 자동 설정으로 즉시 생성·업로드."""
    payload = next_payload()
    Thread(target=run_pipeline, args=(payload,), daemon=True).start()
    logger.info(f"라틴 자동 실행: {payload['rotation']}")
    return jsonify({"status": "started", "rotation": payload["rotation"]}), 202


@app.route("/api/status", methods=["GET"])
def api_status():
    """최근 작업 상태 확인."""
    jobs = sorted(OUTPUT_DIR.iterdir(), reverse=True) if OUTPUT_DIR.exists() else []
    recent = []
    for job_dir in jobs[:10]:
        if not job_dir.is_dir():
            continue
        info = {"job_id": job_dir.name}
        payload_file = job_dir / "payload.json"
        gpt_file = job_dir / "gpt_result.json"
        final = job_dir / "final.mp4"

        info["completed"] = final.exists()
        if payload_file.exists():
            p = json.loads(payload_file.read_text())
            info["keyword"] = p.get("core", {}).get("keyword", "")
        if gpt_file.exists():
            g = json.loads(gpt_file.read_text())
            info["title"] = g.get("title", "")
        recent.append(info)
    return jsonify({"jobs": recent})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route("/", methods=["GET"])
def serve_ui():
    """Pipeline Commander UI를 직접 서빙."""
    ui_path = WORK_DIR / "pipeline_commander.html"
    if ui_path.exists():
        return send_from_directory(str(WORK_DIR), "pipeline_commander.html")
    return "<h3>pipeline_commander.html을 ~/music_pipeline/ 에 넣어주세요</h3>", 404


# ═══════════════════════════════════════════════════════════════
# 스케줄러 (매일 정해진 시간에 큐 실행)
# ═══════════════════════════════════════════════════════════════

def scheduler_loop():
    """큐에 있는 작업을 정해진 시간에 실행."""
    # SCHEDULE_TIME_2를 비워두면 하루 1회만 실행
    schedules = [t for t in (os.getenv("SCHEDULE_TIME_1", "10:00"),
                             os.getenv("SCHEDULE_TIME_2", "")) if t.strip()]
    # 큐가 비어 있으면 라틴 댄스 곡을 자동 설정으로 생성
    auto_latin = os.getenv("AUTO_LATIN_DAILY", "1") == "1"
    executed_today = set()

    logger.info(f"스케줄러 시작: {', '.join(schedules)} (라틴 자동생성: {auto_latin})")

    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today = now.strftime("%Y%m%d")

        # 날짜가 바뀌면 실행 기록 초기화
        if any(d[:8] != today for d in executed_today) if executed_today else False:
            executed_today.clear()

        for schedule_time in schedules:
            schedule_key = f"{today}_{schedule_time}"

            if current_time == schedule_time and schedule_key not in executed_today:
                # 큐에서 가장 오래된 작업 꺼내기
                queue_files = sorted(QUEUE_DIR.glob("*.json"))
                if queue_files:
                    queue_file = queue_files[0]
                    payload = json.loads(queue_file.read_text())
                    queue_file.unlink()  # 큐에서 제거

                    logger.info(f"스케줄 실행 ({schedule_time}): "
                                f"'{payload['core']['keyword']}'")

                    thread = Thread(
                        target=run_pipeline, args=(payload,), daemon=True
                    )
                    thread.start()
                elif auto_latin:
                    payload = next_payload()
                    logger.info(f"스케줄 실행 ({schedule_time}): 라틴 자동 생성 "
                                f"{payload['rotation']}")
                    Thread(target=run_pipeline, args=(payload,), daemon=True).start()
                else:
                    logger.info(f"스케줄 시간 ({schedule_time}) 이지만 큐가 비어있음")

                executed_today.add(schedule_key)

        time.sleep(30)  # 30초마다 체크


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("═══ Music Pipeline Server 시작 ═══")
    logger.info(f"작업 디렉토리: {WORK_DIR}")

    # 스케줄러를 백그라운드 스레드로 실행
    scheduler = Thread(target=scheduler_loop, daemon=True)
    scheduler.start()

    # 맥북 IP 확인
    import subprocess as sp
    try:
        ip = sp.check_output(
            ["ipconfig", "getifaddr", "en0"], text=True
        ).strip()
    except:
        ip = "localhost"

    logger.info(f"서버 주소: http://{ip}:8080")
    logger.info("iPhone에서 위 주소로 접속하세요")

    app.run(host="0.0.0.0", port=8080, debug=False)
