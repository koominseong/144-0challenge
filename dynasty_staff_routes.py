# dynasty_staff_routes.py
# =========================================
# app.py 등록:
#   from dynasty_staff_routes import staff_bp
#   app.register_blueprint(staff_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_staff import (
    init_staff_market, hire_staff, fire_staff,
    STYLE_DESC, TRAIT_DESC, PERSON_SYNERGY, GROUP_SYNERGY, ROLE_KR,
    GRADE_SIM, GRADE_GROWTH,
)

staff_bp = Blueprint("dynasty_staff", __name__)

ROLE_ORDER = {"MANAGER": 0, "HEAD": 1, "HITTING": 2, "PITCHING": 3, "DEFENSE": 4,
              "BULLPEN": 5, "BASERUN": 6, "BATTERY": 7}


@staff_bp.route("/dynasty/<int:save_id>/staff")
def staff_home(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("*").eq("id", save_id).execute().data[0]

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    team_map = {t["id"]: t for t in teams}
    user_team = next(t for t in teams if t["is_user"])

    init_staff_market(save_id)

    staff = sb.table("dynasty_staff").select("*").eq("save_id", save_id).execute().data
    staff_by_name = {s["name"]: s for s in staff}

    for s in staff:
        s["role_kr"] = ROLE_KR.get(s["role"], s["role"])
        s["style_desc"] = STYLE_DESC.get(s["style"]) if s["style"] else None
        s["trait_desc"] = TRAIT_DESC.get(s.get("trait")) if s.get("trait") else None
        if s["role"] == "MANAGER":
            s["effect"] = f"전력 +{GRADE_SIM[s['grade']] * 100:.0f}%"
        elif s["role"] in ("HITTING", "PITCHING"):
            s["effect"] = f"성장 +{GRADE_GROWTH[s['grade']]}"
        else:
            s["effect"] = "등급 비례 효과"
        s["team"] = team_map.get(s["team_id"]) if s["team_id"] else None
        s["disp_name"] = s["name"].rstrip("2")

        # 이 인물이 얽힌 듀오 시너지
        duos = []
        for (mg, ch), (title, desc, _fx) in PERSON_SYNERGY.items():
            if s["name"] == ch and s["role"] != "MANAGER":
                duos.append(f"「{title}」 {mg} 감독과 — {desc}")
            elif s["name"] == mg and s["role"] == "MANAGER":
                duos.append(f"「{title}」 {ch.rstrip('2')} 코치와 — {desc}")
        # 이 인물이 포함된 단체 시너지
        for g in GROUP_SYNERGY:
            if s["name"] in g["members"]:
                duos.append(f"「{g['title']}」 [{len(g['members'])}인 단체] — {g['desc']}")
        s["duo_list"] = duos

    mine = [s for s in staff if s["team_id"] == user_team["id"]]
    market = [s for s in staff if s["team_id"] is None]
    others = [s for s in staff if s["team_id"] and s["team_id"] != user_team["id"]]

    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    market.sort(key=lambda s: (ROLE_ORDER.get(s["role"], 9), grade_order[s["grade"]]))
    mine.sort(key=lambda s: ROLE_ORDER.get(s["role"], 9))
    others.sort(key=lambda s: (s["team_id"], ROLE_ORDER.get(s["role"], 9)))

    my_manager = next((s for s in mine if s["role"] == "MANAGER"), None)
    my_names = {s["name"] for s in mine}

    # ----- 발동 중 시너지 (듀오 + 단체) -----
    synergies = []
    if my_manager:
        for s in mine:
            duo = PERSON_SYNERGY.get((my_manager["name"], s["name"]))
            if duo:
                synergies.append({"coach": s["disp_name"], "name": duo[0], "desc": duo[1]})
    for g in GROUP_SYNERGY:
        if set(g["members"]).issubset(my_names):
            synergies.append({
                "coach": " · ".join(n.rstrip("2") for n in g["members"]),
                "name": g["title"] + f" [{len(g['members'])}인]",
                "desc": g["desc"],
            })

    # ----- 시장 궁합 배지 -----
    for s in market:
        s["duo_hint"] = None
        if my_manager and s["role"] != "MANAGER":
            duo = PERSON_SYNERGY.get((my_manager["name"], s["name"]))
            if duo:
                s["duo_hint"] = duo[0]
        elif s["role"] == "MANAGER":
            cnt = sum(1 for c in mine if (s["name"], c["name"]) in PERSON_SYNERGY)
            if cnt:
                s["duo_hint"] = f"보유 코치와 시너지 {cnt}건"
        if not s["duo_hint"]:
            # 단체 진행도 배지: 이 인물 영입 시 2인 이상 모이는 단체
            for g in GROUP_SYNERGY:
                if s["name"] in g["members"]:
                    got = len(set(g["members"]) & my_names)
                    if got >= 1:
                        s["duo_hint"] = f"{g['title']} {got + 1}/{len(g['members'])}"
                        break

    # ----- 듀오 도감 -----
    codex = []
    for (mg, ch), (title, desc, _fx) in PERSON_SYNERGY.items():
        m = staff_by_name.get(mg)
        c = staff_by_name.get(ch)
        if my_manager and mg == my_manager["name"] and ch in my_names:
            status = "active"
        elif my_manager and mg == my_manager["name"] and c and c["team_id"] is None:
            status = "possible"
        else:
            status = "other"
        codex.append({
            "manager": mg, "coach": ch.rstrip("2"),
            "coach_role": ROLE_KR.get(c["role"], "?") if c else "?",
            "title": title, "desc": desc, "status": status,
            "m_where": (team_map.get(m["team_id"], {}).get("team_name") if m and m["team_id"] else "시장") if m else "-",
            "c_where": (team_map.get(c["team_id"], {}).get("team_name") if c and c["team_id"] else "시장") if c else "-",
        })
    status_order = {"active": 0, "possible": 1, "other": 2}
    codex.sort(key=lambda x: (status_order[x["status"]], x["manager"]))

    # ----- 단체 도감 (멤버별 상태 + 진행도) -----
    group_codex = []
    for g in GROUP_SYNERGY:
        members = []
        got = 0
        obtainable = 0
        for n in g["members"]:
            s = staff_by_name.get(n)
            if n in my_names:
                st, where = "mine", user_team["team_name"]
                got += 1
            elif s and s["team_id"] is None:
                st, where = "market", "시장"
                obtainable += 1
            elif s and s["team_id"]:
                st, where = "taken", team_map.get(s["team_id"], {}).get("team_name", "?")
            else:
                st, where = "none", "-"
            members.append({"name": n.rstrip("2"),
                            "role": ROLE_KR.get(s["role"], "?") if s else "?",
                            "st": st, "where": where})
        total = len(g["members"])
        if got == total:
            status = "active"
        elif got + obtainable == total and got >= 1:
            status = "possible"
        else:
            status = "other"
        group_codex.append({
            "title": g["title"], "desc": g["desc"], "members": members,
            "got": got, "total": total, "status": status,
        })
    group_codex.sort(key=lambda x: (status_order[x["status"]], -x["got"]))

    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "")

    return render_template(
        "dynasty_staff.html",
        save=save,
        user_team=user_team,
        mine=mine,
        market=market,
        others=others,
        synergies=synergies,
        codex=codex,
        group_codex=group_codex,
        my_style=my_manager["style"] if my_manager else None,
        my_manager_name=my_manager["disp_name"] if my_manager else None,
        budget=user_team.get("budget") or 0,
        msg=msg,
        ok=ok,
    )


@staff_bp.route("/dynasty/<int:save_id>/staff/hire", methods=["POST"])
def staff_hire(save_id):
    sb = get_supabase()
    staff_id = int(request.form.get("staff_id"))

    teams = sb.table("dynasty_team").select("id, is_user").eq("save_id", save_id).execute().data
    user_team = next(t for t in teams if t["is_user"])

    success, message = hire_staff(save_id, user_team["id"], staff_id)
    return redirect(url_for("dynasty_staff.staff_home", save_id=save_id,
                            msg=message, ok="1" if success else "0"))


@staff_bp.route("/dynasty/<int:save_id>/staff/fire", methods=["POST"])
def staff_fire(save_id):
    sb = get_supabase()
    staff_id = int(request.form.get("staff_id"))

    teams = sb.table("dynasty_team").select("id, is_user").eq("save_id", save_id).execute().data
    user_team = next(t for t in teams if t["is_user"])

    success, message = fire_staff(save_id, user_team["id"], staff_id)
    return redirect(url_for("dynasty_staff.staff_home", save_id=save_id,
                            msg=message, ok="1" if success else "0"))
