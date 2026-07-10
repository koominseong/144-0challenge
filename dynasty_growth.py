# dynasty_growth.py
# =========================================
# KBO Dynasty - 오프시즌 성장 / 노쇠 / 은퇴 (최종 통합본)
# + 시즌별 능력치 스냅샷 (dynasty_player_history)
# + peak_overall / retired_season 기록
# + 감독/코치 성장 보정 (Phase 3, dynasty_staff)
# + 2군 시설 성장 보정 (Phase 4, dynasty_facility)
# =========================================

import random
from dynasty_utils import get_supabase


# =========================================
# 오프시즌 처리 전체
# =========================================
def process_offseason_growth(save_id):
    sb = get_supabase()

    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("retired", False)
        .execute()
        .data
    )

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    current_season = save["season"]

    # ---------- 스태프(감독/코치) 성장 보정 로드 ----------
    try:
        from dynasty_staff import get_staff_effects
        staff_effects = get_staff_effects(save_id)
    except Exception as ex:
        print(f"[dynasty_growth] 스태프 효과 skip: {ex}")
        staff_effects = {}

    roster_map_rows = (
        sb.table("dynasty_roster")
        .select("player_id, team_id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    player_team = {r["player_id"]: r["team_id"] for r in roster_map_rows}

    # ---------- 2군 시설 성장 보정 로드 ----------
    try:
        from dynasty_facility import get_facility_effects
        fac_effects = get_facility_effects(save_id)
    except Exception as ex:
        print(f"[dynasty_growth] 시설 효과 skip: {ex}")
        fac_effects = {}

    minor_rows = (
        sb.table("dynasty_roster")
        .select("player_id, team_id, role")
        .eq("save_id", save_id)
        .eq("role", "MINOR")
        .execute()
        .data
    )
    minor_team = {r["player_id"]: r["team_id"] for r in minor_rows}

    upsert_rows = []
    retired_ids = []

    for p in players:
        # 등장 전 선수는 건드리지 않음
        if p["appear_season"] > current_season:
            continue

        career_years = current_season - p["appear_season"] + 1

        # 코치 보정: 타자→타격코치 / 투수→투수코치, 육성가 감독은 4년차 이하 +1
        e = staff_effects.get(player_team.get(p["id"]), {})
        is_pitcher_p = "P" in (p["positions"] or "")
        coach_bonus = e.get("pit_growth", 0) if is_pitcher_p else e.get("bat_growth", 0)
        if career_years <= 4:
            coach_bonus += e.get("young_growth", 0)

        # 2군 시설 보정: 2군 소속 선수만
        if p["id"] in minor_team:
            coach_bonus += fac_effects.get(minor_team[p["id"]], {}).get("minor_growth", 0)

        updated = _grow_player(p, career_years, coach_bonus)

        # 커리어 최고 능력치 갱신
        prev_peak = p.get("peak_overall") or p["overall"]
        peak = max(prev_peak, p["overall"], updated["overall"])

        is_retired = _check_retirement(updated, career_years)
        if is_retired:
            retired_ids.append(p["id"])

        upsert_rows.append(
            {
                "id": p["id"],
                "save_id": save_id,
                "name": p["name"],
                "positions": p["positions"],
                "appear_season": p["appear_season"],
                "drafted": p["drafted"],
                "war": p["war"],
                "potential": p["potential"],
                "overall": updated["overall"],
                "peak_overall": peak,
                "contact": updated["contact"],
                "power": updated["power"],
                "eye": updated["eye"],
                "speed": updated["speed"],
                "defense": updated["defense"],
                "arm": updated["arm"],
                "stuff": updated["stuff"],
                "control": updated["control"],
                "stamina": updated["stamina"],
                "retired": is_retired,
                "retired_season": current_season if is_retired else None,
            }
        )

    # ---------- 시즌 종료 시점 능력치 스냅샷 ----------
    history_rows = []
    for row in upsert_rows:
        history_rows.append(
            {
                "save_id": save_id,
                "player_id": row["id"],
                "season": current_season,
                "overall": row["overall"],
                "contact": row["contact"],
                "power": row["power"],
                "eye": row["eye"],
                "speed": row["speed"],
                "defense": row["defense"],
                "arm": row["arm"],
                "stuff": row["stuff"],
                "control": row["control"],
                "stamina": row["stamina"],
            }
        )
    for i in range(0, len(history_rows), 100):
        sb.table("dynasty_player_history").insert(
            history_rows[i : i + 100]
        ).execute()

    print(f"[dynasty_growth] 스냅샷 저장={len(history_rows)}건")

    # ---------- 선수 일괄 upsert ----------
    for i in range(0, len(upsert_rows), 100):
        sb.table("dynasty_player").upsert(upsert_rows[i : i + 100]).execute()

    # ---------- 은퇴 선수 로스터 제거 ----------
    for i in range(0, len(retired_ids), 50):
        chunk = retired_ids[i : i + 50]
        sb.table("dynasty_roster").delete().eq("save_id", save_id).in_(
            "player_id", chunk
        ).execute()

    print(
        f"[dynasty_growth] 처리={len(upsert_rows)}명, 은퇴={len(retired_ids)}명"
    )


# =========================================
# 개별 선수 성장/노쇠 (coach_bonus: 스태프+시설 성장 보정)
# =========================================
def _grow_player(p, career_years, coach_bonus=0):
    overall = p["overall"]
    potential = p["potential"] if p["potential"] else overall

    is_pitcher = "P" in (p["positions"] or "")

    if career_years <= 4:
        room = max(0, potential - overall)
        gain = 0
        if room > 0:
            gain = random.randint(0, min(5, room))
            if random.random() < 0.15:
                gain = min(room, gain + random.randint(1, 3))
        delta = gain
    elif career_years <= 8:
        delta = random.randint(-1, 2)
        if overall > potential:
            delta = random.randint(-2, 0)
    else:
        decline = random.randint(1, 4)
        if random.random() < 0.2:
            decline = random.randint(0, 1)
        delta = -decline

    # 스태프/시설 보정 (성장기엔 상승폭 확대, 하락기엔 하락 완화)
    delta += coach_bonus

    stats = ["contact", "power", "eye", "speed", "defense", "arm"]
    if is_pitcher:
        stats = ["stuff", "control", "stamina", "defense", "arm"]

    result = dict(p)

    for s in stats:
        v = p[s] if p[s] is not None else overall
        sd = delta + random.randint(-1, 1)
        if s == "speed" and career_years > 6:
            sd -= random.randint(0, 2)
        result[s] = max(20, min(99, v + sd))

    if is_pitcher:
        new_overall = int(
            result["stuff"] * 0.4
            + result["control"] * 0.4
            + result["stamina"] * 0.2
        )
    else:
        new_overall = int(
            result["contact"] * 0.25
            + result["power"] * 0.25
            + result["eye"] * 0.15
            + result["speed"] * 0.1
            + result["defense"] * 0.15
            + result["arm"] * 0.1
        )

    result["overall"] = max(20, min(99, new_overall))

    return result


# =========================================
# 은퇴 판정
# =========================================
def _check_retirement(p, career_years):
    overall = p["overall"]

    if career_years < 8:
        return False

    prob = 0.0

    if overall < 45:
        prob += 0.6
    elif overall < 55:
        prob += 0.3
    elif overall < 62:
        prob += 0.12

    if career_years >= 15:
        prob += 0.5
    elif career_years >= 12:
        prob += 0.25
    elif career_years >= 10:
        prob += 0.1

    if career_years >= 18:
        return True

    return random.random() < prob
