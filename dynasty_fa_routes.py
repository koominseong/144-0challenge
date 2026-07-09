# dynasty_fa_routes.py
# =========================================
# KBO Dynasty - FA 화면/라우트
# 별도 Blueprint (dynasty.py 수정 불필요)
# app.py에 아래 2줄 추가:
#   from dynasty_fa_routes import fa_bp
#   app.register_blueprint(fa_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_fa import get_fa_players, sign_fa_player
from dynasty_trade import trade_value

fa_bp = Blueprint("dynasty_fa", __name__)


# =========================================
# FA 시장 화면
# =========================================
@fa_bp.route("/dynasty/<int:save_id>/fa")
def fa_home(save_id):
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

    fa_players = get_fa_players(save_id)
    for p in fa_players:
        p["value"] = trade_value(p, save["season"])
        p["career_years"] = save["season"] - p["appear_season"] + 1

    fa_players.sort(key=lambda x: -x["value"])

    roster_count = (
        sb.table("dynasty_roster")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .eq("team_id", user_team["id"])
        .execute()
        .count
    )

    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "")

    return render_template(
        "dynasty_fa.html",
        save=save,
        user_team=user_team,
        fa_players=fa_players,
        roster_count=roster_count,
        msg=msg,
        ok=ok,
    )


# =========================================
# FA 영입 처리
# =========================================
@fa_bp.route("/dynasty/<int:save_id>/fa/sign", methods=["POST"])
def fa_sign(save_id):
    sb = get_supabase()

    player_id = int(request.form.get("player_id"))

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    success, message = sign_fa_player(save_id, user_team["id"], player_id)

    return redirect(
        url_for(
            "dynasty_fa.fa_home",
            save_id=save_id,
            msg=message,
            ok="1" if success else "0",
        )
    )
