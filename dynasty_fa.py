# dynasty_fa.py
# =========================================
# KBO Dynasty - FA 시스템
# 시즌 종료 후 FA 자격 선수 발생
# 유저 영입 / AI 자동 영입
# =========================================

import random
from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup
from dynasty_trade import trade_value

FA_CAREER_YEARS = 6  # FA 자격 연차
FA_RELEASE_RATE = 0.35  # FA 자격자 중 실제 시장에 나오는 비율


# =========================================
# FA 시장 생성 (오프시즌 호출)
# 자격 선수 일부를 로스터에서 해제
# return: FA 선수 리스트
# =========================================
def generate_fa_market(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    roster_rows = (
        sb.table("dynasty_roster")
        .select("id, team_id, player_id, dynasty_player(*)")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    fa_players = []

    for r in roster_rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue

        career_years = season - p["appear_season"] + 1

        if career_years < FA_CAREER_YEARS:
            continue
        # FA 재자격: 6년차 이후 3년 주기
        if (career_years - FA_CAREER_YEARS) % 3 != 0:
            continue

        if random.random() > FA_RELEASE_RATE:
            continue

        # 로스터에서 해제
        sb.table("dynasty_roster").delete().eq("id", r["id"]).execute()
        fa_players.append(p)

    return fa_players


# =========================================
# 현재 FA 시장 조회
# (드래프트 완료 && 로스터 미소속 && 은퇴 아님 && 등장 완료)
# =========================================
def get_fa_players(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    players = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("drafted", True)
        .eq("retired", False)
        .lte("appear_season", season)
        .order("overall", desc=True)
        .execute()
        .data
    )

    rostered = (
        sb.table("dynasty_roster")
        .select("player_id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    rostered_ids = {r["player_id"] for r in rostered}

    return [p for p in players if p["id"] not in rostered_ids]


# =========================================
# 유저 FA 영입
# =========================================
def sign_fa_player(save_id, team_id, player_id):
    sb = get_supabase()

    fa_players = get_fa_players(save_id)
    fa_ids = {p["id"] for p in fa_players}

    if player_id not in fa_ids:
        return False, "해당 선수는 FA 시장에 없습니다."

    roster_count = (
        sb.table("dynasty_roster")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .execute()
        .count
    )

    if roster_count >= 30:
        return False, "로스터가 가득 찼습니다. (최대 30명)"

    sb.table("dynasty_roster").insert(
        {
            "save_id": save_id,
            "team_id": team_id,
            "player_id": player_id,
            "role": "BENCH",
            "depth": 99,
        }
    ).execute()

    auto_generate_lineup(save_id, team_id)

    return True, "FA 영입에 성공했습니다!"


# =========================================
# AI 자동 FA 영입
# 로스터 적은 팀 우선, 상위 FA부터 확률 영입
# =========================================
def ai_sign_fa(save_id):
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
    ai_team_ids = [t["id"] for t in teams if not t["is_user"]]

    fa_players = get_fa_players(save_id)
    fa_players.sort(key=lambda p: -trade_value(p, season))

    signed = 0

    for p in fa_players:
        # 로스터 인원 파악
        counts = {}
        for tid in ai_team_ids:
            c = (
                sb.table("dynasty_roster")
                .select("id", count="exact")
                .eq("save_id", save_id)
                .eq("team_id", tid)
                .execute()
                .count
            )
            counts[tid] = c

        # 25명 미만 팀만 영입 시도
        needy = [tid for tid in ai_team_ids if counts[tid] < 25]
        if not needy:
            break

        # 상위 FA일수록 영입 확률 높음
        if p["overall"] >= 75:
            prob = 0.9
        elif p["overall"] >= 65:
            prob = 0.7
        elif p["overall"] >= 55:
            prob = 0.4
        else:
            prob = 0.15

        if random.random() > prob:
            continue

        # 인원 적은 팀에 가중치
        needy.sort(key=lambda tid: counts[tid])
        pool = needy[: min(3, len(needy))]
        target = random.choice(pool)

        sb.table("dynasty_roster").insert(
            {
                "save_id": save_id,
                "team_id": target,
                "player_id": p["id"],
                "role": "BENCH",
                "depth": 99,
            }
        ).execute()

        signed += 1

    for tid in ai_team_ids:
        auto_generate_lineup(save_id, tid)

    return signed
