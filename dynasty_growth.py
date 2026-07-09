# dynasty_growth.py
# =========================================
# KBO Dynasty - 오프시즌 성장 / 노쇠 / 은퇴
# =========================================

import random
from dynasty_utils import get_supabase


# =========================================
# 오프시즌 처리 전체
# 1. 성장/노쇠
# 2. 은퇴 판정
# 3. 은퇴 선수 로스터 제거
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

    retired_ids = []

    for p in players:
        # 등장 전 선수는 건드리지 않음
        if p["appear_season"] > current_season:
            continue

        career_years = current_season - p["appear_season"] + 1

        updated = _grow_player(p, career_years)

        if _check_retirement(updated, career_years):
            updated["retired"] = True
            retired_ids.append(p["id"])

        sb.table("dynasty_player").update(
            {
                "overall": updated["overall"],
                "contact": updated["contact"],
                "power": updated["power"],
                "eye": updated["eye"],
                "speed": updated["speed"],
                "defense": updated["defense"],
                "arm": updated["arm"],
                "stuff": updated["stuff"],
                "control": updated["control"],
                "stamina": updated["stamina"],
                "retired": updated.get("retired", False),
            }
        ).eq("id", p["id"]).execute()

    # 은퇴 선수 로스터에서 제거
    if retired_ids:
        for i in range(0, len(retired_ids), 50):
            chunk = retired_ids[i : i + 50]
            sb.table("dynasty_roster").delete().eq("save_id", save_id).in_(
                "player_id", chunk
            ).execute()


# =========================================
# 개별 선수 성장/노쇠
# =========================================
def _grow_player(p, career_years):
    overall = p["overall"]
    potential = p["potential"] if p["potential"] else overall

    is_pitcher = "P" in (p["positions"] or "")

    # 성장 곡선
    # 1~4년차: 성장기
    # 5~8년차: 전성기 (미세 변동)
    # 9년차~: 하락기
    if career_years <= 4:
        room = max(0, potential - overall)
        gain = 0
        if room > 0:
            gain = random.randint(0, min(5, room))
            # 어린 유망주 급성장 변수
            if random.random() < 0.15:
                gain = min(room, gain + random.randint(1, 3))
        delta = gain
    elif career_years <= 8:
        delta = random.randint(-1, 2)
        if overall > potential:
            delta = random.randint(-2, 0)
    else:
        decline = random.randint(1, 4)
        # 장수 변수
        if random.random() < 0.2:
            decline = random.randint(0, 1)
        delta = -decline

    stats = ["contact", "power", "eye", "speed", "defense", "arm"]
    if is_pitcher:
        stats = ["stuff", "control", "stamina", "defense", "arm"]

    result = dict(p)

    # 개별 능력치 변동
    for s in stats:
        v = p[s] if p[s] is not None else overall
        sd = delta + random.randint(-1, 1)
        # 스피드는 노쇠 빠름
        if s == "speed" and career_years > 6:
            sd -= random.randint(0, 2)
        result[s] = max(20, min(99, v + sd))

    # overall 재계산
    if is_pitcher:
        core = [result["stuff"], result["control"], result["stamina"]]
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

    # 능력치 낮을수록, 연차 길수록 은퇴 확률 상승
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
