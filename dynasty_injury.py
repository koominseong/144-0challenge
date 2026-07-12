# dynasty_injury.py
# =========================================
# KBO Dynasty - Phase 6: 부상 / 각성 이벤트
# 주 단위 진행 시 호출 (simulate_week 이전)
#
# 부상: 1군 선수 주당 1.2% 확률, 2~4주 결장
#       → 즉시 2군행 + 같은 유형(투수/야수) 2군 최고 선수가 자리 대체
# 회복: 결장 기간 종료 시 부상 해제 (2군에 머무름, 승격은 유저/자동라인업)
# 각성: 5년차 이하 + 잠재력 여유 5+ 선수, 주당 0.4% 확률
#       → 핵심 능력치 +2~4 (영구), OVR 재계산
# 모든 이벤트는 뉴스(dynasty_event)에 기록
# =========================================

import random
from dynasty_utils import get_supabase

INJURY_RATE = 0.012
AWAKEN_RATE = 0.004

FIRST_TEAM_ROLES = ["START", "SP", "CP", "RP"]


def process_weekly_events(save_id, season, week):
    sb = get_supabase()

    rows = (
        sb.table("dynasty_roster")
        .select("id, team_id, role, depth, dynasty_player(*)")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    teams = (
        sb.table("dynasty_team")
        .select("id, team_name, logo")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_map = {t["id"]: t for t in teams}

    first_team = []   # (roster_row, player)
    minors_by_team = {}

    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        if r["role"] in FIRST_TEAM_ROLES:
            first_team.append((r, p))
        elif r["role"] == "MINOR":
            minors_by_team.setdefault(r["team_id"], []).append((r, p))

    events = []
    injuries = 0
    recoveries = 0
    awakenings = 0

    # ---------- 1. 회복 처리 ----------
    for r, p in first_team + [x for v in minors_by_team.values() for x in v]:
        if (
            p.get("injured_season") == season
            and p.get("injured_until_week") is not None
            and p["injured_until_week"] <= week
        ):
            sb.table("dynasty_player").update(
                {"injured_season": None, "injured_until_week": None}
            ).eq("id", p["id"]).execute()
            events.append(
                {"season": season, "week": week, "type": "recover", "icon": "💪",
                 "message": f"{p['name']} 부상 복귀! (현재 2군 대기)"}
            )
            recoveries += 1

    # ---------- 2. 부상 발생 (1군 대상) ----------
    for r, p in first_team:
        if p.get("injured_season") == season and (p.get("injured_until_week") or 0) > week:
            continue
        if random.random() > INJURY_RATE:
            continue

        out_weeks = random.randint(2, 4)
        sb.table("dynasty_player").update(
            {"injured_season": season, "injured_until_week": week + out_weeks}
        ).eq("id", p["id"]).execute()

        # 2군 대체 선수 승격 (같은 유형)
        is_pitcher = "P" in (p["positions"] or "")
        pool = minors_by_team.get(r["team_id"], [])
        candidates = [
            (mr, mp) for mr, mp in pool
            if ("P" in (mp["positions"] or "")) == is_pitcher
            and not (mp.get("injured_season") == season and (mp.get("injured_until_week") or 0) > week)
        ]

        team = team_map.get(r["team_id"], {})
        if candidates:
            candidates.sort(key=lambda x: -x[1]["overall"])
            sub_r, sub_p = candidates[0]
            pool.remove((sub_r, sub_p))

            # 역할 스왑
            sb.table("dynasty_roster").update(
                {"role": r["role"], "depth": r["depth"]}
            ).eq("id", sub_r["id"]).execute()
            sb.table("dynasty_roster").update(
                {"role": "MINOR", "depth": 99}
            ).eq("id", r["id"]).execute()

            msg = (
                f"{team.get('team_name','')} {p['name']} 부상 ({out_weeks}주 결장) "
                f"→ {sub_p['name']}(OVR {sub_p['overall']}) 1군 콜업"
            )
        else:
            sb.table("dynasty_roster").update(
                {"role": "MINOR", "depth": 99}
            ).eq("id", r["id"]).execute()
            msg = f"{team.get('team_name','')} {p['name']} 부상 ({out_weeks}주 결장) — 대체 자원 없음!"

        events.append(
            {"season": season, "week": week, "type": "injury", "icon": "🤕", "message": msg}
        )
        injuries += 1

    # ---------- 3. 각성 (젊은 유망주) ----------
    for r, p in first_team:
        career_years = season - p["appear_season"] + 1
        potential = p["potential"] or p["overall"]
        if career_years > 5 or potential - p["overall"] < 5:
            continue
        if random.random() > AWAKEN_RATE:
            continue

        is_pitcher = "P" in (p["positions"] or "")
        stat = random.choice(
            ["stuff", "control", "stamina"] if is_pitcher
            else ["contact", "power", "eye"]
        )
        gain = random.randint(2, 4)
        new_value = min(99, (p[stat] or 25) + gain)

        stats = dict(p)
        stats[stat] = new_value
        if is_pitcher:
            new_overall = int(stats["stuff"] * 0.4 + stats["control"] * 0.4 + stats["stamina"] * 0.2)
        else:
            new_overall = int(
                stats["contact"] * 0.25 + stats["power"] * 0.25 + stats["eye"] * 0.15
                + stats["speed"] * 0.1 + stats["defense"] * 0.15 + stats["arm"] * 0.1
            )
        new_overall = max(20, min(99, new_overall))

        sb.table("dynasty_player").update(
            {stat: new_value, "overall": new_overall}
        ).eq("id", p["id"]).execute()

        team = team_map.get(r["team_id"], {})
        events.append(
            {"season": season, "week": week, "type": "awaken", "icon": "✨",
             "message": f"{team.get('team_name','')} {p['name']} 각성! OVR {p['overall']} → {new_overall}"}
        )
        awakenings += 1

    # ---------- 이벤트 일괄 기록 ----------
    if events:
        try:
            from dynasty_event import log_events
            log_events(save_id, events)
        except Exception as ex:
            print(f"[dynasty_injury] 이벤트 기록 실패: {ex}")

    print(f"[dynasty_injury] W{week}: 부상={injuries}, 복귀={recoveries}, 각성={awakenings}")
