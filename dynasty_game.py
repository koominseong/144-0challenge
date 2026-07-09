# dynasty_game.py
# =========================================
# KBO Dynasty - 경기 시뮬레이션 엔진
# 능력치 평균 기반 + 랜덤 요소
# =========================================

import random
from dynasty_utils import get_supabase, calc_team_power


# =========================================
# 한 주 경기 전체 시뮬레이션
# =========================================
def simulate_week(save_id, season, week):
    sb = get_supabase()

    games = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .eq("week", week)
        .eq("played", False)
        .execute()
        .data
    )

    if not games:
        return

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_map = {t["id"]: t for t in teams}

    powers = {}
    for t in teams:
        powers[t["id"]] = _get_team_power(sb, save_id, t["id"])

    for g in games:
        home_id = g["home_team"]
        away_id = g["away_team"]

        home_score, away_score = _simulate_game(
            powers[home_id], powers[away_id]
        )

        sb.table("dynasty_schedule").update(
            {
                "home_score": home_score,
                "away_score": away_score,
                "played": True,
            }
        ).eq("id", g["id"]).execute()

        home = team_map[home_id]
        away = team_map[away_id]

        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif away_score > home_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1

    for t in teams:
        sb.table("dynasty_team").update(
            {
                "wins": t["wins"],
                "losses": t["losses"],
                "ties": t["ties"],
            }
        ).eq("id", t["id"]).execute()


# =========================================
# 팀 전력 계산 (로스터 기반)
# =========================================
def _get_team_power(sb, save_id, team_id):
    roster = (
        sb.table("dynasty_roster")
        .select("role, depth, dynasty_player(overall, positions)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .execute()
        .data
    )

    if not roster:
        return {"bat": 50.0, "pit": 50.0}

    batters = []
    pitchers = []

    for r in roster:
        p = r["dynasty_player"]
        if p is None:
            continue
        role = r["role"]
        if role in ("SP", "RP", "CP"):
            pitchers.append((role, r["depth"], p["overall"]))
        elif role == "START":
            batters.append((r["depth"], p["overall"]))

    # 주전 타자만 반영, 없으면 벤치 포함 상위 9명
    if not batters:
        all_bat = [
            (r["depth"], r["dynasty_player"]["overall"])
            for r in roster
            if r["dynasty_player"]
            and "P" not in (r["dynasty_player"]["positions"] or "")
        ]
        all_bat.sort(key=lambda x: -x[1])
        batters = all_bat[:9]

    if not pitchers:
        all_pit = [
            ("SP", r["depth"], r["dynasty_player"]["overall"])
            for r in roster
            if r["dynasty_player"]
            and "P" in (r["dynasty_player"]["positions"] or "")
        ]
        all_pit.sort(key=lambda x: -x[2])
        pitchers = all_pit[:8]

    bat_power = (
        sum(o for _, o in batters) / len(batters) if batters else 50.0
    )

    # 선발 가중치 높게
    sp = [o for role, _, o in pitchers if role == "SP"]
    bp = [o for role, _, o in pitchers if role in ("RP", "CP")]

    sp_avg = sum(sp) / len(sp) if sp else 50.0
    bp_avg = sum(bp) / len(bp) if bp else 50.0

    pit_power = sp_avg * 0.6 + bp_avg * 0.4

    return {"bat": bat_power, "pit": pit_power}


# =========================================
# 단일 경기 시뮬레이션
# 타격력 vs 상대 투수력 → 득점 기대치 → 랜덤 득점
# =========================================
def _simulate_game(home_power, away_power):
    home_exp = _expected_runs(home_power["bat"], away_power["pit"])
    away_exp = _expected_runs(away_power["bat"], home_power["pit"])

    # 홈 어드밴티지
    home_exp *= 1.05

    home_score = _random_runs(home_exp)
    away_score = _random_runs(away_exp)

    # 무승부 15% 확률로 연장 결판
    if home_score == away_score and random.random() < 0.85:
        if random.random() < home_exp / (home_exp + away_exp):
            home_score += 1
        else:
            away_score += 1

    return home_score, away_score


def _expected_runs(bat, pit):
    # 기준: 양쪽 65 → 약 4.5점
    diff = bat - pit
    base = 4.5 + diff * 0.09
    return max(1.2, min(9.0, base))


def _random_runs(expected):
    # 포아송 근사 (누적 랜덤)
    runs = 0
    remaining = expected
    while remaining > 0:
        if random.random() < min(remaining, 1.0) * 0.75:
            runs += 1
        remaining -= 1.0

    # 빅이닝 변수
    if random.random() < 0.12:
        runs += random.randint(1, 4)
    if random.random() < 0.05:
        runs = max(0, runs - random.randint(1, 2))

    return runs
