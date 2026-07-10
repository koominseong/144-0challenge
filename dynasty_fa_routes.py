# dynasty_fa_routes.py
# =========================================
# KBO Dynasty - FA 입찰 화면/라우트 (입찰 방식)
# app.py에 아래 2줄 (이미 등록했으면 그대로):
#   from dynasty_fa_routes import fa_bp
#   app.register_blueprint(fa_bp)
#
# 흐름: 신인 드래프트 종료 → /fa_bid (입찰 입력)
#       → 제출 → 결과 화면 → 시즌 시작
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_fa import get_fa_players, fa_base_price, resolve_fa_bidding
from dynasty_lineup import auto_generate_lineup
from dynasty_schedule import generate_schedule

fa_bp = Blueprint("dynasty_fa", __name__)

SEASON_WEEKS = 24


# =========================================
# FA 입찰 화면
# =========================================
@fa_bp.route("/dynasty/<int:save_id>/fa_bid")
def fa_bid(save_id):
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
    team_map = {t["id"]: t for t in teams}
    user_team = next(t for t in teams if t["is_user"])

    fa_players = get_fa_players(save_id)

    for p in fa_players:
        p["base_price"] = fa_base_price(p, save["season"])
        p["career_years"] = save["season"] - p["appear_season"] + 1
        ft = p.get("fa_from_team")
        p["from_team"] = team_map.get(ft) if ft else None
        p["is_my_fa"] = ft == user_team["id"]

    fa_players.sort(key=lambda x: -x["overall"])

    return render_template(
        "dynasty_fa_bid.html",
        save=save,
        user_team=user_team,
        fa_players=fa_players,
        budget=user_team.get("budget") or 0,
        results=None,
    )


# =========================================
# FA 입찰 제출 → 일괄 판정 → 결과 화면
# =========================================
@fa_bp.route("/dynasty/<int:save_id>/fa_bid/submit", methods=["POST"])
def fa_bid_submit(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    # 폼에서 bid_<player_id> 형태로 수집
    user_bids = {}
    for key, value in request.form.items():
        if not key.startswith("bid_"):
            continue
        value = value.strip()
        if not value:
            continue
        try:
            pid = int(key[4:])
            amount = int(value)
        except ValueError:
            continue
        if amount > 0:
            user_bids[pid] = amount

    results = resolve_fa_bidding(save_id, user_bids)

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    return render_template(
        "dynasty_fa_bid.html",
        save=save,
        user_team=user_team,
        fa_players=None,
        budget=user_team.get("budget") or 0,
        results=results,
    )


# =========================================
# FA 종료 → 라인업 + 일정 생성 → 시즌 시작
# =========================================
@fa_bp.route("/dynasty/<int:save_id>/fa_bid/start_season", methods=["POST"])
def fa_start_season(save_id):
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
