# dynasty.py - Part1
# =========================================
# KBO Dynasty - Main Blueprint (최종 통합본)
# 비밀번호 보호 + 사이드바 드래프트 + 순위 역순 신인 드래프트
# + 일괄 시뮬 + FA/트레이드/역사 연동
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
from dynasty_game import simulate_week, simulate_rest_of_season
from dynasty_growth import process_offseason_growth
from dynasty_lineup import auto_generate_lineup
from dynasty_fa import generate_fa_market, reset_budgets, resolve_fa_bidding, release_surplus_players
from dynasty_trade import ai_auto_trades
from dynasty_history import record_season_history
from dynasty_utils import (
    get_supabase,
    AI_TEAM_POOL,
    calc_team_power,
    get_standings,
)

dynasty_bp = Blueprint("dynasty", __name__)

SEASON_WEEKS = 24
DRAFT_ROUNDS = 25
ROOKIE_ROUNDS = 5
TEAM_COUNT = 10


# =========================================
# 비밀번호 해시
# =========================================
def _hash_pw(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =========================================
# 접근 인증
# =========================================
def _is_authed(save_id):
    return session.get(f"auth_{save_id}") is True


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
# 공용 헬퍼
# =========================================
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


def _bulk_draft(sb, save_id, picks):
    player_ids = [p["id"] for _, p in picks]

    for i in range(0, len(player_ids), 100):
        sb.table("dynasty_player").update({"drafted": True}).in_(
            "id", player_ids[i : i + 100]
        ).execute()

    roster_rows = [
        {
            "save_id": save_id,
            "team_id": team_id,
            "player_id": p["id"],
            "role": "BENCH",
            "depth": 99,
        }
        for team_id, p in picks
    ]
    for i in range(0, len(roster_rows), 100):
        sb.table("dynasty_roster").insert(roster_rows[i : i + 100]).execute()


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


def _get_rookie_draft_order(sb, save_id, season):
    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_map = {t["id"]: t for t in teams}

    history = (
        sb.table("dynasty_history")
        .select("team_id, rank")
        .eq("save_id", save_id)
        .eq("season", season - 1)
        .order("rank", desc=True)
        .execute()
        .data
    )

    if history:
        order = [team_map[h["team_id"]] for h in history if h["team_id"] in team_map]
        seen = {t["id"] for t in order}
        order += [t for t in teams if t["id"] not in seen]
        return order

    standings = get_standings(teams)
    return list(reversed(standings))

# dynasty.py - Part2

# =========================================
# 창단 드래프트 화면
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
        rookie_done=False,
        draft_order=None,
        user_slot=0,
    )


# =========================================
# 창단 드래프트 - 유저 픽 + AI 픽 (일괄 처리)
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
        .select("id", count="exact")
        .eq("save_id", save_id)
        .execute()
    )
    picked_count = roster_rows.count or 0
    current_round = picked_count // TEAM_COUNT + 1

    if current_round > DRAFT_ROUNDS:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    round_picks = []
    bulk = []

    # 유저 픽
    user_pick = _get_player_brief(sb, save_id, player_id)
    user_pick["id"] = player_id
    bulk.append((user_team["id"], user_pick))
    round_picks.append(
        {
            "team_name": user_team["team_name"],
            "logo": user_team["logo"],
            "is_user": True,
            "player": user_pick,
        }
    )

    # AI 픽 (메모리에서 선정 → 일괄 반영)
    remaining = (
        sb.table("dynasty_player")
        .select("id, name, positions, overall, potential")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .eq("retired", False)
        .neq("id", player_id)
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
        bulk.append((team["id"], pick))
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

    _bulk_draft(sb, save_id, bulk)

    session[f"last_picks_{save_id}"] = {
        "round": current_round,
        "picks": round_picks,
    }

    picked_count = picked_count + len(bulk)
    if picked_count >= DRAFT_ROUNDS * TEAM_COUNT:
        return redirect(url_for("dynasty.dynasty_draft_finish", save_id=save_id))

    return redirect(url_for("dynasty.dynasty_draft", save_id=save_id))


# =========================================
# 창단 드래프트 종료 → 라인업 + 일정 생성
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

    from dynasty_event import get_recent_events
    events = get_recent_events(save_id)

    from dynasty_facility import upgrade_cost, MAX_LEVEL
    stadium_level = user_team.get("stadium_level") or 1
    facility_level = user_team.get("facility_level") or 1
    stadium_cost = upgrade_cost("stadium", stadium_level)
    facility_cost = upgrade_cost("facility", facility_level)
    
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
        events=events,
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
# 시즌 전체 일괄 진행
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/sim_all", methods=["POST"])
@require_auth
def dynasty_sim_all(save_id):
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

    simulate_rest_of_season(save_id, save["season"], save["week"])

    sb.table("dynasty_save").update(
        {"week": SEASON_WEEKS + 1}
    ).eq("id", save_id).execute()

    return redirect(url_for("dynasty.dynasty_season_end", save_id=save_id))


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
# 역사 기록 → 성장/은퇴 → FA 방출 → AI 트레이드 → 신인 Import
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

    # 1. 시즌 역사 기록 (성적 리셋 전!)
    record_season_history(save_id)

    # 1.5 팬 변동 + 예산 지급
    from dynasty_finance import update_fans, grant_season_budget
    update_fans(save_id)
    grant_season_budget(save_id)

    from dynasty_staff import init_staff_market, pay_staff_salaries, ai_hire_staff
    init_staff_market(save_id)
    pay_staff_salaries(save_id)
    ai_hire_staff(save_id)

    from dynasty_facility import ai_upgrade_facilities
    ai_upgrade_facilities(save_id)
    
    # 2. 성장 / 노쇠 / 은퇴
    process_offseason_growth(save_id)

    # 3. FA 시장 생성
    generate_fa_market(save_id)

    release_surplus_players(save_id)
    
    reset_budgets(save_id)

    # 4. AI끼리 트레이드
    ai_auto_trades(save_id, max_trades=3)

    from dynasty_training import ai_auto_training
    ai_auto_training(save_id)

    # 5. 신인 Import
    import_players_for_season(save_id, new_season)

    # 6. 팀 성적 초기화 + 시즌 갱신
    sb.table("dynasty_team").update(
        {"wins": 0, "losses": 0, "ties": 0}
    ).eq("save_id", save_id).execute()

    sb.table("dynasty_save").update(
        {"season": new_season, "week": 0}
    ).eq("id", save_id).execute()

    # 신인 드래프트 픽 카운터 초기화
    session[f"rookie_picked_{save_id}"] = 0
    session.pop(f"last_picks_{save_id}", None)

    return redirect(url_for("dynasty.dynasty_rookie_draft", save_id=save_id))


# =========================================
# 신인 드래프트 화면
# 전년도 순위 역순, 유저 차례 직전까지 AI 자동 픽
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

    order = _get_rookie_draft_order(sb, save_id, save["season"])
    user_team = next(t for t in order if t["is_user"])
    user_slot = next(i for i, t in enumerate(order) if t["is_user"])

    picked_count = session.get(f"rookie_picked_{save_id}", 0)

    def rookie_pool(select_str, limit=None):
        q = (
            sb.table("dynasty_player")
            .select(select_str)
            .eq("save_id", save_id)
            .eq("drafted", False)
            .eq("retired", False)
            .eq("appear_season", save["season"])
            .order("overall", desc=True)
        )
        if limit:
            q = q.limit(limit)
        return q.execute().data

    # 유저 차례 직전까지 AI 자동 픽 (일괄 반영)
    pre_picks = []
    bulk = []

    pool = rookie_pool("id, name, positions, overall, potential", limit=60)

    while picked_count < ROOKIE_ROUNDS * TEAM_COUNT:
        slot = picked_count % TEAM_COUNT
        if slot == user_slot:
            break
        if not pool:
            picked_count = ROOKIE_ROUNDS * TEAM_COUNT
            break

        team = order[slot]
        candidates = pool[: min(4, len(pool))]
        pick = random.choice(candidates)
        pool.remove(pick)

        bulk.append((team["id"], pick))
        pre_picks.append(
            {
                "team_name": team["team_name"],
                "logo": team["logo"],
                "is_user": False,
                "player": pick,
            }
        )
        picked_count += 1

    if bulk:
        _bulk_draft(sb, save_id, bulk)

    session[f"rookie_picked_{save_id}"] = picked_count

    # 직전 유저 픽 + 이번 AI 픽 병합 → 사이드바 로그
    last = session.pop(f"last_picks_{save_id}", None)
    if pre_picks:
        merged = (last["picks"] if last else []) + pre_picks
        last = {"round": picked_count // TEAM_COUNT + 1, "picks": merged}

    players = rookie_pool("*")

    teams_all = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    my_picks = _get_my_picks(sb, save_id, user_team["id"])

    draft_done = picked_count >= ROOKIE_ROUNDS * TEAM_COUNT or not players

    return render_template(
        "dynasty_draft.html",
        save=save,
        teams=teams_all,
        players=players,
        user_team=user_team,
        current_round=min(picked_count // TEAM_COUNT + 1, ROOKIE_ROUNDS),
        total_rounds=ROOKIE_ROUNDS,
        picked_count=picked_count,
        my_picks=my_picks,
        last_picks=last,
        rookie_mode=True,
        rookie_done=draft_done,
        draft_order=order,
        user_slot=user_slot,
    )


# =========================================
# 신인 드래프트 - 유저 픽
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

    order = _get_rookie_draft_order(sb, save_id, save["season"])
    user_team = next(t for t in order if t["is_user"])

    user_pick = _get_player_brief(sb, save_id, player_id)
    user_pick["id"] = player_id
    _bulk_draft(sb, save_id, [(user_team["id"], user_pick)])

    picked_count = session.get(f"rookie_picked_{save_id}", 0) + 1
    session[f"rookie_picked_{save_id}"] = picked_count

    session[f"last_picks_{save_id}"] = {
        "round": picked_count // TEAM_COUNT + 1,
        "picks": [
            {
                "team_name": user_team["team_name"],
                "logo": user_team["logo"],
                "is_user": True,
                "player": user_pick,
            }
        ],
    }

    return redirect(url_for("dynasty.dynasty_rookie_draft", save_id=save_id))


# =========================================
# 신인 드래프트 종료 → AI FA 영입 → 시즌 시작
# =========================================
# =========================================
# 신인 드래프트 종료 → FA 입찰 단계로 이동
# =========================================
@dynasty_bp.route("/dynasty/<int:save_id>/rookie_finish")
@require_auth
def dynasty_rookie_finish(save_id):
    session.pop(f"last_picks_{save_id}", None)
    session.pop(f"rookie_picked_{save_id}", None)

    return redirect(url_for("dynasty_fa.fa_bid", save_id=save_id))


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
    sb.table("dynasty_history").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_team").delete().eq("save_id", save_id).execute()
    sb.table("dynasty_save").delete().eq("id", save_id).execute()

    session.pop(f"auth_{save_id}", None)
    session.pop(f"rookie_picked_{save_id}", None)
    session.pop(f"last_picks_{save_id}", None)

    return redirect(url_for("dynasty.dynasty_home"))
