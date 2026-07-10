# dynasty_fa.py - Part1
# =========================================
# KBO Dynasty - FA 입찰 시스템
# 시즌 전 FA 단계: 유저+AI 동시 입찰 → 최고액 낙찰
# 원소속팀은 유효 입찰액 15% 가산 (충성 보정)
#
# 사전 준비 (Supabase SQL Editor):
#   ALTER TABLE dynasty_team ADD COLUMN IF NOT EXISTS budget int DEFAULT 100;
#   ALTER TABLE dynasty_player ADD COLUMN IF NOT EXISTS fa_from_team bigint;
# =========================================

import random
from dynasty_utils import get_supabase, get_standings
from dynasty_trade import trade_value

FA_CAREER_YEARS = 6
FA_RELEASE_RATE = 0.35
BASE_BUDGET = 100
LOYALTY_BONUS = 1.15  # 원소속팀 가산


# =========================================
# 기준 몸값 (최소 입찰가)
# =========================================
def fa_base_price(player, season):
    value = trade_value(player, season)
    return max(5, int(round(value * 0.4)))


# =========================================
# 시즌 예산 리셋 (전년도 순위 기반, 하위팀 우대)
# 1위 90 ~ 10위 117
# =========================================
def reset_budgets(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    standings = get_standings(teams)

    rows = []
    for i, t in enumerate(standings):
        rank = i + 1
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = BASE_BUDGET - 13 + rank * 3
        rows.append(row)

    sb.table("dynasty_team").upsert(rows).execute()
    print(f"[dynasty_fa] 예산 리셋 완료 ({len(rows)}팀)")


# =========================================
# FA 시장 생성 (next_season에서 호출)
# 방출 시 원소속팀 기록 (fa_from_team)
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
    from_team_updates = {}  # player_id -> team_id

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
        from_team_updates[r["player_id"]] = r["team_id"]

    for i in range(0, len(release_ids), 50):
        sb.table("dynasty_roster").delete().in_(
            "id", release_ids[i : i + 50]
        ).execute()

    # 원소속팀 기록 (팀별로 묶어 일괄 update)
    by_team = {}
    for pid, tid in from_team_updates.items():
        by_team.setdefault(tid, []).append(pid)

    for tid, pids in by_team.items():
        for i in range(0, len(pids), 100):
            sb.table("dynasty_player").update(
                {"fa_from_team": tid}
            ).in_("id", pids[i : i + 100]).execute()

    print(f"[dynasty_fa] FA 시장 방출={len(release_ids)}명")
    return len(release_ids)


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

# dynasty_fa.py - Part2

# =========================================
# FA 입찰 일괄 처리 (핵심)
# user_bids: {player_id: 입찰액} — 유저가 제출한 입찰
# 1. 각 FA 선수에 대해 AI 팀들이 관심도/예산에 따라 입찰 생성
# 2. 유저 입찰 병합
# 3. 유효 입찰액 = 입찰액 × (원소속팀이면 1.15)
# 4. 최고 유효액 팀 낙찰, 예산 차감
# return: 결과 리스트 (사이드바/화면 표시용)
# =========================================
def resolve_fa_bidding(save_id, user_bids):
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
    team_map = {t["id"]: t for t in teams}
    user_team = next(t for t in teams if t["is_user"])
    ai_team_ids = [t["id"] for t in teams if not t["is_user"]]

    budgets = {t["id"]: (t.get("budget") or 0) for t in teams}

    roster_rows = (
        sb.table("dynasty_roster")
        .select("team_id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    counts = {t["id"]: 0 for t in teams}
    for r in roster_rows:
        if r["team_id"] in counts:
            counts[r["team_id"]] += 1

    fa_players = get_fa_players(save_id)
    fa_players.sort(key=lambda p: -trade_value(p, season))

    results = []
    insert_rows = []

    for p in fa_players:
        base = fa_base_price(p, season)
        from_team = p.get("fa_from_team")

        bids = []  # (team_id, 입찰액, 유효액)

        # ----- 유저 입찰 -----
        user_bid = user_bids.get(p["id"], 0)
        if user_bid >= base and user_bid <= budgets[user_team["id"]] and counts[user_team["id"]] < 30:
            eff = user_bid * (LOYALTY_BONUS if from_team == user_team["id"] else 1.0)
            bids.append((user_team["id"], user_bid, eff))

        # ----- AI 입찰 -----
        for tid in ai_team_ids:
            if counts[tid] >= 28 or budgets[tid] < base:
                continue

            # 관심도: OVR 높을수록, 예산 여유 많을수록 참여
            if p["overall"] >= 75:
                interest = 0.8
            elif p["overall"] >= 65:
                interest = 0.5
            elif p["overall"] >= 55:
                interest = 0.25
            else:
                interest = 0.08

            # 원소속팀은 잔류 시도 확률 상승
            if from_team == tid:
                interest = min(1.0, interest + 0.25)

            if random.random() > interest:
                continue

            # 입찰액: 기준가 × 1.0~1.6, 예산 한도 내
            bid = int(base * random.uniform(1.0, 1.6))
            bid = min(bid, budgets[tid])
            if bid < base:
                continue

            eff = bid * (LOYALTY_BONUS if from_team == tid else 1.0)
            bids.append((tid, bid, eff))

        # ----- 낙찰 -----
        if not bids:
            results.append(
                {
                    "player": {
                        "name": p["name"],
                        "positions": p["positions"],
                        "overall": p["overall"],
                    },
                    "signed": False,
                    "team_name": None,
                    "logo": None,
                    "is_user": False,
                    "price": 0,
                    "loyalty": False,
                }
            )
            continue

        bids.sort(key=lambda b: -b[2])
        winner_id, price, _ = bids[0]

        budgets[winner_id] -= price
        counts[winner_id] += 1

        insert_rows.append(
            {
                "save_id": save_id,
                "team_id": winner_id,
                "player_id": p["id"],
                "role": "BENCH",
                "depth": 99,
            }
        )

        w = team_map[winner_id]
        results.append(
            {
                "player": {
                    "name": p["name"],
                    "positions": p["positions"],
                    "overall": p["overall"],
                },
                "signed": True,
                "team_name": w["team_name"],
                "logo": w["logo"],
                "is_user": w["is_user"],
                "price": price,
                "loyalty": from_team == winner_id,
            }
        )

    # ----- DB 일괄 반영 -----
    for i in range(0, len(insert_rows), 100):
        sb.table("dynasty_roster").insert(insert_rows[i : i + 100]).execute()

    budget_rows = []
    for t in teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budgets[t["id"]]
        budget_rows.append(row)
    sb.table("dynasty_team").upsert(budget_rows).execute()

    signed = sum(1 for r in results if r["signed"])
    print(f"[dynasty_fa] FA 입찰 완료: 낙찰={signed} / 전체={len(results)}")
    return results
