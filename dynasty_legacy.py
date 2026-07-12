# dynasty_legacy.py
# =========================================
# KBO Dynasty - Phase 9: 영구결번 + 라이벌
#
# 영구결번: 은퇴 선수 중 한 팀 8시즌+ 활약 & peak OVR 75+
#           (dynasty_player_stats 기반, 오프시즌 자동 선정)
# 라이벌: 통산 상대전적에서 경기수 가장 많고 승률 차 작은 팀
#          시즌 종료 시 라이벌전 우세 → 팬 +2%
# =========================================

from dynasty_utils import get_supabase

RETIRE_NUM_SEASONS = 8
RETIRE_NUM_PEAK = 75


# =========================================
# 영구결번 선정 (오프시즌, growth 이후 호출)
# =========================================
def grant_retired_numbers(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]
    season = save["season"]

    # 이번 시즌 은퇴자
    retired = (
        sb.table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("retired", True)
        .eq("retired_season", season)
        .execute()
        .data
    )
    if not retired:
        return 0

    # 기존 영구결번 (중복 방지)
    existing = (
        sb.table("dynasty_retired_number")
        .select("player_id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    existing_ids = {r["player_id"] for r in existing}

    teams = (
        sb.table("dynasty_team")
        .select("id, team_name, logo")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_map = {t["id"]: t for t in teams}

    granted = []

    for p in retired:
        if p["id"] in existing_ids:
            continue
        peak = p.get("peak_overall") or p["overall"]
        if peak < RETIRE_NUM_PEAK:
            continue

        # 팀별 활약 시즌 수 (개인 기록 기반)
        stats = (
            sb.table("dynasty_player_stats")
            .select("team_id, season")
            .eq("save_id", save_id)
            .eq("player_id", p["id"])
            .execute()
            .data
        )
        by_team = {}
        for s in stats:
            by_team.setdefault(s["team_id"], set()).add(s["season"])

        for tid, seasons in by_team.items():
            if len(seasons) >= RETIRE_NUM_SEASONS:
                granted.append(
                    {
                        "save_id": save_id,
                        "team_id": tid,
                        "player_id": p["id"],
                        "player_name": p["name"],
                        "seasons_played": len(seasons),
                        "peak_overall": peak,
                        "retired_season": season,
                    }
                )
                team = team_map.get(tid, {})
                try:
                    from dynasty_event import log_event
                    log_event(save_id, season, 99, "legend", "🔒",
                              f"{team.get('team_name','')} {p['name']} 영구결번! "
                              f"({len(seasons)}시즌 헌신, 최고 OVR {peak})")
                except Exception:
                    pass
                break  # 한 팀에서만

    if granted:
        sb.table("dynasty_retired_number").insert(granted).execute()

    print(f"[dynasty_legacy] 영구결번={len(granted)}명")
    return len(granted)


def get_retired_numbers(save_id, team_id=None):
    sb = get_supabase()
    q = (
        sb.table("dynasty_retired_number")
        .select("*")
        .eq("save_id", save_id)
        .order("retired_season")
    )
    if team_id:
        q = q.eq("team_id", team_id)
    return q.execute().data


# =========================================
# 라이벌 판정 (통산 전적 기반)
# return: (rival_team_dict, my_wins, rival_wins) | (None, 0, 0)
# =========================================
def get_rival(save_id, my_team_id):
    sb = get_supabase()

    games = (
        sb.table("dynasty_schedule")
        .select("home_team, away_team, home_score, away_score, played")
        .eq("save_id", save_id)
        .eq("played", True)
        .execute()
        .data
    )

    records = {}  # opponent_id -> [my_wins, opp_wins, games]
    for g in games:
        if g["home_team"] == my_team_id:
            opp = g["away_team"]
            my_s, op_s = g["home_score"], g["away_score"]
        elif g["away_team"] == my_team_id:
            opp = g["home_team"]
            my_s, op_s = g["away_score"], g["home_score"]
        else:
            continue

        rec = records.setdefault(opp, [0, 0, 0])
        rec[2] += 1
        if my_s > op_s:
            rec[0] += 1
        elif op_s > my_s:
            rec[1] += 1

    if not records:
        return None, 0, 0

    # 라이벌 = 경기수 충분(10+) 중 승률 차가 가장 팽팽한 팀
    candidates = [
        (opp, rec) for opp, rec in records.items() if rec[2] >= 10
    ]
    if not candidates:
        candidates = list(records.items())

    def tension(item):
        _, rec = item
        decided = rec[0] + rec[1]
        if decided == 0:
            return 999
        return abs(rec[0] - rec[1]) / decided  # 작을수록 팽팽

    opp_id, rec = min(candidates, key=tension)

    rival = (
        sb.table("dynasty_team")
        .select("*")
        .eq("id", opp_id)
        .execute()
        .data
    )
    return (rival[0] if rival else None), rec[0], rec[1]


# =========================================
# 라이벌전 팬 보너스 (update_fans 이전 호출 불필요 —
# dynasty_finance.update_fans에서 직접 사용)
# 이번 시즌 라이벌전 우세 팀에 +0.02 반환
# =========================================
def rival_fan_bonus(save_id, season):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("id")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_ids = [t["id"] for t in teams]

    # 통산 경기 1회 조회
    games = (
        sb.table("dynasty_schedule")
        .select("season, home_team, away_team, home_score, away_score, played")
        .eq("save_id", save_id)
        .eq("played", True)
        .execute()
        .data
    )

    # 통산 상대전적 집계
    career = {}  # (a,b) 정렬 tuple -> {a_wins, b_wins, games}
    season_rec = {}
    for g in games:
        a, b = g["home_team"], g["away_team"]
        key = (min(a, b), max(a, b))
        rec = career.setdefault(key, [0, 0, 0])  # [작은쪽 승, 큰쪽 승, 경기수]
        rec[2] += 1

        if g["home_score"] > g["away_score"]:
            winner = a
        elif g["away_score"] > g["home_score"]:
            winner = b
        else:
            winner = None

        if winner == key[0]:
            rec[0] += 1
        elif winner == key[1]:
            rec[1] += 1

        if g["season"] == season and winner is not None:
            srec = season_rec.setdefault(key, [0, 0])
            if winner == key[0]:
                srec[0] += 1
            else:
                srec[1] += 1

    # 팀별 라이벌 = 10경기+ 중 승률 차 최소 상대
    bonus = {}
    for tid in team_ids:
        best = None
        best_tension = 999
        for key, rec in career.items():
            if tid not in key or rec[2] < 10:
                continue
            decided = rec[0] + rec[1]
            if decided == 0:
                continue
            tension = abs(rec[0] - rec[1]) / decided
            if tension < best_tension:
                best_tension = tension
                best = key

        if best is None:
            continue

        srec = season_rec.get(best)
        if not srec:
            continue
        my_idx = 0 if tid == best[0] else 1
        if srec[my_idx] > srec[1 - my_idx]:
            bonus[tid] = 0.02

    return bonus
