# dynasty.py - Part1
# =========================================
# KBO Dynasty - Main Blueprint
# Part1 / Part2 / Part3 을 이어 붙이면 완성된다.
# =========================================

import os
import random
import json
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session

from supabase import create_client

from dynasty_import import import_players_for_season
from dynasty_schedule import generate_schedule, get_week_games
from dynasty_game import simulate_week
from dynasty_growth import process_offseason_growth
from dynasty_lineup import auto_generate_lineup
from dynasty_utils import (
    get_supabase,
    AI_TEAM_POOL,
    calc_team_power,
    get_standings,
)

dynasty_bp = Blueprint("dynasty", __name__)

SEASON_WEEKS = 24
DRAFT_ROUNDS = 25
TEAM_COUNT = 10


# =========================================
# 홈 - 세이브 목록
# =========================================
@dynasty_bp.route("/dynasty")
def dynasty_home():
    sb = get_supabase()
    saves = (
        sb.table("dynasty_save")
        .select("*")
        .order("id", desc=True)
        .execute()
        .data
    )
    return render_template("dynasty_home.html", saves=saves)


# =========================================
# 새 게임 생성
# =========================================
@dynasty_bp.route("/dynasty/new", methods=["GET", "POST"])
def dynasty_new():
    if request.method == "GET":
        return render_template("dynasty_new.html")

    sb = get_supabase()

    team_name = request.form.get("team_name", "").strip()
    logo = request.form.get("logo", "⚾").strip()
    color = request.form.get("color", "#1a5276").strip()
    stadium = request.form.get("stadium", "").strip()

    if not team_name:
        return redirect(url_for("dynasty.dynasty_new"))
    if not stadium:
        stadium = team_name + " 파크"

    save_row = (
        sb.table("dynasty_save")
        .insert(
            {
                "team_name": team_name,
                "logo": logo,
                "color": color,
                "stadium": stadium,
                "season": 1,
                "week": 0,
                "finished": False,
            }
        )
        .execute()
        .data[0]
    )
    save_id = save_row["id"]

    teams = []
    teams.append(
        {
            "save_id": save_id,
            "team_name": team_name,
            "logo": logo,
            "color": color,
            "stadium": stadium,
            "is_user": True,
            "wins": 0,
            "losses": 0,
            "ties": 0,
        }
    )

    ai_pool = [t for t in AI_TEAM_POOL if t["team_name"] != team_name]
    random.shuffle(ai_pool)
    for t in ai_pool[: TEAM_COUNT - 1]:
        teams.append(
            {
                "save_id": save_id,
                "team_name": t["team_name"],
                "logo": t["logo"],
                "color": t["color"],
                "stadium": t["stadium"],
                "is_user": False,
                "wins": 0,
                "losses": 0,
                "ties": 0,
            }
        )

    sb.table("dynasty_team").insert(teams).execute()

    import_players_for_season(save_id, 1)

    return redirect(url_for("dynasty.dynasty_draft", save_id=save_id))


# =========================================
# 드래프트 화면
# =========================================
@dynasty_bp.route("/dynasty/draft/<int:save_id>")
def dynasty_draft(save_id):
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
        .order("id")
        .execute()
        .data
    )

    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .order("overall", desc=True)
        .execute()
        .data
    )

    user_team = next(t for t in teams if t["is_user"])

    roster_rows = (
        sb.table("dynasty_roster")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    picked_count = len(roster_rows)
    current_round = picked_count // TEAM_COUNT + 1

    return render_template(
        "dynasty_draft.html",
        save=save,
        teams=teams,
        players=players,
        user_team=user_team,
        current_round=current_round,
        total_rounds=DRAFT_ROUNDS,
        picked_count=picked_count,
    )

# dynasty.py - Part2

# =========================================
# 드래프트 - 유저 픽
# =========================================
@dynasty_bp.route("/dynasty/draft/<int:save_id>/pick", methods=["POST"])
def dynasty_draft_pick(save_id):
    sb = get_supabase()

    player_id = int(request.form.get("player_id"))

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .order("id")
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])
    ai_teams = [t for t in teams if not t["is_user"]]

    roster_rows = (
        sb.table("dynasty_roster")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    picked_count = len(roster_rows)
    current_round = picked_count // TEAM_COUNT + 1

    if current_round > DRAFT_ROUNDS:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    # 유저 픽
    _draft_player(sb, save_id, user_team["id"], player_id)

    # AI 픽
    remaining = (
        sb.table("dynasty_player")
        .select("id, overall, positions")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .order("overall", desc=True)
        .limit(80)
        .execute()
        .data
    )

    random.shuffle(ai_teams)
    for team in ai_teams:
        if not remaining:
            break
        pool = remaining[: min(8, len(remaining))]
        pick = random.choice(pool)
        remaining.remove(pick)
        _draft_player(sb, save_id, team["id"], pick["id"])

    picked_count = picked_count + TEAM_COUNT
    if picked_count >= DRAFT_ROUNDS * TEAM_COUNT:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    return redirect(url_for("dynasty.dynasty_draft", save_id=save_id))


def _draft_player(sb, save_id, team_id, player_id):
    sb.table("dynasty_player").update({"drafted": True}).eq("id", player_id).execute()
    sb.table("dynasty_roster").insert(
        {
            "save_id": save_id,
            "team_id": team_id,
            "player_id": player_id,
            "role": "BENCH",
            "depth": 99,
        }
    ).execute()


# =========================================
# 드래프트 종료 → 라인업 + 일정 생성
# =========================================
@dynasty_bp.route("/dynasty/draft/<int:save_id>/finish")
def dynasty_draft_finish(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    for team in teams:
        auto_generate_lineup(save_id, team["id"])

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    generate_schedule(save_id, save["season"], SEASON_WEEKS)

    sb.table("dynasty_save").update({"week": 1}).eq("id", save_id).execute()

    return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))


# =========================================
# 대시보드
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>")
def dynasty_dashboard(save_id):
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

    standings = get_standings(teams)

    week_games = get_week_games(save_id, save["season"], save["week"])
    last_games = (
        get_week_games(save_id, save["season"], save["week"] - 1)
        if save["week"] > 1
        else []
    )

    team_map = {t["id"]: t for t in teams}

    roster_rows = (
        sb.table("dynasty_roster")
        .select("*, dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", user_team["id"])
        .order("depth")
        .execute()
        .data
    )

    return render_template(
        "dynasty_dashboard.html",
        save=save,
        teams=teams,
        team_map=team_map,
        user_team=user_team,
        standings=standings,
        week_games=week_games,
        last_games=last_games,
        roster=roster_rows,
        season_weeks=SEASON_WEEKS,
    )

# dynasty.py - Part3

# =========================================
# 다음 주 진행
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/next", methods=["POST"])
def dynasty_next_week(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    if save["finished"]:
        return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))

    week = save["week"]

    if week > SEASON_WEEKS:
        return redirect(url_for("dynasty.dynasty_season_end", save_id=save_id))

    simulate_week(save_id, save["season"], week)

    new_week = week + 1
    sb.table("dynasty_save").update({"week": new_week}).eq("id", save_id).execute()

    if new_week > SEASON_WEEKS:
        return redirect(url_for("dynasty.dynasty_season_end", save_id=save_id))

    return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))


# =========================================
# 시즌 종료
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/season_end")
def dynasty_season_end(save_id):
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

    standings = get_standings(teams)
    champion = standings[0]
    user_team = next(t for t in teams if t["is_user"])
    user_rank = next(
        i + 1 for i, t in enumerate(standings) if t["id"] == user_team["id"]
    )

    return render_template(
        "dynasty_end.html",
        save=save,
        standings=standings,
        champion=champion,
        user_team=user_team,
        user_rank=user_rank,
    )


# =========================================
# 다음 시즌 시작
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/next_season", methods=["POST"])
def dynasty_next_season(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    new_season = save["season"] + 1

    process_offseason_growth(save_id)

    import_players_for_season(save_id, new_season)

    sb.table("dynasty_team").update(
        {"wins": 0, "losses": 0, "ties": 0}
    ).eq("save_id", save_id).execute()

    sb.table("dynasty_save").update(
        {"season": new_season, "week": 0}
    ).eq("id", save_id).execute()

    return redirect(url_for("dynasty.dynasty_rookie_draft", save_id=save_id))


# =========================================
# 신인 드래프트 (시즌2 이후)
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_draft")
def dynasty_rookie_draft(save_id):
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
        .order("id")
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .eq("appear_season", save["season"])
        .order("overall", desc=True)
        .execute()
        .data
    )

    return render_template(
        "dynasty_draft.html",
        save=save,
        teams=teams,
        players=players,
        user_team=user_team,
        current_round=1,
        total_rounds=5,
        picked_count=0,
        rookie_mode=True,
    )


# =========================================
# 신인 드래프트 픽
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_pick", methods=["POST"])
def dynasty_rookie_pick(save_id):
    sb = get_supabase()

    player_id = int(request.form.get("player_id"))

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
        .order("id")
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])
    ai_teams = [t for t in teams if not t["is_user"]]

    _draft_player(sb, save_id, user_team["id"], player_id)

    remaining = (
        sb.table("dynasty_player")
        .select("id, overall")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .eq("appear_season", save["season"])
        .order("overall", desc=True)
        .limit(40)
        .execute()
        .data
    )

    random.shuffle(ai_teams)
    for team in ai_teams:
        if not remaining:
            break
        pool = remaining[: min(5, len(remaining))]
        pick = random.choice(pool)
        remaining.remove(pick)
        _draft_player(sb, save_id, team["id"], pick["id"])

    return redirect(url_for("dynasty.dynasty_rookie_draft", save_id=save_id))


# =========================================
# 신인 드래프트 종료 → 시즌 시작
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_finish")
def dynasty_rookie_finish(save_id):
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

    for team in teams:
        auto_generate_lineup(save_id, team["id"])

    generate_schedule(save_id, save["season"], SEASON_WEEKS)

    sb.table("dynasty_save").update({"week": 1}).eq("id", save_id).execute()

    return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))


# =========================================
# 세이브 삭제
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/delete", methods=["POST"])
def dynasty_delete(save_id):
    sb = get_supabase()

    sb.table("dynasty_roster").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_schedule").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_player").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_team").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_save").delete().eq("id", save_id).execute()

    return redirect(url_for("dynasty.dynasty_home"))
