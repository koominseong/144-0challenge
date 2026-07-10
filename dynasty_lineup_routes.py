# dynasty_lineup_routes.py
# =========================================
# KBO Dynasty - 라인업 수동 편집 (1군/2군 체제)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup

lineup_bp = Blueprint("dynasty_lineup", __name__)

ROLE_ORDER = {"START": 0, "SP": 1, "CP": 2, "RP": 3, "BENCH": 4, "MINOR": 5}


@lineup_bp.route("/dynasty/<int:save_id>/lineup")
def lineup_home(save_id):
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
        .select("id, role, depth, dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", user_team["id"])
        .execute()
        .data
    )

    roster = []
    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        roster.append(
            {
                "roster_id": r["id"],
                "player_id": p["id"],   
                "role": r["role"],
                "depth": r["depth"],
                "name": p["name"],
                "positions": p["positions"],
                "overall": p["overall"],
                "potential": p["potential"],
            }
        )

    roster.sort(key=lambda x: (ROLE_ORDER.get(x["role"], 9), x["depth"]))

    starters = [r for r in roster if r["role"] == "START"]
    sps = [r for r in roster if r["role"] == "SP"]
    cps = [r for r in roster if r["role"] == "CP"]
    rps = [r for r in roster if r["role"] == "RP"]
    bench = [r for r in roster if r["role"] == "BENCH"]
    minors = [r for r in roster if r["role"] == "MINOR"]

    # 어떤 역할에도 안 잡힌 선수 방어 (구버전 depth=99 BENCH 등)
    known = {"START", "SP", "CP", "RP", "BENCH", "MINOR"}
    others = [r for r in roster if r["role"] not in known]
    minors = minors + others

    first_team_count = len(starters) + len(sps) + len(cps) + len(rps) + len(bench)

    msg = request.args.get("msg", "")

    return render_template(
        "dynasty_lineup.html",
        save=save,
        user_team=user_team,
        starters=starters,
        sps=sps,
        cps=cps,
        rps=rps,
        bench=bench,
        minors=minors,
        first_team_count=first_team_count,
        total_count=len(roster),
        msg=msg,
    )


@lineup_bp.route("/dynasty/<int:save_id>/lineup/set_role", methods=["POST"])
def lineup_set_role(save_id):
    sb = get_supabase()

    roster_id = int(request.form.get("roster_id"))
    new_role = request.form.get("role", "MINOR")

    if new_role not in ("START", "SP", "CP", "RP", "BENCH", "MINOR"):
        new_role = "MINOR"

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    same_role = (
        sb.table("dynasty_roster")
        .select("depth")
        .eq("save_id", save_id)
        .eq("team_id", user_team["id"])
        .eq("role", new_role)
        .execute()
        .data
    )
    max_depth = max([r["depth"] for r in same_role], default=0)

    sb.table("dynasty_roster").update(
        {"role": new_role, "depth": max_depth + 1}
    ).eq("id", roster_id).execute()

    return redirect(url_for("dynasty_lineup.lineup_home", save_id=save_id))


@lineup_bp.route("/dynasty/<int:save_id>/lineup/auto", methods=["POST"])
def lineup_auto(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    user_team = next(t for t in teams if t["is_user"])

    auto_generate_lineup(save_id, user_team["id"])

    return redirect(
        url_for(
            "dynasty_lineup.lineup_home",
            save_id=save_id,
            msg="자동 라인업이 생성되었습니다.",
        )
    )
