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
    ph_id = request.form.get("ph_id", type=int)
    live_row = progress(save_id, live_id, user_action=action, ph_id=ph_id)
    return _render(save_id, live_row)


def _render(save_id, live_row):
    sb = get_supabase()
    state = live_row["state"]
    ctx = load_context(save_id, state)

    home = ctx["team_map"][state["home_id"]]
    away = ctx["team_map"][state["away_id"]]
    us = user_side(state, ctx)

    base_names = []
    for rid in state["bases"]:
        base_names.append(ctx["players"][rid]["name"] if rid else None)

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

    # 양팀 라인업 (대타 오버라이드 반영 + 현재 타순 표시)
    def lineup_view(side):
        team = ctx[side]
        if not team:
            return []
        ok = "h_order" if side == "home" else "a_order"
        cur_slot = state[ok] % len(team["batters"]) if team["batters"] else -1
        over = state.get("ph_over", {}).get(side, {})
        rows = []
        for i, p in enumerate(team["batters"]):
            shown = ctx["players"].get(over.get(str(i)), p)
            rows.append({
                "num": i + 1, "name": shown["name"], "overall": shown["overall"],
                "positions": shown.get("positions") or "",
                "at_bat": (i == cur_slot and side == off),
                "sub": str(i) in over,
            })
        return rows

    next_batter = None
    lv = lineup_view(off)
    for r in lv:
        if r["at_bat"]:
            next_batter = {"name": r["name"], "overall": r["overall"]}

    # 유저 벤치 (미사용 대타만)
    used_ph = state.get("used_ph", [])
    bench = []
    if us:
        bench = [p for p in ctx[us].get("bench", []) if p["id"] not in used_ph]

    save = sb.table("dynasty_save").select("*").eq("id", save_id).execute().data[0]

    return render_template(
        "dynasty_live.html",
        save=save,
        live=live_row,
        state=state,
        home=home,
        away=away,
        user_team=home if us == "home" else away,
        user_is_offense=(us == off),
        base_names=base_names,
        cur_pitcher=cur_pitcher,
        next_batter=next_batter,
        can_steal=bool(state["bases"][0] and not state["bases"][1]),
        away_lineup=lineup_view("away"),
        home_lineup=lineup_view("home"),
        away_pitchers=ctx["away"]["sps"] + ctx["away"]["rps"] + ([ctx["away"]["cp"]] if ctx["away"]["cp"] else []),
        home_pitchers=ctx["home"]["sps"] + ctx["home"]["rps"] + ([ctx["home"]["cp"]] if ctx["home"]["cp"] else []),
        bench=bench,
    )
