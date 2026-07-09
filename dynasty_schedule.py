# dynasty_schedule.py
# =========================================
# KBO Dynasty - 일정 생성 / 조회
# =========================================

import random
from dynasty_utils import get_supabase


# =========================================
# 시즌 일정 생성
# 10팀 → 매주 5경기 × 24주 = 120경기
# 라운드 로빈 방식 순환
# =========================================
def generate_schedule(save_id, season, total_weeks):
    sb = get_supabase()

    # 기존 시즌 일정 제거 (재생성 대비)
    sb.table("dynasty_schedule").delete().eq("save_id", save_id).eq(
        "season", season
    ).execute()

    teams = (
        sb.table("dynasty_team")
        .select("id")
        .eq("save_id", save_id)
        .order("id")
        .execute()
        .data
    )
    team_ids = [t["id"] for t in teams]

    n = len(team_ids)
    rounds = _round_robin(team_ids)

    rows = []
    week = 1
    round_idx = 0

    while week <= total_weeks:
        pairs = rounds[round_idx % len(rounds)]

        # 순환 반복 시 홈/원정 교대
        flip = (round_idx // len(rounds)) % 2 == 1

        for home, away in pairs:
            if flip:
                home, away = away, home
            rows.append(
                {
                    "save_id": save_id,
                    "season": season,
                    "week": week,
                    "home_team": home,
                    "away_team": away,
                    "home_score": 0,
                    "away_score": 0,
                    "played": False,
                }
            )

        week += 1
        round_idx += 1

    # 대량 insert 분할
    for i in range(0, len(rows), 100):
        sb.table("dynasty_schedule").insert(rows[i : i + 100]).execute()


# =========================================
# 라운드 로빈 대진 생성
# n팀 → n-1 라운드, 라운드당 n/2 경기
# =========================================
def _round_robin(team_ids):
    ids = list(team_ids)
    random.shuffle(ids)

    n = len(ids)
    if n % 2 == 1:
        ids.append(None)
        n += 1

    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a = ids[i]
            b = ids[n - 1 - i]
            if a is not None and b is not None:
                if i % 2 == 0:
                    pairs.append((a, b))
                else:
                    pairs.append((b, a))
        rounds.append(pairs)
        # 회전 (첫 번째 고정)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]

    return rounds


# =========================================
# 특정 주차 경기 조회
# =========================================
def get_week_games(save_id, season, week):
    if week < 1:
        return []

    sb = get_supabase()

    games = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .eq("week", week)
        .order("id")
        .execute()
        .data
    )
    return games


# =========================================
# 시즌 전체 경기 조회
# =========================================
def get_season_games(save_id, season):
    sb = get_supabase()

    games = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .order("week")
        .execute()
        .data
    )
    return games


# =========================================
# 특정 팀의 시즌 경기 조회
# =========================================
def get_team_games(save_id, season, team_id):
    sb = get_supabase()

    home = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .eq("home_team", team_id)
        .execute()
        .data
    )

    away = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .eq("away_team", team_id)
        .execute()
        .data
    )

    games = home + away
    games.sort(key=lambda g: g["week"])
    return games
