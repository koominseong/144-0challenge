# dynasty_training_routes.py
# =========================================
# KBO Dynasty - 육성 화면/라우트
# app.py에 등록:
#   from dynasty_training_routes import training_bp
#   app.register_blueprint(training_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_training import train_player, trainable_stats, TRAINING_COST

training_bp = Blueprint("dynasty_training", __name__)


@training_bp.route("/dynasty/<int:save_id>/training")
def training_home(save_id):
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

    rows = (
        sb.table("dynasty_roster")
        .select("dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", user_team["id"])
        .eq("role", "MINOR")
        .execute()
        .data
    )

    minors = []
    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        p["trained"] = p.get("trained_season") == save["season"]
        p["stats_options"] = trainable_stats(p)
        p["career_years"] = save["season"] - p["appear_season"] + 1
        minors.append(p)

    minors.sort(key=lambda x: -(x["potential"] or x["overall"]))

    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "")

    return render_template(
        "dynasty_training.html",
        save=save,
        user_team=user_team,
        minors=minors,
        budget=user_team.get("budget") or 0,
        cost=TRAINING_COST,
        msg=msg,
        ok=ok,
    )


@training_bp.route("/dynasty/<int:save_id>/training/run", methods=["POST"])
def training_run(save_id):
    sb = get_supabase()

    player_id = int(request.form.get("player_id"))
    stat = request.form.get("stat", "")

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    success, message = train_player(save_id, user_team["id"], player_id, stat)

    return redirect(
        url_for(
            "dynasty_training.training_home",
            save_id=save_id,
            msg=message,
            ok="1" if success else "0",
        )
    )
