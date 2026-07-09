# dynasty_trade_routes.py
# =========================================
# KBO Dynasty - 트레이드 화면/라우트
# 별도 Blueprint (dynasty.py 수정 불필요)
# app.py에 아래 2줄 추가:
#   from dynasty_trade_routes import trade_bp
#   app.register_blueprint(trade_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_trade import propose_trade, trade_value

trade_bp = Blueprint("dynasty_trade", __name__)


# =========================================
# 트레이드 화면
# =========================================
@trade_bp.route("/dynasty/<int:save_id>/trade")
def trade_home(save_id):
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
    ai_teams = [t for t in teams if not t["is_user"]]

    target_id = request.args.get("target", type=int)
    if target_id is None:
        target_id = ai_teams[0]["id"]
    target_team = next(
        (t for t in ai_teams if t["id"] == target_id), ai_teams[0]
    )
    target_id = target_team["id"]

    my_roster = _get_roster_with_value(sb, save_id, user_team["id"], save["season"])
    their_roster = _get_roster_with_value(sb, save_id, target_id, save["season"])

    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "")

    return render_template(
        "dynasty_trade.html",
        save=save,
        user_team=user_team,
        ai_teams=ai_teams,
        target_team=target_team,
        my_roster=my_roster,
        their_roster=their_roster,
        msg=msg,
        ok=ok,
    )


# =========================================
# 트레이드 제안 처리
# =========================================
@trade_bp.route("/dynasty/<int:save_id>/trade/propose", methods=["POST"])
def trade_propose(save_id):
    sb = get_supabase()

    target_id = int(request.form.get("target_team_id"))
    my_ids = [int(x) for x in request.form.getlist("my_players")]
    their_ids = [int(x) for x in request.form.getlist("their_players")]

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    success, message = propose_trade(
        save_id, user_team["id"], target_id, my_ids, their_ids
    )

    return redirect(
        url_for(
            "dynasty_trade.trade_home",
            save_id=save_id,
            target=target_id,
            msg=message,
            ok="1" if success else "0",
        )
    )


# =========================================
# 로스터 + 트레이드 가치 조회
# =========================================
def _get_roster_with_value(sb, save_id, team_id, season):
    rows = (
        sb.table("dynasty_roster")
        .select("role, depth, dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .order("depth")
        .execute()
        .data
    )

    result = []
    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        item = dict(p)
        item["role"] = r["role"]
        item["value"] = trade_value(p, season)
        result.append(item)

    result.sort(key=lambda x: -x["value"])
    return result
