# dynasty_live_routes.py - 전체 교체본
# =========================================
# app.py 등록:
#   from dynasty_live_routes import live_bp
#   app.register_blueprint(live_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_live import (
    start_live_game, progress, load_context, user_side,
    offense_defense, win_prob,
)

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

    if g["played"] and not live_row["finished"]:
        return redirect(url_for("dynasty.dynasty_dashboard", save_id=save_id))

    if not live_row["finished"] and live_row["state"].get("pending") == "pregame":
        live_row = progress(save_id, live_row["id"])

    return _render(save_id, live_row)


@live_bp.route("/dynasty/<int:save_id>/live/<int:live_id>/action", methods=["POST"])
def live_action(save_id, live_id):
    action = request.form.get("action", "swing")
    ph_id = request.form.get("ph_id", type=int)
    rp_id = request.form.get("rp_id", type=int)
    slot = request.form.get("slot", type=int)
    live_row = progress(save_id, live_id, user_action=action, ph_id=ph_id, rp_id=rp_id, user_action_slot=slot)
    return _render(save_id, live_row)

def _render(save_id, live_row):
    sb = get_supabase()
    state = live_row["state"]
    ctx = load_context(save_id, state)

    home = ctx["team_map"][state["home_id"]]
    away = ctx["team_map"][state["away_id"]]
    us = user_side(state, ctx)
    off, def_ = offense_defense(state)

    base_names = []
    for rid in state["bases"]:
        base_names.append(ctx["players"][rid]["name"] if rid else None)

    cur_pitcher = None
    pk = "h_pitcher" if def_ == "home" else "a_pitcher"
    if state.get(pk):
        p = ctx["players"][state[pk]]
        outs_thrown = state["h_pit_outs" if def_ == "home" else "a_pit_outs"]
        cur_pitcher = {
            "id": p["id"], "name": p["name"], "overall": p["overall"],
            "ip": f"{outs_thrown // 3}.{outs_thrown % 3}",
        }

    cond = state.get("cond", {})

    def cond_mark(pid):
        c = cond.get(str(pid), 0)
        if c >= 2:
            return "🔥"
        if c <= -2:
            return "❄"
        return ""

    # 양팀 라인업 뷰
    def lineup_view(side):
        team = ctx[side]
        if not team or not team["batters"]:
            return []
        ok = "h_order" if side == "home" else "a_order"
        cur_slot = state[ok] % len(team["batters"])
        over = state.get("ph_over", {}).get(side, {})
        rows = []
        for i, p in enumerate(team["batters"]):
            shown = ctx["players"].get(over.get(str(i)), p)
            rows.append({
                "num": i + 1, "name": shown["name"], "overall": shown["overall"],
                "cond": cond_mark(shown["id"]),
                "at_bat": (i == cur_slot and side == off and state["pending"] != "finished"),
                "sub": str(i) in over,
            })
        return rows

    next_batter = None
    for r in lineup_view(off):
        if r["at_bat"]:
            next_batter = r

    used_ph = state.get("used_ph", [])
    bench = []
    rps = []
    if us:
        bench = [
            {"id": p["id"], "name": p["name"], "overall": p["overall"],
             "positions": p.get("positions") or "", "cond": cond_mark(p["id"])}
            for p in ctx[us].get("bench", []) if p["id"] not in used_ph
        ]
        cur_pid = state["h_pitcher" if us == "home" else "a_pitcher"]
        rps = [
            {"id": p["id"], "name": p["name"], "overall": p["overall"], "cond": cond_mark(p["id"])}
            for p in ctx[us]["rps"] if p["id"] != cur_pid
        ]

    # 박스스코어 (이 경기 기록이 있는 선수만)
    def boxscore(side):
        tid = state["home_id"] if side == "home" else state["away_id"]
        rows = []
        for k, v in state.get("acc", {}).items():
            if v.get("team_id") != tid:
                continue
            if not (v["hits"] or v["hr"] or v["rbi"] or v["sb"] or v["so"] or v["saves"]):
                continue
            rows.append(v)
        rows.sort(key=lambda v: (v["hits"] + v["hr"] * 2 + v["rbi"] + v["so"] * 0.4), reverse=True)
        return rows[:8]

    # 주루 판단 대상
    send_runner = None
    if state["pending"] == "running" and state.get("send_runner"):
        send_runner = ctx["players"][state["send_runner"]]["name"]

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
        away_lineup=lineup_view("away"),
        home_lineup=lineup_view("home"),
        bench=bench,
        rps=rps,
        cp_available=bool(us and ctx[us]["cp"] and not state["h_used_cp" if us == "home" else "a_used_cp"]),
        wp=win_prob(state, ctx),
        box_home=boxscore("home"),
        box_away=boxscore("away"),
        send_runner=send_runner,
        mvp=state.get("mvp"),
        highlights=state.get("hl", []),
        my_lineup=lineup_view(us) if us else [],
    )
