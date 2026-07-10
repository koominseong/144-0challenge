# dynasty_growth.py
# =========================================
# KBO Dynasty - 오프시즌 성장 / 노쇠 / 은퇴 (명예의 전당 추적 버전)
# peak_overall(커리어 최고 능력치) 기록 → 명예의 전당 판정에 사용
# 사전 준비 (Supabase SQL Editor):
#   ALTER TABLE dynasty_player ADD COLUMN IF NOT EXISTS peak_overall int;
#   ALTER TABLE dynasty_player ADD COLUMN IF NOT EXISTS retired_season int;
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

    upsert_rows = []
    retired_ids = []

    for p in players:
        if p["appear_season"] > current_season:
            continue

        career_years = current_season - p["appear_season"] + 1

        updated = _grow_player(p, career_years)

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

    for i in range(0, len(upsert_rows), 100):
        sb.table("dynasty_player").upsert(upsert_rows[i : i + 100]).execute()

    for i in range(0, len(retired_ids), 50):
        chunk = retired_ids[i : i + 50]
        sb.table("dynasty_roster").delete().eq("save_id", save_id).in_(
            "player_id", chunk
        ).execute()

    from dynasty_event import log_events
    big_retires = [
        r for r in upsert_rows
        if r["retired"] and (r.get("peak_overall") or 0) >= 72
    ]
    log_events(save_id, [
        {"season": current_season, "week": 0, "type": "retire", "icon": "👋",
         "message": f"{r['name']} 은퇴 (최고 OVR {r['peak_overall']})"}
        for r in big_retires
    ])

    print(
        f"[dynasty_growth] 처리={len(upsert_rows)}명, 은퇴={len(retired_ids)}명"
    )


# =========================================
# 개별 선수 성장/노쇠
# =========================================
def _grow_player(p, career_years):
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
