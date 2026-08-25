# scout_routes.py
# =========================================
# 스카우트 블라인드 테스트
# app.py 등록:
#   from scout_routes import scout_bp
#   app.register_blueprint(scout_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from scout import create_round, advance, score_round, ROUNDS

scout_bp = Blueprint("scout", __name__)


@scout_bp.route("/scout")
def scout_home():
    sb = get_supabase()
    records = (
        sb.table("scout_record")
        .select("*")
        .order("total", desc=True)
        .limit(50)
        .execute()
        .data
    )
    return render_template("scout_home.html", records=records)


@scout_bp.route("/scout/new")
def scout_new():
    sb = get_supabase()
    state = create_round()
    if state is None:
        return redirect(url_for("scout.scout_home"))

    state = advance(state)  # 유저가 선픽이 아니면 AI 먼저 진행

    row = (
        sb.table("scout_game")
        .insert({"state": state, "finished": False})
        .execute()
        .data[0]
    )
    return redirect(url_for("scout.scout_play", game_id=row["id"]))


@scout_bp.route("/scout/<int:game_id>")
def scout_play(game_id):
    sb = get_supabase()
    row = sb.table("scout_game").select("*").eq("id", game_id).execute().data
    if not row:
        return redirect(url_for("scout.scout_home"))
    row = row[0]
    state = row["state"]

    if state.get("done"):
        return redirect(url_for("scout.scout_reveal", game_id=game_id))

    return _render_play(row)


@scout_bp.route("/scout/<int:game_id>/pick", methods=["POST"])
def scout_pick(game_id):
    sb = get_supabase()
    cid = request.form.get("cid", type=int)

    row = sb.table("scout_game").select("*").eq("id", game_id).execute().data[0]
    state = row["state"]
    if state.get("done"):
        return redirect(url_for("scout.scout_reveal", game_id=game_id))

    state = advance(state, user_cid=cid)
    sb.table("scout_game").update({"state": state}).eq("id", game_id).execute()

    if state.get("done"):
        return redirect(url_for("scout.scout_reveal", game_id=game_id))
    return redirect(url_for("scout.scout_play", game_id=game_id))


@scout_bp.route("/scout/<int:game_id>/reveal")
def scout_reveal(game_id):
    sb = get_supabase()
    row = sb.table("scout_game").select("*").eq("id", game_id).execute().data[0]
    state = row["state"]
    if not state.get("done"):
        return redirect(url_for("scout.scout_play", game_id=game_id))

    result = score_round(state)

    # 최초 1회만 기록 저장
    if not row["finished"]:
        try:
            sb.table("scout_record").insert({
                "year": state["year"],
                "grade": result["grade"],
                "place": result["place"],
                "total": result["results"]["user"]["total"],
                "picks": result["results"]["user"]["detail"],
            }).execute()
        except Exception as ex:
            print(f"[scout] 기록 저장 skip: {ex}")
        sb.table("scout_game").update({"finished": True}).eq("id", game_id).execute()

    # 전체 선수 WAR 순위표 (지명자 표시 포함)
    seat_names = {"user": "🙋 나", "ai1": "🦉 베테랑", "ai2": "📋 정석파", "ai3": "🎲 도박사"}
    picked_by = {}
    for seat, picks in state["picks"].items():
        for cid in picks:
            picked_by[cid] = seat_names[seat]

    full_ranking = sorted(state["cards"], key=lambda c: -c["war"])
    ranking = [{
        "rank": i + 1,
        "name": c["name"], "team": c["team"], "positions": c["positions"],
        "war": c["war"], "hint": c["hint"],
        "owner": picked_by.get(c["cid"]),
        "mine": picked_by.get(c["cid"]) == "🙋 나",
    } for i, c in enumerate(full_ranking)]

    return render_template(
        "scout_result.html",
        year=state["year"],
        result=result,
        user=result["results"]["user"],
        ais=[
            {"label": "🦉 베테랑", **result["results"]["ai1"]},
            {"label": "📋 정석파", **result["results"]["ai2"]},
            {"label": "🎲 도박사", **result["results"]["ai3"]},
        ],
        ranking=ranking,
        seat_names=seat_names,
    )


def _render_play(row):
    from scout import current_round
    state = row["state"]
    taken_map = {}
    for seat, picks in state["picks"].items():
        for cid in picks:
            taken_map[cid] = seat

    rnd = current_round(state)

    cards = []
    for c in state["cards"]:
        if c["wave"] > rnd:
            continue  # 미공개 웨이브
        cards.append({
            "cid": c["cid"],
            "hint": c["hint"],
            "positions": c["positions"],
            "wave": c["wave"],
            "new": c["wave"] == rnd,
            "taken": c["cid"] in taken_map,
            "mine": taken_map.get(c["cid"]) == "user",
        })

    my_picks = [next(c for c in state["cards"] if c["cid"] == cid)
                for cid in state["picks"]["user"]]

    # 내 드래프트 순번 (1라운드 기준 몇 번째인지)
    my_slot = state["order"][:4].index("user") + 1

    return render_template(
        "scout_game.html",
        game_id=row["id"],
        year=state["year"],
        cards=cards,
        my_round=len(state["picks"]["user"]) + 1,
        total_rounds=ROUNDS,
        my_slot=my_slot,
        my_picks=[{"hint": c["hint"], "positions": c["positions"]} for c in my_picks],
    )
