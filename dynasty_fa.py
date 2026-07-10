# dynasty_fa.py
# =========================================
# KBO Dynasty - FA 시스템 (일괄 처리 버전)
# =========================================

import random
from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup
from dynasty_trade import trade_value

FA_CAREER_YEARS = 6
FA_RELEASE_RATE = 0.35


# =========================================
# FA 시장 생성 (오프시즌 호출)
# 자격 선수 일부를 로스터에서 일괄 해제
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

    release_ids = []
    fa_players = []

    for r in roster_rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue

        career_years = season - p["appear_season"] + 1

        if career_years < FA_CAREER_YEARS:
            continue
        if (career_years - FA_CAREER_YEARS) % 3 != 0:
            continue

        if random.random() > FA_RELEASE_RATE:
            continue

        release_ids.append(r["id"])
        fa_players.append(p)

    # 일괄 삭제 (50개 단위)
    for i in range(0, len(release_ids), 50):
        chunk = release_ids[i : i + 50]
        sb.table("dynasty_roster").delete().in_("id", chunk).execute()

    print(f"[dynasty_fa] FA 시장 방출={len(fa_players)}명")
    return fa_players


# =========================================
# 현재 FA 시장 조회
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
# AI 자동 FA 영입 (일괄 처리)
# 로스터 조회 1회 → 메모리에서 배분 → insert 일괄
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

    # 팀별 로스터 인원 한 번에 조회
    roster_rows = (
        sb.table("dynasty_roster")
        .select("team_id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    counts = {tid: 0 for tid in ai_team_ids}
    for r in roster_rows:
        if r["team_id"] in counts:
            counts[r["team_id"]] += 1

    fa_players = get_fa_players(save_id)
    fa_players.sort(key=lambda p: -trade_value(p, season))

    insert_rows = []

    for p in fa_players:
        needy = [tid for tid in ai_team_ids if counts[tid] < 25]
        if not needy:
            break

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

        needy.sort(key=lambda tid: counts[tid])
        pool = needy[: min(3, len(needy))]
        target = random.choice(pool)

        insert_rows.append(
            {
                "save_id": save_id,
                "team_id": target,
                "player_id": p["id"],
                "role": "BENCH",
                "depth": 99,
            }
        )
        counts[target] += 1

    # 일괄 insert
    for i in range(0, len(insert_rows), 100):
        sb.table("dynasty_roster").insert(insert_rows[i : i + 100]).execute()

    # 라인업 재생성은 rookie_finish에서 전 팀 대상으로 이미 실행되므로 여기선 생략
    print(f"[dynasty_fa] AI FA 영입={len(insert_rows)}명")
    return len(insert_rows)
