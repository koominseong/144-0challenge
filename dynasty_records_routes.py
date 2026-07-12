# dynasty_records_routes.py
# =========================================
# KBO Dynasty - Phase 10: 기록실 (통산 리더보드)
# dynasty_player_stats 전 시즌 합산
# app.py 등록:
#   from dynasty_records_routes import records_bp
#   app.register_blueprint(records_bp)
# =========================================

from flask import Blueprint, render_template

from dynasty_utils import get_supabase

records_bp = Blueprint("dynasty_records", __name__)

CATEGORIES = [
    ("hr", "🏏 통산 홈런"),
    ("hits", "⚾ 통산 안타"),
    ("rbi", "🎯 통산 타점"),
    ("sb", "💨 통산 도루"),
    ("wins", "🏆 통산 다승"),
    ("saves", "🧯 통산 세이브"),
    ("so", "🔥 통산 탈삼진"),
    ("games", "📅 통산 출장"),
]

TOP_N = 10


@records_bp.route("/dynasty/<int:save_id>/records")
def records_home(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("*").eq("id", save_id).execute().data[0]

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    user_team = next(t for t in teams if t["is_user"])

    # 전 시즌 기록 로드 (페이지네이션)
    all_rows = []
    offset = 0
    while True:
        rows = (
            sb.table("dynasty_player_stats")
            .select("player_id, season, hits, hr, rbi, sb, wins, losses, saves, so, games")
            .eq("save_id", save_id)
            .range(offset, offset + 999)
            .execute()
            .data
        )
        all_rows.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    # 선수별 통산 합산
    career = {}
    for r in all_rows:
        c = career.setdefault(
            r["player_id"],
            {"player_id": r["player_id"], "seasons": set(),
             "hits": 0, "hr": 0, "rbi": 0, "sb": 0,
             "wins": 0, "losses": 0, "saves": 0, "so": 0, "games": 0},
        )
        c["seasons"].add(r["season"])
        for k in ("hits", "hr", "rbi", "sb", "wins", "losses", "saves", "so", "games"):
            c[k] += r[k] or 0

    # 상위 후보 선수 이름/상태 로드 (카테고리별 TOP_N 합집합만)
    top_ids = set()
    for key, _ in CATEGORIES:
        ranked = sorted(career.values(), key=lambda c: -c[key])[:TOP_N]
        top_ids.update(c["player_id"] for c in ranked if c[key] > 0)

    players = {}
    ids = list(top_ids)
    for i in range(0, len(ids), 100):
        rows = (
            sb.table("dynasty_player")
            .select("id, name, positions, retired")
            .eq("save_id", save_id)
            .in_("id", ids[i : i + 100])
            .execute()
            .data
        )
        for p in rows:
            players[p["id"]] = p

    # 카테고리별 보드 구성
    boards = []
    for key, title in CATEGORIES:
        ranked = sorted(career.values(), key=lambda c: -c[key])[:TOP_N]
        entries = []
        for c in ranked:
            if c[key] <= 0:
                continue
            p = players.get(c["player_id"])
            if not p:
                continue
            entries.append(
                {
                    "player_id": c["player_id"],
                    "name": p["name"],
                    "positions": p["positions"],
                    "retired": p["retired"],
                    "value": c[key],
                    "seasons": len(c["seasons"]),
                }
            )
        boards.append({"key": key, "title": title, "entries": entries})

    return render_template(
        "dynasty_records.html",
        save=save,
        user_team=user_team,
        boards=boards,
    )
