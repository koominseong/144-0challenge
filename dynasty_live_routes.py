# dynasty_live_routes.py
# =========================================
# app.py 등록:
#   from dynasty_live_routes import live_bp
#   app.register_blueprint(live_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_live import start_live_game, progress, load_context, user_side

live_bp = Blueprint("dynasty_live", __name__)


@live_bp.route("/dynasty/<int:save_id>/live/<int:schedule_id>")
def live_enter(save_id, schedule_id):
    sb = get_supabase()

    g = (
        sb.table("dynasty_schedule")
        .select("played")
        .eq("id", schedule_id)
        .execute()
        .data[0]
    )
    live_row = start_live_game(save_id, schedule_id)

    # 이미 자동 시뮬로 끝난 경기 방어
    if g["played"] and not live_row["finished"]:
        return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))

    # 첫 진입이면 결정 포인트까지 자동 진행
    if not live_row["finished"] and live_row["state"].get("pending") == "pregame":
        live_row = progress(save_id, live_row["id"])

    return _render(save_id, live_row)


@live_bp.route("/dynasty/<int:save_id>/live/<int:live_id>/action", methods=["POST"])
def live_action(save_id, live_id):
    action = request.form.get("action", "swing")
    live_row = progress(save_id, live_id, user_action=action)
    return _render(save_id, live_row)


def _render(save_id, live_row):
    sb = get_supabase()
    state = live_row["state"]
    ctx = load_context(save_id, state)

    home = ctx["team_map"][state["home_id"]]
    away = ctx["team_map"][state["away_id"]]
    us = user_side(state, ctx)

    # 주자 이름
    base_names = []
    for rid in state["bases"]:
        base_names.append(ctx["players"][rid]["name"] if rid else None)

    # 현재 투수/타자 정보 (결정 화면용)
    off = "away" if state["half"] == "top" else "home"
    def_ = "home" if off == "away" else "away"

    cur_pitcher = None
    pk = "h_pitcher" if def_ == "home" else "a_pitcher"
    if state.get(pk):
        p = ctx["players"][state[pk]]
        outs_thrown = state["h_pit_outs" if def_ == "home" else "a_pit_outs"]
        cur_pitcher = {
            "name": p["name"], "overall": p["overall"],
            "ip": f"{outs_thrown // 3}.{outs_thrown % 3}",
        }

    next_batter = None
    if ctx[off] and ctx[off]["batters"]:
        ok = "h_order" if off == "home" else "a_order"
        b = ctx[off]["batters"][state[ok] % len(ctx[off]["batters"])]
        next_batter = {"name": b["name"], "overall": b["overall"]}

    save = sb.table("dynasty_save").select("*").eq("id", save_id).execute().data[0]

    return render_template(
        "dynasty_live.html",
        save=save,
        live=live_row,
        state=state,
        home=home,
        away=away,
        user_team=home if us == "home" else away,
        base_names=base_names,
        cur_pitcher=cur_pitcher,
        next_batter=next_batter,
        can_steal=bool(state["bases"][0] and not state["bases"][1]),
    )
