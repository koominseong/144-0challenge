# dynasty_postseason_routes.py
# =========================================
# app.py 등록:
#   from dynasty_postseason_routes import ps_bp
#   app.register_blueprint(ps_bp)
# =========================================

from flask import Blueprint, render_template, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_postseason import (
    ensure_postseason, get_series_list, play_next_game,
    is_postseason_done, ROUND_KR, ROUND_WINS,
)

ps_bp = Blueprint("dynasty_ps", __name__)


@ps_bp.route("/dynasty/<int:save_id>/postseason")
def ps_home(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("*").eq("id", save_id).execute().data[0]

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    team_map = {t["id"]: t for t in teams}
    user_team = next(t for t in teams if t["is_user"])

    ensure_postseason(save_id, save["season"])

    series = get_series_list(save_id, save["season"])
    for s in series:
        s["round_kr"] = ROUND_KR[s["round"]]
        s["need"] = ROUND_WINS[s["round"]]
        s["ta"] = team_map.get(s["team_a"])
        s["tb"] = team_map.get(s["team_b"])
        s["w"] = team_map.get(s["winner"]) if s["winner"] else None

    done = is_postseason_done(save_id, save["season"])
    champion = team_map.get(save.get("ks_champion")) if done else None

    return render_template(
        "dynasty_postseason.html",
        save=save,
        user_team=user_team,
        series=series,
        done=done,
        champion=champion,
    )


@ps_bp.route("/dynasty/<int:save_id>/postseason/next", methods=["POST"])
def ps_next(save_id):
    sb = get_supabase()
    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    play_next_game(save_id, save["season"])

    return redirect(url_for("dynasty_ps.ps_home", save_id=save_id))
