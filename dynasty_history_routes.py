# dynasty_history_routes.py
# =========================================
# KBO Dynasty - 역사 화면/라우트
# app.py에 아래 2줄 추가:
#   from dynasty_history_routes import history_bp
#   app.register_blueprint(history_bp)
# =========================================

from flask import Blueprint, render_template

from dynasty_utils import get_supabase
from dynasty_history import get_history, get_title_counts

history_bp = Blueprint("dynasty_history", __name__)


# =========================================
# 역사 화면
# =========================================
@history_bp.route("/dynasty/<int:save_id>/history")
def history_home(save_id):
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

    history = get_history(save_id)
    titles = get_title_counts(save_id)

    from dynasty_award import get_awards
    awards_rows = get_awards(save_id)
    awards_by_season = {}
    for a in awards_rows:
        awards_by_season.setdefault(a["season"], []).append(a)

    return render_template(
        "dynasty_history.html",
        save=save,
        user_team=user_team,
        history=history,
        titles=titles,
        awards_by_season=awards_by_season,
    )
