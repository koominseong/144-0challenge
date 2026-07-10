# dynasty_fa.py - Part1
# =========================================
# KBO Dynasty - FA 입찰 시스템 (안정화 재작성판, 예산 750 기준)
#
# 사전 준비 (Supabase SQL Editor):
#   ALTER TABLE dynasty_team ADD COLUMN IF NOT EXISTS budget int DEFAULT 750;
#
#   -- 기존 세이브 즉시 반영:
#   UPDATE dynasty_team SET budget = 750 WHERE save_id = <내 세이브 id>;
#
#   ALTER TABLE dynasty_player ADD COLUMN IF NOT EXISTS fa_from_team bigint;
#
# 개선점:
# 1. AI 예산 방어: 예산이 낮거나 NULL인 AI 팀은 기본 예산으로
#    보정 후 참여 (전원 유찰 방지)
# 2. 유저 입찰 사전 검증: 예산 총합 초과 시 가치 낮은 순으로
#    자동 제외 (조용한 무효 방지)
# 3. 상세 로그: 유찰 원인 추적 가능
# =========================================

import random
from dynasty_utils import get_supabase, get_standings
from dynasty_trade import trade_value

FA_CAREER_YEARS = 6        # FA 자격 연차
FA_RELEASE_RATE = 0.35     # 자격자 중 시장에 나오는 비율
BASE_BUDGET = 750          # 기본 예산
LOYALTY_BONUS = 1.15       # 원소속팀 유효 입찰액 가산
AI_MIN_BUDGET = 300        # AI 예산이 이 밑이면 기본 예산으로 보정
# 상단 상수 (추가/변경)
MAX_ROSTER = 50            # 절대 상한
OFFSEASON_ROSTER = 45      # 오프시즌 정리 목표
AI_BID_CAP = 55            # AI는 이 인원 미만일 때만 입찰

# resolve_fa_bidding 안에서 두 곳 수정:
#   유저 조건: counts[user_team["id"]] < 30  →  < MAX_ROSTER
#   AI 조건:   counts[tid] >= 28             →  >= AI_BID_CAP

# =========================================
# 기준 몸값 (최소 입찰가)
# OVR 70 → 약 18, OVR 75 → 약 23, OVR 80 → 약 27
# =========================================
def fa_base_price(player, season):
    value = trade_value(player, season)
    return max(3, int(round(value * 0.22)))


# =========================================
# 시즌 예산 리셋 (next_season에서 호출)
# 전년도 1위 690 ~ 10위 825 (하위팀 우대)
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
        row["budget"] = BASE_BUDGET - 75 + rank * 15
        rows.append(row)

    sb.table("dynasty_team").upsert(rows).execute()
    print(f"[dynasty_fa] 예산 리셋: {[(r['team_name'], r['budget']) for r in rows]}")


# =========================================
# FA 시장 생성 (next_season에서 호출)
# 방출 시 원소속팀 기록
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
    from_team_updates = {}

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

# =========================================
# FA 입찰 일괄 처리 (핵심)
# user_bids: {player_id: 입찰액}
#
# 처리 순서:
# 0. AI 예산 방어 보정 (낮거나 NULL이면 기본 예산 지급)
# 1. 유저 입찰 사전 검증 (최소가 미달 제외, 총합 초과 시 가치 낮은 순 제외)
# 2. 선수별로 유저+AI 입찰 수집
# 3. 유효액 = 입찰액 × (원소속팀 1.15)
# 4. 최고 유효액 낙찰, 예산 차감
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

    # ----- 0. 예산 로드 + AI 예산 방어 보정 -----
    budgets = {}
    for t in teams:
        b = t.get("budget")
        if b is None:
            b = 0
        if not t["is_user"] and b < AI_MIN_BUDGET:
            print(f"[dynasty_fa] AI 예산 보정: {t['team_name']} {b} → {BASE_BUDGET}")
            b = BASE_BUDGET
        budgets[t["id"]] = b

    print(f"[dynasty_fa] 입찰 시작. 예산: {[(team_map[tid]['team_name'], b) for tid, b in budgets.items()]}")

    # ----- 로스터 인원 -----
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

    # ----- FA 명단 -----
    fa_players = get_fa_players(save_id)
    fa_players.sort(key=lambda p: -trade_value(p, season))
    fa_map = {p["id"]: p for p in fa_players}

    # ----- 1. 유저 입찰 사전 검증 -----
    valid_bids = {}
    for pid, amount in user_bids.items():
        p = fa_map.get(pid)
        if p is None:
            print(f"[dynasty_fa] 유저 입찰 무효(시장에 없음): player_id={pid}")
            continue
        base = fa_base_price(p, season)
        if amount < base:
            print(f"[dynasty_fa] 유저 입찰 무효(최소가 미달): {p['name']} {amount} < {base}")
            continue
        valid_bids[pid] = amount

    # 총합 예산 초과 시 가치 낮은 선수부터 제외
    total = sum(valid_bids.values())
    user_budget = budgets[user_team["id"]]
    if total > user_budget:
        print(f"[dynasty_fa] 유저 입찰 총합 초과: {total} > {user_budget} → 하위 입찰 제외")
        ordered = sorted(
            valid_bids.keys(),
            key=lambda pid: trade_value(fa_map[pid], season),
        )
        for pid in ordered:
            if total <= user_budget:
                break
            total -= valid_bids[pid]
            print(f"[dynasty_fa]   제외: {fa_map[pid]['name']} (입찰 {valid_bids[pid]})")
            del valid_bids[pid]

    # ----- 2~4. 선수별 입찰 판정 -----
    results = []
    insert_rows = []

    for p in fa_players:
        base = fa_base_price(p, season)
        from_team = p.get("fa_from_team")

        bids = []  # (team_id, 입찰액, 유효액)

        # 유저 입찰 (인원 제한 없음, 예산만 검사)
        user_bid = valid_bids.get(p["id"], 0)
        if user_bid >= base and user_bid <= budgets[user_team["id"]]:
            eff = user_bid * (LOYALTY_BONUS if from_team == user_team["id"] else 1.0)
            bids.append((user_team["id"], user_bid, eff))

        # AI 입찰 (AI_BID_CAP 미만 인원 팀만 참여)
        for tid in ai_team_ids:
            if counts[tid] >= AI_BID_CAP or budgets[tid] < base:
                continue

            if p["overall"] >= 75:
                interest = 0.8
            elif p["overall"] >= 65:
                interest = 0.5
            elif p["overall"] >= 55:
                interest = 0.25
            else:
                interest = 0.08

            if from_team == tid:
                interest = min(1.0, interest + 0.25)

            if random.random() > interest:
                continue

            bid = int(base * random.uniform(1.0, 1.6))
            bid = min(bid, budgets[tid])
            if bid < base:
                continue

            eff = bid * (LOYALTY_BONUS if from_team == tid else 1.0)
            bids.append((tid, bid, eff))

        # 낙찰 판정
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

        # 대어 낙찰 이벤트 기록
        if p["overall"] >= 85:
            try:
                from dynasty_event import log_event
                tag = " (잔류)" if from_team == winner_id else ""
                log_event(
                    save_id, season, 0, "fa", "💰",
                    f"FA {p['name']}(OVR {p['overall']}) → {w['team_name']} 낙찰가 {price}{tag}",
                )
            except Exception:
                pass

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


# =========================================
# 오프시즌 인원 정리: 팀당 45명으로 (하위 OVR부터 방출)
# =========================================
def release_surplus_players(save_id):
    sb = get_supabase()

    roster_rows = (
        sb.table("dynasty_roster")
        .select("id, team_id, dynasty_player(overall)")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    by_team = {}
    for r in roster_rows:
        if r["dynasty_player"]:
            by_team.setdefault(r["team_id"], []).append(r)

    release_ids = []
    for tid, rows in by_team.items():
        if len(rows) <= OFFSEASON_ROSTER:
            continue
        rows.sort(key=lambda r: r["dynasty_player"]["overall"])
        surplus = len(rows) - OFFSEASON_ROSTER
        release_ids += [r["id"] for r in rows[:surplus]]

    for i in range(0, len(release_ids), 50):
        sb.table("dynasty_roster").delete().in_(
            "id", release_ids[i : i + 50]
        ).execute()

    print(f"[dynasty_fa] 오프시즌 정리 방출={len(release_ids)}명")
