# dynasty_training.py
# =========================================
# KBO Dynasty - Phase 2: 선수 육성
# 대상: 내 팀 2군(MINOR) 선수, 시즌당 선수별 1회
# 비용: 30 (예산 차감)
# 결과: 대성공(+4~6) 20% / 성공(+2~3) 50% / 실패(+0~1) 30%
#       1~4년차는 대성공 확률 +10%p
# potential이 성장 천장
# AI 팀도 오프시즌에 자동 육성 (ai_auto_training)
# =========================================

import random
from dynasty_utils import get_supabase

TRAINING_COST = 30

BATTER_STATS = {
    "contact": "컨택", "power": "파워", "eye": "선구",
    "speed": "주력", "defense": "수비", "arm": "송구",
}
PITCHER_STATS = {
    "stuff": "구위", "control": "제구", "stamina": "체력",
    "defense": "수비", "arm": "송구",
}


def trainable_stats(player):
    if "P" in (player["positions"] or ""):
        return PITCHER_STATS
    return BATTER_STATS


# =========================================
# 육성 실행
# return: (성공여부, 메시지)
# =========================================
def train_player(save_id, team_id, player_id, stat):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    # 선수 확인
    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("id", player_id)
        .execute()
        .data
    )
    if not players:
        return False, "선수를 찾을 수 없습니다."
    p = players[0]

    if p["retired"]:
        return False, "은퇴한 선수는 육성할 수 없습니다."

    if p.get("trained_season") == season:
        return False, f"{p['name']}은(는) 이번 시즌 이미 육성했습니다."

    valid = trainable_stats(p)
    if stat not in valid:
        return False, "해당 선수에게 적용할 수 없는 능력치입니다."

    # 2군 소속 확인
    roster = (
        sb.table("dynasty_roster")
        .select("role")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .eq("player_id", player_id)
        .execute()
        .data
    )
    if not roster:
        return False, "내 로스터에 없는 선수입니다."
    if roster[0]["role"] != "MINOR":
        return False, "2군 선수만 육성할 수 있습니다."

    # 예산 확인
    team = (
        sb.table("dynasty_team")
        .select("*")
        .eq("id", team_id)
        .execute()
        .data[0]
    )
    budget = team.get("budget") or 0
    if budget < TRAINING_COST:
        return False, f"예산이 부족합니다. (필요 {TRAINING_COST} / 보유 {budget})"

    # ----- 육성 판정 -----
    career_years = season - p["appear_season"] + 1
    big_chance = 0.20 + (0.10 if career_years <= 4 else 0)

    r = random.random()
    if r < big_chance:
        gain = random.randint(4, 6)
        grade = "🌟 대성공"
    elif r < big_chance + 0.50:
        gain = random.randint(2, 3)
        grade = "✅ 성공"
    else:
        gain = random.randint(0, 1)
        grade = "😓 미미한 성과"

    old_value = p[stat] if p[stat] is not None else 25
    potential = p["potential"] or p["overall"]

    # potential 천장: 개별 능력치도 potential + 5 초과 불가
    ceiling = min(99, potential + 5)
    new_value = min(ceiling, old_value + gain)
    actual_gain = new_value - old_value

    # overall 재계산
    stats = dict(p)
    stats[stat] = new_value
    is_pitcher = "P" in (p["positions"] or "")
    if is_pitcher:
        new_overall = int(
            stats["stuff"] * 0.4 + stats["control"] * 0.4 + stats["stamina"] * 0.2
        )
    else:
        new_overall = int(
            stats["contact"] * 0.25 + stats["power"] * 0.25 + stats["eye"] * 0.15
            + stats["speed"] * 0.1 + stats["defense"] * 0.15 + stats["arm"] * 0.1
        )
    new_overall = max(20, min(99, new_overall))

    # ----- DB 반영 -----
    sb.table("dynasty_player").update(
        {
            stat: new_value,
            "overall": new_overall,
            "trained_season": season,
        }
    ).eq("id", player_id).execute()

    sb.table("dynasty_team").update(
        {"budget": budget - TRAINING_COST}
    ).eq("id", team_id).execute()

    stat_kr = valid[stat]
    msg = (
        f"{grade}! {p['name']} {stat_kr} {old_value} → {new_value} "
        f"(+{actual_gain}) · OVR {p['overall']} → {new_overall} "
        f"· 잔여 예산 {budget - TRAINING_COST}"
    )
    return True, msg


# =========================================
# AI 자동 육성 (오프시즌 호출)
# 각 AI 팀: 예산의 최대 30%로 2군 유망주(어림, potential 갭 큰 순) 육성
# =========================================
def ai_auto_training(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    ai_teams = [t for t in teams if not t["is_user"]]

    roster_rows = (
        sb.table("dynasty_roster")
        .select("team_id, role, dynasty_player(*)")
        .eq("save_id", save_id)
        .in_("team_id", [t["id"] for t in ai_teams])
        .eq("role", "MINOR")
        .execute()
        .data
    )

    by_team = {}
    for r in roster_rows:
        p = r["dynasty_player"]
        if not p or p["retired"] or p.get("trained_season") == season:
            continue
        by_team.setdefault(r["team_id"], []).append(p)

    total = 0
    player_updates = []
    team_updates = []

    for t in ai_teams:
        budget = t.get("budget") or 0
        spend_cap = int(budget * 0.3)
        pool = by_team.get(t["id"], [])

        # 어리고 potential 갭 큰 순
        pool.sort(
            key=lambda p: (
                -(p["potential"] or p["overall"]) + p["overall"],
                season - p["appear_season"],
            )
        )

        spent = 0
        for p in pool:
            if spent + TRAINING_COST > spend_cap:
                break

            valid = trainable_stats(p)
            stat = random.choice(list(valid.keys()))

            career_years = season - p["appear_season"] + 1
            big_chance = 0.20 + (0.10 if career_years <= 4 else 0)
            r = random.random()
            if r < big_chance:
                gain = random.randint(4, 6)
            elif r < big_chance + 0.50:
                gain = random.randint(2, 3)
            else:
                gain = random.randint(0, 1)

            old_value = p[stat] if p[stat] is not None else 25
            ceiling = min(99, (p["potential"] or p["overall"]) + 5)
            new_value = min(ceiling, old_value + gain)

            stats = dict(p)
            stats[stat] = new_value
            is_pitcher = "P" in (p["positions"] or "")
            if is_pitcher:
                new_overall = int(
                    stats["stuff"] * 0.4 + stats["control"] * 0.4 + stats["stamina"] * 0.2
                )
            else:
                new_overall = int(
                    stats["contact"] * 0.25 + stats["power"] * 0.25 + stats["eye"] * 0.15
                    + stats["speed"] * 0.1 + stats["defense"] * 0.15 + stats["arm"] * 0.1
                )
            new_overall = max(20, min(99, new_overall))

            player_updates.append(
                {"id": p["id"], "stat": stat, "value": new_value,
                 "overall": new_overall}
            )
            spent += TRAINING_COST
            total += 1

        if spent > 0:
            row = dict(t)
            row.pop("pct", None)
            row.pop("gb", None)
            row["budget"] = budget - spent
            team_updates.append(row)

    # 반영 (선수는 stat 컬럼이 제각각이라 개별 update, 수십 건 수준이라 OK)
    for u in player_updates:
        sb.table("dynasty_player").update(
            {u["stat"]: u["value"], "overall": u["overall"], "trained_season": season}
        ).eq("id", u["id"]).execute()

    if team_updates:
        sb.table("dynasty_team").upsert(team_updates).execute()

    print(f"[dynasty_training] AI 육성={total}건")
    return total
