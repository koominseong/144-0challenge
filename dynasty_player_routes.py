# dynasty_player_routes.py
# =========================================
# KBO Dynasty - 선수 상세 / 명예의 전당
# app.py에 등록:
#   from dynasty_player_routes import player_bp
#   app.register_blueprint(player_bp)
# =========================================

from flask import Blueprint, render_template

from dynasty_utils import get_supabase

player_bp = Blueprint("dynasty_player", __name__)

# 명예의 전당 헌액 기준
HOF_PEAK = 82           # 최고 OVR 82 이상이면 무조건
HOF_PEAK_LONG = 75      # 또는 최고 75 이상 + 12년 이상
HOF_CAREER_LONG = 12


# =========================================
# 선수 상세 (능력치 + 시즌별 변화)
# =========================================
@player_bp.route("/dynasty/<int:save_id>/player/<int:player_id>")
def player_detail(save_id, player_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])
    team_map = {t["id"]: t for t in teams}

    player = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("id", player_id)
        .execute()
        .data[0]
    )

    # 소속팀
    roster = (
        sb.table("dynasty_roster")
        .select("team_id, role")
        .eq("save_id", save_id)
        .eq("player_id", player_id)
        .execute()
        .data
    )
    current_team = team_map.get(roster[0]["team_id"]) if roster else None
    current_role = roster[0]["role"] if roster else None

    # 시즌별 능력치 변화
    history = (
        sb.table("dynasty_player_history")
        .select("*")
        .eq("save_id", save_id)
        .eq("player_id", player_id)
        .order("season")
        .execute()
        .data
    )

    is_pitcher = "P" in (player["positions"] or "")

    career_years = None
    if player.get("retired") and player.get("retired_season"):
        career_years = player["retired_season"] - player["appear_season"] + 1
    else:
        career_years = save["season"] - player["appear_season"] + 1

    is_hof = _check_hof(player)

    return render_template(
        "dynasty_player.html",
        save=save,
        user_team=user_team,
        player=player,
        current_team=current_team,
        current_role=current_role,
        history=history,
        is_pitcher=is_pitcher,
        career_years=career_years,
        is_hof=is_hof,
    )


# =========================================
# 명예의 전당
# =========================================
@player_bp.route("/dynasty/<int:save_id>/hof")
def hof(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    retired = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("retired", True)
        .order("peak_overall", desc=True)
        .execute()
        .data
    )

    inductees = []
    for p in retired:
        if _check_hof(p):
            p["career_years"] = (
                (p.get("retired_season") or save["season"])
                - p["appear_season"] + 1
            )
            inductees.append(p)

    return render_template(
        "dynasty_hof.html",
        save=save,
        user_team=user_team,
        inductees=inductees,
    )


def _check_hof(p):
    if not p.get("retired"):
        return False
    peak = p.get("peak_overall") or p["overall"]
    career = None
    if p.get("retired_season"):
        career = p["retired_season"] - p["appear_season"] + 1
    if peak >= HOF_PEAK:
        return True
    if peak >= HOF_PEAK_LONG and career and career >= HOF_CAREER_LONG:
        return True
    return False
