# dynasty_trade.py
# =========================================
# KBO Dynasty - 트레이드 시스템 (티어 기반 판정)
# S(80+) / A(72-79) / B(64-71) / C(56-63) / D(~55)
# 같은 티어: 자유 교환
# 1티어 상향: 5명 이상 + 가치 충족 필요
# 2티어 이상 상향: 불가
# =========================================

import random
from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup

TIER_BOUNDS = [(80, "S"), (72, "A"), (64, "B"), (56, "C"), (0, "D")]
TIER_RANK = {"S": 4, "A": 3, "B": 2, "C": 1, "D": 0}
TIER_JUMP_MIN_PLAYERS = 5


# =========================================
# 티어 판정
# =========================================
def player_tier(overall):
    for bound, tier in TIER_BOUNDS:
        if overall >= bound:
            return tier
    return "D"


# =========================================
# 트레이드 가치 계산 (스타 프리미엄 반영)
# =========================================
def trade_value(player, current_season):
    overall = player["overall"]
    potential = player["potential"] if player["potential"] else overall
    career_years = current_season - player["appear_season"] + 1

    value = 10 + (overall / 20.0) ** 2.3 * 10

    room = max(0, potential - overall)
    if career_years <= 3:
        value += room * 1.2
    elif career_years <= 6:
        value += room * 0.6
    else:
        value += room * 0.15

    if career_years >= 12:
        value *= 0.6
    elif career_years >= 9:
        value *= 0.8

    return round(value, 1)


# =========================================
# 티어 규칙 검사
# return: (통과여부, 메시지)
# =========================================
def _check_tier_rule(my_players, their_players):
    my_best_tier = max(TIER_RANK[player_tier(p["overall"])] for p in my_players)
    their_best_tier = max(TIER_RANK[player_tier(p["overall"])] for p in their_players)

    gap = their_best_tier - my_best_tier

    if gap <= 0:
        return True, ""

    if gap >= 2:
        return False, "상대 구단이 거절했습니다. (등급 차이가 너무 큽니다 — 2등급 이상 상위 선수는 교환 불가)"

    # gap == 1: 5명 이상 제시해야 검토
    if len(my_players) < TIER_JUMP_MIN_PLAYERS:
        return False, f"상대 구단이 거절했습니다. (상위 등급 선수 영입에는 최소 {TIER_JUMP_MIN_PLAYERS}명 이상 제시 필요)"

    return True, ""


# =========================================
# 유저 트레이드 제안
# =========================================
def propose_trade(save_id, my_team_id, target_team_id, my_player_ids, their_player_ids):
    sb = get_supabase()

    if not my_player_ids or not their_player_ids:
        return False, "양쪽 모두 최소 1명 이상 포함해야 합니다."

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    my_players = _get_players(sb, save_id, my_player_ids)
    their_players = _get_players(sb, save_id, their_player_ids)

    if len(my_players) != len(my_player_ids):
        return False, "내 선수 정보를 찾을 수 없습니다."
    if len(their_players) != len(their_player_ids):
        return False, "상대 선수 정보를 찾을 수 없습니다."

    if not _verify_roster(sb, save_id, my_team_id, my_player_ids):
        return False, "내 로스터에 없는 선수가 포함되어 있습니다."
    if not _verify_roster(sb, save_id, target_team_id, their_player_ids):
        return False, "상대 로스터에 없는 선수가 포함되어 있습니다."

    # 1. 티어 규칙
    ok, msg = _check_tier_rule(my_players, their_players)
    if not ok:
        return False, msg

    # 2. 가치 비교
    my_value = sum(trade_value(p, season) for p in my_players)
    their_value = sum(trade_value(p, season) for p in their_players)

    # 인원수 페널티
    count_diff = len(my_players) - len(their_players)
    if count_diff > 0:
        my_value *= max(0.7, 1.0 - count_diff * 0.12)

    # 티어 점프 시 가치도 20% 더 요구
    my_best_tier = max(TIER_RANK[player_tier(p["overall"])] for p in my_players)
    their_best_tier = max(TIER_RANK[player_tier(p["overall"])] for p in their_players)
    required = 1.0
    if their_best_tier > my_best_tier:
        required = 1.2

    ratio = my_value / their_value if their_value > 0 else 0

    if ratio < 0.9 * required:
        return False, "상대 구단이 제안을 거절했습니다. (가치 차이가 큽니다)"

    if ratio < 1.0 * required:
        if random.random() > 0.3:
            return False, "상대 구단이 고민 끝에 제안을 거절했습니다."

    if ratio > 1.6 and random.random() < 0.2:
        return False, "상대 구단이 제안 의도를 의심하며 거절했습니다."

    _execute_trade(
        sb, save_id, my_team_id, target_team_id, my_player_ids, their_player_ids
    )

    auto_generate_lineup(save_id, my_team_id)
    auto_generate_lineup(save_id, target_team_id)

    return True, "트레이드가 성사되었습니다!"


# =========================================
# 트레이드 실행 (로스터 이동)
# =========================================
def _execute_trade(sb, save_id, team_a, team_b, a_player_ids, b_player_ids):
    for i in range(0, len(a_player_ids), 50):
        sb.table("dynasty_roster").update(
            {"team_id": team_b, "role": "BENCH", "depth": 99}
        ).eq("save_id", save_id).in_(
            "player_id", a_player_ids[i : i + 50]
        ).execute()

    for i in range(0, len(b_player_ids), 50):
        sb.table("dynasty_roster").update(
            {"team_id": team_a, "role": "BENCH", "depth": 99}
        ).eq("save_id", save_id).in_(
            "player_id", b_player_ids[i : i + 50]
        ).execute()


# =========================================
# AI끼리 자동 트레이드 (같은 티어끼리만)
# =========================================
def ai_auto_trades(save_id, max_trades=3):
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
        .select("id, is_user")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    ai_teams = [t["id"] for t in teams if not t["is_user"]]

    if len(ai_teams) < 2:
        return 0

    roster_rows = (
        sb.table("dynasty_roster")
        .select("team_id, dynasty_player(*)")
        .eq("save_id", save_id)
        .in_("team_id", ai_teams)
        .execute()
        .data
    )

    by_team = {}
    for r in roster_rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        by_team.setdefault(r["team_id"], []).append(p)

    trades_done = 0
    attempts = 0

    while trades_done < max_trades and attempts < 10:
        attempts += 1

        candidates_teams = [tid for tid in ai_teams if len(by_team.get(tid, [])) >= 15]
        if len(candidates_teams) < 2:
            break

        team_a, team_b = random.sample(candidates_teams, 2)

        roster_a = by_team[team_a]
        roster_b = by_team[team_b]

        pa = random.choice(roster_a)
        va = trade_value(pa, season)
        tier_a = player_tier(pa["overall"])

        # 같은 티어 + 비슷한 가치만 매칭
        matches = [
            pb
            for pb in roster_b
            if player_tier(pb["overall"]) == tier_a
            and abs(trade_value(pb, season) - va) <= va * 0.15
        ]
        if not matches:
            continue

        pb = random.choice(matches)

        _execute_trade(sb, save_id, team_a, team_b, [pa["id"]], [pb["id"]])

        roster_a.remove(pa)
        roster_b.remove(pb)
        roster_a.append(pb)
        roster_b.append(pa)

        trades_done += 1

    print(f"[dynasty_trade] AI 트레이드 성사={trades_done}건")
    return trades_done


# =========================================
# 헬퍼
# =========================================
def _get_players(sb, save_id, player_ids):
    return (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .in_("id", player_ids)
        .execute()
        .data
    )


def _verify_roster(sb, save_id, team_id, player_ids):
    rows = (
        sb.table("dynasty_roster")
        .select("player_id")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .in_("player_id", player_ids)
        .execute()
        .data
    )
    return len(rows) == len(player_ids)
