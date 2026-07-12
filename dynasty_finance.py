# dynasty_finance.py
# =========================================
# KBO Dynasty - Phase 1: 팬 + 통합 예산
#
# 팬 변동 (시즌 종료 시):
#   우승 +25% / 2~3위 +10% / 4~6위 +3% / 7~8위 -3% / 9~10위 -8%
#   스타(OVR 80+) 1명당 +3%
#   최소 3,000 / 최대 200,000
#
# 예산 (시즌 시작 시):
#   400 + 순위보상(1위 0 ~ 10위 150) + fans/100
# =========================================

from dynasty_utils import get_supabase, get_standings

FAN_MIN = 3000
FAN_MAX = 200000

BUDGET_BASE = 400
RANK_BONUS_STEP = 150 / 9  # 1위 0 ~ 10위 150


# =========================================
# 시즌 종료 시 팬 변동 (record_season_history 이후,
# 팀 성적 리셋 이전에 호출)
# =========================================
def update_fans(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    standings = get_standings(teams)

    try:
        from dynasty_legacy import rival_fan_bonus
        save_row = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]
        rv_bonus = rival_fan_bonus(save_id, save_row["season"])
    except Exception:
        rv_bonus = {}

    # 팀별 스타 수 (OVR 80+ 로스터 보유)
    roster_rows = (
        sb.table("dynasty_roster")
        .select("team_id, dynasty_player(overall)")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    stars = {}
    for r in roster_rows:
        p = r["dynasty_player"]
        if p and p["overall"] >= 80:
            stars[r["team_id"]] = stars.get(r["team_id"], 0) + 1

    rows = []
    for i, t in enumerate(standings):
        rank = i + 1
        fans = t.get("fans") or 10000

        if rank == 1:
            rate = 0.25
        elif rank <= 3:
            rate = 0.10
        elif rank <= 6:
            rate = 0.03
        elif rank <= 8:
            rate = -0.03
        else:
            rate = -0.08

        rate += stars.get(t["id"], 0) * 0.03
        rate += rv_bonus.get(t["id"], 0.0)

        # (rate += stars... 다음에)
        try:
            from dynasty_staff import get_staff_effects
            _fx = get_staff_effects(save_id)
            rate += _fx.get(t["id"], {}).get("fan_bonus", 0.0)
        except Exception:
            pass

        try:
            from dynasty_facility import get_facility_effects
            rate += get_facility_effects(save_id).get(t["id"], {}).get("fan_bonus", 0.0)
        except Exception:
            pass

        fans = int(fans * (1 + rate))
        fans = max(FAN_MIN, min(FAN_MAX, fans))

        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["fans"] = fans
        rows.append(row)

    sb.table("dynasty_team").upsert(rows).execute()
    print(f"[dynasty_finance] 팬 갱신: {[(r['team_name'], r['fans']) for r in rows]}")


# =========================================
# 시즌 시작 예산 지급 (기존 reset_budgets 대체)
# update_fans 이후에 호출
# =========================================
def grant_season_budget(save_id):
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
        fans = t.get("fans") or 10000

        budget = int(
            BUDGET_BASE
            + (rank - 1) * RANK_BONUS_STEP
            + fans / 100
        )

        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budget
        rows.append(row)

    sb.table("dynasty_team").upsert(rows).execute()
    print(f"[dynasty_finance] 예산 지급: {[(r['team_name'], r['budget']) for r in rows]}")
