# dynasty_staff_routes.py
# =========================================
# KBO Dynasty - 감독/코치 화면/라우트
# app.py에 등록:
#   from dynasty_staff_routes import staff_bp
#   app.register_blueprint(staff_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_staff import (
    init_staff_market,
    hire_staff,
    STYLE_DESC,
    GRADE_SIM,
    GRADE_GROWTH,
)

staff_bp = Blueprint("dynasty_staff", __name__)

ROLE_KR = {"MANAGER": "감독", "HITTING": "타격코치", "PITCHING": "투수코치"}


# =========================================
# 코칭스태프 화면 (내 스태프 + 시장)
# =========================================
@staff_bp.route("/dynasty/<int:save_id>/staff")
def staff_home(save_id):
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
    team_map = {t["id"]: t for t in teams}
    user_team = next(t for t in teams if t["is_user"])

    # 시장이 비어있으면 초기화 (첫 진입 대비)
    init_staff_market(save_id)

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    for s in staff:
        s["role_kr"] = ROLE_KR.get(s["role"], s["role"])
        s["style_desc"] = STYLE_DESC.get(s["style"]) if s["style"] else None
        if s["role"] == "MANAGER":
            s["effect"] = f"전력 +{GRADE_SIM[s['grade']] * 100:.0f}%"
        else:
            s["effect"] = f"성장 +{GRADE_GROWTH[s['grade']]}"
        s["team"] = team_map.get(s["team_id"]) if s["team_id"] else None

    mine = [s for s in staff if s["team_id"] == user_team["id"]]
    market = [s for s in staff if s["team_id"] is None]
    others = [s for s in staff if s["team_id"] and s["team_id"] != user_team["id"]]

    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    role_order = {"MANAGER": 0, "HITTING": 1, "PITCHING": 2}
    market.sort(key=lambda s: (role_order[s["role"]], grade_order[s["grade"]]))
    mine.sort(key=lambda s: role_order[s["role"]])
    others.sort(key=lambda s: (s["team_id"], role_order[s["role"]]))

    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "")

    return render_template(
        "dynasty_staff.html",
        save=save,
        user_team=user_team,
        mine=mine,
        market=market,
        others=others,
        budget=user_team.get("budget") or 0,
        msg=msg,
        ok=ok,
    )


# =========================================
# 영입
# =========================================
@staff_bp.route("/dynasty/<int:save_id>/staff/hire", methods=["POST"])
def staff_hire(save_id):
    sb = get_supabase()

    staff_id = int(request.form.get("staff_id"))

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    success, message = hire_staff(save_id, user_team["id"], staff_id)

    return redirect(
        url_for(
            "dynasty_staff.staff_home",
            save_id=save_id,
            msg=message,
            ok="1" if success else "0",
        )
    )
