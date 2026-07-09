# dynasty.py - Part1
# =========================================
# KBO Dynasty - Main Blueprint
# (비밀번호 보호 + FA 연동 버전)
# 세이브 생성 시 비밀번호 설정 → 접근 시 인증 필요
# DB 준비: ALTER TABLE dynasty_save ADD COLUMN IF NOT EXISTS password text;
# Part1 / Part2 / Part3 을 이어 붙이면 완성된다.
# =========================================

import os
import random
import json
import hashlib
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session

from supabase import create_client

from dynasty_import import import_players_for_season
from dynasty_schedule import generate_schedule, get_week_games
from dynasty_game import simulate_week
from dynasty_growth import process_offseason_growth
from dynasty_lineup import auto_generate_lineup
from dynasty_fa import generate_fa_market, ai_sign_fa
from dynasty_trade import ai_auto_trades
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
# 비밀번호 해시
# =========================================
def _hash_pw(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =========================================
# 접근 인증 확인
# =========================================
def _is_authed(save_id):
    return session.get(f"auth_{save_id}") is True


# =========================================
# 인증 필요 데코레이터
# 라우트 첫 번째 인자가 save_id여야 한다
# =========================================
def require_auth(f):
    @wraps(f)
    def wrapper(save_id, *args, **kwargs):
        if not _is_authed(save_id):
            return redirect(url_for("dynasty.dynasty_unlock", save_id=save_id))
        return f(save_id, *args, **kwargs)
    return wrapper


# =========================================
# 비밀번호 입력 화면 / 확인
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/unlock", methods=["GET", "POST"])
def dynasty_unlock(save_id):
    sb = get_supabase()

    save_rows = (
        sb.table("dynasty_save")
        .select("id, team_name, logo, color, password")
        .eq("id", save_id)
        .execute()
        .data
    )
    if not save_rows:
        return redirect(url_for("dynasty.dynasty_home"))
    save = save_rows[0]

    # 비밀번호 미설정 세이브는 바로 통과
    if not save.get("password"):
        session[f"auth_{save_id}"] = True
        return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))

    error = ""

    if request.method == "POST":
        pw = request.form.get("password", "")
        if _hash_pw(pw) == save["password"]:
            session[f"auth_{save_id}"] = True
            return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))
        error = "비밀번호가 올바르지 않습니다."

    return render_template("dynasty_unlock.html", save=save, error=error)


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
# 새 게임 생성 (비밀번호 설정)
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
    password = request.form.get("password", "").strip()

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
                "password": _hash_pw(password) if password else None,
            }
        )
        .execute()
        .data[0]
    )
    save_id = save_row["id"]

    # 생성자는 즉시 인증
    session[f"auth_{save_id}"] = True

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
@require_auth
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
        .select("id")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    picked_count = len(roster_rows)
    current_round = picked_count // TEAM_COUNT + 1

    my_picks = _get_my_picks(sb, save_id, user_team["id"])
    last_picks = session.pop(f"last_picks_{save_id}", None)

    return render_template(
        "dynasty_draft.html",
        save=save,
        teams=teams,
        players=players,
        user_team=user_team,
        current_round=current_round,
        total_rounds=DRAFT_ROUNDS,
        picked_count=picked_count,
        my_picks=my_picks,
        last_picks=last_picks,
        rookie_mode=False,
    )


# =========================================
# 내가 뽑은 선수 목록 조회
# =========================================
def _get_my_picks(sb, save_id, team_id):
    rows = (
        sb.table("dynasty_roster")
        .select("id, dynasty_player(name, positions, overall, potential)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .order("id")
        .execute()
        .data
    )
    picks = []
    for i, r in enumerate(rows):
        p = r["dynasty_player"]
        if not p:
            continue
        picks.append(
            {
                "round": i + 1,
                "name": p["name"],
                "positions": p["positions"],
                "overall": p["overall"],
                "potential": p["potential"],
            }
        )
    return picks

# dynasty.py - Part2

# =========================================
# 드래프트 - 유저 픽 + AI 픽
# =========================================
@dynasty_bp.route("/dynasty/draft/<int:save_id>/pick", methods=["POST"])
@require_auth
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
        .select("id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    picked_count = len(roster_rows)
    current_round = picked_count // TEAM_COUNT + 1

    if current_round > DRAFT_ROUNDS:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    round_picks = []

    # 유저 픽
    user_pick = _get_player_brief(sb, save_id, player_id)
    _draft_player(sb, save_id, user_team["id"], player_id)
    round_picks.append(
        {
            "team_name": user_team["team_name"],
            "logo": user_team["logo"],
            "is_user": True,
            "player": user_pick,
        }
    )

    # AI 픽
    remaining = (
        sb.table("dynasty_player")
        .select("id, name, positions, overall, potential")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .order("overall", desc=True)
        .limit(80)
        .execute()
        .data
    )

    shuffled_ai = list(ai_teams)
    random.shuffle(shuffled_ai)
    for team in shuffled_ai:
        if not remaining:
            break
        pool = remaining[: min(8, len(remaining))]
        pick = random.choice(pool)
        remaining.remove(pick)
        _draft_player(sb, save_id, team["id"], pick["id"])
        round_picks.append(
            {
                "team_name": team["team_name"],
                "logo": team["logo"],
                "is_user": False,
                "player": {
                    "name": pick["name"],
                    "positions": pick["positions"],
                    "overall": pick["overall"],
                    "potential": pick["potential"],
                },
            }
        )

    session[f"last_picks_{save_id}"] = {
        "round": current_round,
        "picks": round_picks,
    }

    picked_count = picked_count + len(round_picks)
    if picked_count >= DRAFT_ROUNDS * TEAM_COUNT:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    return redirect(url_for("dynasty.dynasty_draft", save_id=save_id))


def _get_player_brief(sb, save_id, player_id):
    p = (
        sb.table("dynasty_player")
        .select("name, positions, overall, potential")
        .eq("save_id", save_id)
        .eq("id", player_id)
        .execute()
        .data[0]
    )
    return {
        "name": p["name"],
        "positions": p["positions"],
        "overall": p["overall"],
        "potential": p["potential"],
    }


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
@require_auth
def dynasty_draft_finish(save_id):
    sb = get_supabase()

    session.pop(f"last_picks_{save_id}", None)

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
@require_auth
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


# =========================================
# 다음 주 진행
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/next", methods=["POST"])
@require_auth
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
@require_auth
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

# dynasty.py - Part3

# =========================================
# 다음 시즌 시작
# 성장/은퇴 → FA 시장 생성 → AI 트레이드 → AI FA 영입 → 신인 Import
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/next_season", methods=["POST"])
@require_auth
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

    # 1. 성장 / 노쇠 / 은퇴
    process_offseason_growth(save_id)

    # 2. FA 시장 생성 (자격 선수 로스터 해제)
    generate_fa_market(save_id)

    # 3. AI끼리 트레이드
    ai_auto_trades(save_id, max_trades=3)

    # 4. 신인 Import
    import_players_for_season(save_id, new_season)

    # 5. 팀 성적 초기화 + 시즌 갱신
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
@require_auth
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

    my_picks = _get_my_picks(sb, save_id, user_team["id"])
    last_picks = session.pop(f"last_picks_{save_id}", None)

    return render_template(
        "dynasty_draft.html",
        save=save,
        teams=teams,
        players=players,
        user_team=user_team,
        current_round=1,
        total_rounds=5,
        picked_count=0,
        my_picks=my_picks,
        last_picks=last_picks,
        rookie_mode=True,
    )


# =========================================
# 신인 드래프트 픽
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_pick", methods=["POST"])
@require_auth
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

    round_picks = []

    user_pick = _get_player_brief(sb, save_id, player_id)
    _draft_player(sb, save_id, user_team["id"], player_id)
    round_picks.append(
        {
            "team_name": user_team["team_name"],
            "logo": user_team["logo"],
            "is_user": True,
            "player": user_pick,
        }
    )

    remaining = (
        sb.table("dynasty_player")
        .select("id, name, positions, overall, potential")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .eq("appear_season", save["season"])
        .order("overall", desc=True)
        .limit(40)
        .execute()
        .data
    )

    shuffled_ai = list(ai_teams)
    random.shuffle(shuffled_ai)
    for team in shuffled_ai:
        if not remaining:
            break
        pool = remaining[: min(5, len(remaining))]
        pick = random.choice(pool)
        remaining.remove(pick)
        _draft_player(sb, save_id, team["id"], pick["id"])
        round_picks.append(
            {
                "team_name": team["team_name"],
                "logo": team["logo"],
                "is_user": False,
                "player": {
                    "name": pick["name"],
                    "positions": pick["positions"],
                    "overall": pick["overall"],
                    "potential": pick["potential"],
                },
            }
        )

    session[f"last_picks_{save_id}"] = {
        "round": 0,
        "picks": round_picks,
    }

    return redirect(url_for("dynasty.dynasty_rookie_draft", save_id=save_id))


# =========================================
# 신인 드래프트 종료 → AI FA 영입 → 시즌 시작
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_finish")
@require_auth
def dynasty_rookie_finish(save_id):
    sb = get_supabase()

    session.pop(f"last_picks_{save_id}", None)

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    # AI가 남은 FA 영입 (유저는 FA 화면에서 직접 영입 가능)
    ai_sign_fa(save_id)

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
@require_auth
def dynasty_delete(save_id):
    sb = get_supabase()

    sb.table("dynasty_roster").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_schedule").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_player").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_team").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_save").delete().eq("id", save_id).execute()

    session.pop(f"auth_{save_id}", None)

    return redirect(url_for("dynasty.dynasty_home"))
