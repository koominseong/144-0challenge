# dynasty_facility.py
# =========================================
# KBO Dynasty - Phase 4: 구장 / 2군 시설 투자
#
# 구장 (stadium_level 1~5):
#   효과: 팬 증가율 +1%p/레벨, 홈 어드밴티지 +0.5%p/레벨
#   비용: Lv2 150 / Lv3 300 / Lv4 500 / Lv5 800
#
# 2군 시설 (facility_level 1~5):
#   효과: 2군(MINOR) 선수 오프시즌 성장 delta + (레벨-1)//2
#         (Lv1~2: +0, Lv3~4: +1, Lv5: +2)
#         육성 대성공 확률 +2%p/레벨
#   비용: Lv2 120 / Lv3 250 / Lv4 400 / Lv5 650
#
# 레벨은 영구 (시즌 넘어가도 유지). AI도 오프시즌 자동 투자.
# =========================================

from dynasty_utils import get_supabase

MAX_LEVEL = 5

STADIUM_COST = {2: 150, 3: 300, 4: 500, 5: 800}
FACILITY_COST = {2: 120, 3: 250, 4: 400, 5: 650}

STADIUM_DESC = "팬 증가율 +1%p/Lv · 홈 어드밴티지 +0.5%p/Lv"
FACILITY_DESC = "2군 성장 보정 (Lv3~4: +1, Lv5: +2) · 육성 대성공 +2%p/Lv"


def upgrade_cost(kind, current_level):
    table = STADIUM_COST if kind == "stadium" else FACILITY_COST
    return table.get(current_level + 1)


# =========================================
# 업그레이드 (유저)
# kind: "stadium" | "facility"
# =========================================
def upgrade(save_id, team_id, kind):
    sb = get_supabase()

    if kind not in ("stadium", "facility"):
        return False, "잘못된 요청입니다."

    team = (
        sb.table("dynasty_team")
        .select("*")
        .eq("id", team_id)
        .execute()
        .data[0]
    )

    col = "stadium_level" if kind == "stadium" else "facility_level"
    level = team.get(col) or 1

    if level >= MAX_LEVEL:
        return False, "이미 최고 레벨입니다."

    cost = upgrade_cost(kind, level)
    budget = team.get("budget") or 0

    if budget < cost:
        return False, f"예산 부족 (필요 {cost} / 보유 {budget})"

    sb.table("dynasty_team").update(
        {col: level + 1, "budget": budget - cost}
    ).eq("id", team_id).execute()

    name = "구장" if kind == "stadium" else "2군 시설"
    return True, f"{name} Lv{level} → Lv{level + 1} 업그레이드 완료! (비용 {cost}, 잔여 {budget - cost})"


# =========================================
# 팀별 시설 효과 조회
# return: {team_id: {"fan_bonus": float, "home_adv": float,
#                    "minor_growth": int, "training_crit": float}}
# =========================================
def get_facility_effects(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("id, stadium_level, facility_level")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    effects = {}
    for t in teams:
        sl = t.get("stadium_level") or 1
        fl = t.get("facility_level") or 1
        effects[t["id"]] = {
            "fan_bonus": (sl - 1) * 0.01,
            "home_adv": (sl - 1) * 0.005,
            "minor_growth": (fl - 1) // 2,
            "training_crit": (fl - 1) * 0.02,
        }
    return effects


# =========================================
# AI 자동 투자 (오프시즌 호출)
# 예산 40% 이상 남아있으면 낮은 쪽 시설부터 업그레이드
# =========================================
def ai_upgrade_facilities(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    upgraded = 0

    for t in teams:
        if t["is_user"]:
            continue

        budget = t.get("budget") or 0
        sl = t.get("stadium_level") or 1
        fl = t.get("facility_level") or 1

        # 낮은 쪽 우선
        plans = sorted(
            [("stadium", sl), ("facility", fl)], key=lambda x: x[1]
        )

        updates = {}
        for kind, level in plans:
            if level >= MAX_LEVEL:
                continue
            cost = upgrade_cost(kind, level)
            # 업그레이드 후에도 예산 40% 이상 남을 때만
            if budget - cost < (t.get("budget") or 0) * 0.4:
                continue
            col = "stadium_level" if kind == "stadium" else "facility_level"
            updates[col] = level + 1
            budget -= cost
            upgraded += 1
            break  # 시즌당 1회만

        if updates:
            updates["budget"] = budget
            sb.table("dynasty_team").update(updates).eq("id", t["id"]).execute()

    print(f"[dynasty_facility] AI 시설 투자={upgraded}건")
    return upgraded
