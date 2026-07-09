# dynasty_trade.py
# =========================================
# KBO Dynasty - 트레이드 시스템
# 유저 제안 → AI 수락/거절 판정
# AI끼리 자동 트레이드
# =========================================

import random
from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup


# =========================================
# 트레이드 가치 계산
# overall + potential + 연차 반영
# =========================================
def trade_value(player, current_season):
    overall = player["overall"]
    potential = player["potential"] if player["potential"] else overall
    career_years = current_season - player["appear_season"] + 1

    value = overall * 1.0

    # 잠재력 프리미엄 (젊을수록 크게)
    room = max(0, potential - overall)
    if career_years <= 3:
        value += room * 0.8
    elif career_years <= 6:
        value += room * 0.4
    else:
        value += room * 0.1

    # 노장 디스카운트
    if career_years >= 12:
        value *= 0.6
    elif career_years >= 9:
        value *= 0.8

    return round(value, 1)


# =========================================
# 유저 트레이드 제안
# my_player_ids: 유저가 내주는 선수 id 리스트
# their_player_ids: 받아오는 선수 id 리스트
# target_team_id: 상대 팀
# return: (성사여부, 메시지)
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

    # 로스터 소속 검증
    if not _verify_roster(sb, save_id, my_team_id, my_player_ids):
        return False, "내 로스터에 없는 선수가 포함되어 있습니다."
    if not _verify_roster(sb, save_id, target_team_id, their_player_ids):
        return False, "상대 로스터에 없는 선수가 포함되어 있습니다."

    my_value = sum(trade_value(p, season) for p in my_players)
    their_value = sum(trade_value(p, season) for p in their_players)

    # AI 판정: 받는 가치가 주는 가치의 95% 이상이면 수락 검토
    ratio = my_value / their_value if their_value > 0 else 0

    if ratio < 0.85:
        return False, "상대 구단이 제안을 거절했습니다. (가치 차이가 큽니다)"

    if ratio < 0.95:
        # 애매한 제안은 확률 수락
        if random.random() > 0.35:
            return False, "상대 구단이 고민 끝에 제안을 거절했습니다."

    # 과도하게 유리한 제안도 가끔 의심하고 거절
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
    for pid in a_player_ids:
        sb.table("dynasty_roster").update(
            {"team_id": team_b, "role": "BENCH", "depth": 99}
        ).eq("save_id", save_id).eq("player_id", pid).execute()

    for pid in b_player_ids:
        sb.table("dynasty_roster").update(
            {"team_id": team_a, "role": "BENCH", "depth": 99}
        ).eq("save_id", save_id).eq("player_id", pid).execute()


# =========================================
# AI끼리 자동 트레이드 (오프시즌 호출용)
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

    trades_done = 0
    attempts = 0

    while trades_done < max_trades and attempts < 10:
        attempts += 1

        if len(ai_teams) < 2:
            break

        team_a, team_b = random.sample(ai_teams, 2)

        roster_a = _get_team_roster_players(sb, save_id, team_a)
        roster_b = _get_team_roster_players(sb, save_id, team_b)

        if len(roster_a) < 15 or len(roster_b) < 15:
            continue

        pa = random.choice(roster_a)
        va = trade_value(pa, season)

        # 비슷한 가치의 상대 선수 탐색
        candidates = [
            pb
            for pb in roster_b
            if abs(trade_value(pb, season) - va) <= va * 0.15
        ]
        if not candidates:
            continue

        pb = random.choice(candidates)

        _execute_trade(sb, save_id, team_a, team_b, [pa["id"]], [pb["id"]])
        auto_generate_lineup(save_id, team_a)
        auto_generate_lineup(save_id, team_b)

        trades_done += 1

    return trades_done


# =========================================
# 헬퍼
# =========================================
def _get_players(sb, save_id, player_ids):
    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .in_("id", player_ids)
        .execute()
        .data
    )
    return players


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


def _get_team_roster_players(sb, save_id, team_id):
    rows = (
        sb.table("dynasty_roster")
        .select("dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .execute()
        .data
    )
    return [r["dynasty_player"] for r in rows if r["dynasty_player"]]
