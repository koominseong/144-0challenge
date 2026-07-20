# gauntlet_routes.py
# =========================================
# 가을야구 업셋 런
# app.py 등록:
#   from gauntlet_routes import gauntlet_bp
#   app.register_blueprint(gauntlet_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from gauntlet import (
    create_run, init_run_db, suggest_entry, apply_entry,
    start_stage, collect_game, settle_stage, eliminate,
    market_pool, sign_player, proceed_to_stage, record_run,
    STAGES, MAX_SIGNINGS_PER_ROUND,
)

gauntlet_bp = Blueprint("gauntlet", __name__)


def _load(run_id):
    sb = get_supabase()
    row = sb.table("gauntlet_run").select("*").eq("id", run_id).execute().data
    return row[0] if row else None


def _save(run_id, state):
    sb = get_supabase()
    sb.table("gauntlet_run").update({"state": state}).eq("id", run_id).execute()


# ========== 홈 ==========
@gauntlet_bp.route("/gauntlet")
def g_home():
    sb = get_supabase()
    records = (
        sb.table("gauntlet_record").select("*")
        .order("id", desc=True).limit(15).execute().data
    )
    ongoing = (
        sb.table("gauntlet_run").select("id, state")
        .eq("finished", False).order("id", desc=True).limit(1).execute().data
    )
    return render_template("gauntlet_home.html",
                           records=records,
                           ongoing=ongoing[0] if ongoing else None)


# ========== 런 생성 ==========
@gauntlet_bp.route("/gauntlet/new")
def g_new():
    sb = get_supabase()
    state = create_run()
    if state is None:
        return redirect(url_for("gauntlet.g_home"))
    state = init_run_db(state)
    row = sb.table("gauntlet_run").insert({"state": state, "finished": False,
                                           "save_id": state["save_id"]}).execute().data[0]
    return redirect(url_for("gauntlet.g_play", run_id=row["id"]))


# ========== 메인 디스패처 (phase 분기) ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>")
def g_play(run_id):
    row = _load(run_id)
    if not row:
        return redirect(url_for("gauntlet.g_home"))
    state = row["state"]

    # 시리즈 중이면 경기 결과 회수 시도
    if state["phase"] == "series" and state.get("series"):
        outcome = collect_game(state)
        if outcome == "stage_clear":
            state = settle_stage(state)
        elif outcome == "eliminated":
            state = eliminate(state)
        elif outcome == "series_go":
            from gauntlet import next_game
            state = next_game(state)
        _save(run_id, state)
        if state["phase"] == "finished":
            return redirect(url_for("gauntlet.g_finish", run_id=run_id))

    phase = state["phase"]
    if phase == "manager_select":
        return render_template("gauntlet_manager.html", run_id=run_id, state=state)
    if phase == "entry":
        sug = suggest_entry(state)
        pmap = {p["id"]: p for p in state["players"]}
        return render_template("gauntlet_entry.html", run_id=run_id, state=state,
                               sug=sug, pmap=pmap,
                               players=sorted(state["players"],
                                              key=lambda p: (p["is_pitcher"], -p["overall"])))
    if phase == "market":
        q = request.args.get("q", "")
        pf = request.args.get("pos", "")
        pool = market_pool(state, query=q, pos_filter=pf)
        pmap = {p["id"]: p for p in state["players"]}
        entry_players = [pmap[pid] for pid in state["entry"] if pid in pmap]
        return render_template("gauntlet_market.html", run_id=run_id, state=state,
                               pool=pool, entry_players=entry_players,
                               q=q, pos=pf,
                               left=MAX_SIGNINGS_PER_ROUND - state.get("signed_this_round", 0),
                               next_stage=STAGES[state["stage_idx"]][1],
                               next_opp=state["opponents"][state["stage_idx"]])
    if phase == "series":
        return render_template("gauntlet_series.html", run_id=run_id, state=state,
                               sr=state["series"])
    if phase == "finished":
        return redirect(url_for("gauntlet.g_finish", run_id=run_id))
    return redirect(url_for("gauntlet.g_home"))


# ========== 감독 선택 ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>/manager", methods=["POST"])
def g_manager(run_id):
    row = _load(run_id)
    state = row["state"]
    idx = request.form.get("idx", type=int)
    if state["phase"] == "manager_select" and idx is not None and 0 <= idx < 3:
        state["manager"] = state["manager_cands"][idx]
        state["phase"] = "entry"
        _save(run_id, state)
    return redirect(url_for("gauntlet.g_play", run_id=run_id))


# ========== 엔트리 확정 (자동 추천 그대로 or 수정) ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>/entry", methods=["POST"])
def g_entry(run_id):
    row = _load(run_id)
    state = row["state"]
    if state["phase"] != "entry":
        return redirect(url_for("gauntlet.g_play", run_id=run_id))

    mode = request.form.get("mode", "auto")
    sug = suggest_entry(state)
    if mode == "auto":
        entry, lineup, rotation, closer = sug["entry"], sug["lineup"], sug["rotation"], sug["closer"]
    else:
        entry = [int(x) for x in request.form.getlist("entry")]
        lineup = [int(x) for x in request.form.getlist("lineup")]
        rotation = [int(x) for x in request.form.getlist("rotation")]
        closer = request.form.get("closer", type=int)
        if len(entry) != 28 or len(lineup) != 9 or not (3 <= len(rotation) <= 4):
            return redirect(url_for("gauntlet.g_play", run_id=run_id))

    state = apply_entry(state, entry, lineup, rotation, closer)
    state["phase"] = "series"
    state = start_stage(state)
    _save(run_id, state)
    return redirect(url_for("gauntlet.g_play", run_id=run_id))


# ========== 경기 진입 (live 직결) ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>/game")
def g_game(run_id):
    row = _load(run_id)
    state = row["state"]
    sr = state.get("series")
    if not sr or not sr.get("current_schedule_id"):
        return redirect(url_for("gauntlet.g_play", run_id=run_id))
    return redirect(url_for("dynasty_live.live_enter",
                            save_id=state["save_id"],
                            schedule_id=sr["current_schedule_id"]))


# ========== live 종료 후 복귀 훅 (save_id로 런 찾기) ==========
@gauntlet_bp.route("/gauntlet/return/<int:save_id>")
def g_return(save_id):
    sb = get_supabase()
    row = (sb.table("gauntlet_run").select("id")
           .eq("save_id", save_id).eq("finished", False)
           .order("id", desc=True).limit(1).execute().data)
    if not row:
        return redirect(url_for("gauntlet.g_home"))
    return redirect(url_for("gauntlet.g_play", run_id=row[0]["id"]))


# ========== 마켓 영입 / 진행 ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>/sign", methods=["POST"])
def g_sign(run_id):
    import json as _json
    row = _load(run_id)
    state = row["state"]
    if state["phase"] != "market":
        return redirect(url_for("gauntlet.g_play", run_id=run_id))

    payload = request.form.get("player_json")
    drop_pid = request.form.get("drop_pid", type=int)
    try:
        mp = _json.loads(payload)
    except Exception:
        return redirect(url_for("gauntlet.g_play", run_id=run_id))

    ok, msg = sign_player(state, mp, drop_pid)
    _save(run_id, state)
    return redirect(url_for("gauntlet.g_play", run_id=run_id, msg=msg))


@gauntlet_bp.route("/gauntlet/<int:run_id>/proceed", methods=["POST"])
def g_proceed(run_id):
    row = _load(run_id)
    state = row["state"]
    if state["phase"] == "market":
        state = proceed_to_stage(state)
        _save(run_id, state)
    return redirect(url_for("gauntlet.g_play", run_id=run_id))


# ========== 종료 화면 ==========
@gauntlet_bp.route("/gauntlet/<int:run_id>/finish")
def g_finish(run_id):
    sb = get_supabase()
    row = _load(run_id)
    state = row["state"]
    if not row["finished"]:
        record_run(state)
        sb.table("gauntlet_run").update({"finished": True, "state": state}).eq("id", run_id).execute()
    return render_template("gauntlet_finish.html", state=state)
