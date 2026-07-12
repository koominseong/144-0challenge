# dynasty_stats.py
# =========================================
# KBO Dynasty - Phase 5: 개인 기록 엔진
# 경기 결과(팀 득점)를 1군 선수들에게 그럴듯하게 분배
#
# 타자(START): 안타/홈런/타점/도루 — power·contact·speed 가중
# 투수: 승(SP 위주) / 패 / 세이브(CP) / 탈삼진(stuff 가중)
#
# simulate_week / simulate_rest_of_season에서 메모리로 누적 후
# 시즌 단위 upsert (on_conflict: save_id,player_id,season)
# =========================================

import random
from dynasty_utils import get_supabase


# =========================================
# 팀별 1군 라인업 로드 (기록 분배용)
# return: {team_id: {"batters":[...], "sps":[...], "cp":..., "rps":[...]}}
# =========================================
def load_lineups(sb, save_id):
    rows = (
        sb.table("dynasty_roster")
        .select("team_id, role, depth, dynasty_player(id, name, positions, overall, contact, power, speed, stuff)")
        .eq("save_id", save_id)
        .in_("role", ["START", "SP", "CP", "RP"])
        .execute()
        .data
    )

    lineups = {}
    for r in rows:
        p = r["dynasty_player"]
        if not p:
            continue
        team = lineups.setdefault(
            r["team_id"], {"batters": [], "sps": [], "cp": None, "rps": []}
        )
        if r["role"] == "START":
            team["batters"].append(p)
        elif r["role"] == "SP":
            team["sps"].append((r["depth"], p))
        elif r["role"] == "CP":
            team["cp"] = p
        elif r["role"] == "RP":
            team["rps"].append(p)

    for team in lineups.values():
        team["sps"].sort(key=lambda x: x[0])
        team["sps"] = [p for _, p in team["sps"]]

    return lineups


# =========================================
# 한 경기 기록 생성 → acc(누적 dict)에 반영
# acc: {player_id: {"team_id":.., "games":.., "hits":.., ...}}
# week: 선발 로테이션 결정용
# =========================================
def record_game(acc, lineups, home_id, away_id, home_score, away_score, week):
    _record_offense(acc, lineups.get(home_id), home_id, home_score)
    _record_offense(acc, lineups.get(away_id), away_id, away_score)

    home_win = home_score > away_score
    away_win = away_score > home_score

    _record_pitching(
        acc, lineups.get(home_id), home_id,
        won=home_win, lost=away_win, close=abs(home_score - away_score) <= 3,
        runs_allowed=away_score, week=week,
    )
    _record_pitching(
        acc, lineups.get(away_id), away_id,
        won=away_win, lost=home_win, close=abs(home_score - away_score) <= 3,
        runs_allowed=home_score, week=week,
    )


def _ensure(acc, player_id, team_id):
    if player_id not in acc:
        acc[player_id] = {
            "team_id": team_id, "games": 0, "hits": 0, "hr": 0,
            "rbi": 0, "sb": 0, "wins": 0, "losses": 0, "saves": 0, "so": 0,
        }
    return acc[player_id]


def _record_offense(acc, lineup, team_id, runs):
    if not lineup or not lineup["batters"]:
        return

    batters = lineup["batters"]

    for p in batters:
        s = _ensure(acc, p["id"], team_id)
        s["games"] += 1

    # 안타 수: 득점 기반 근사 (득점*1.8 + 잡음)
    total_hits = max(2, int(runs * 1.8 + random.randint(0, 4)))
    hit_weights = [max(20, p["contact"] or 50) for p in batters]

    for _ in range(total_hits):
        p = random.choices(batters, weights=hit_weights)[0]
        acc[p["id"]]["hits"] += 1

    # 홈런: 득점의 일부, power 가중
    hr_count = 0
    for _ in range(runs):
        if random.random() < 0.22:
            hr_count += 1
    if hr_count:
        hr_weights = [max(10, (p["power"] or 50) - 30) ** 2 for p in batters]
        for _ in range(hr_count):
            p = random.choices(batters, weights=hr_weights)[0]
            acc[p["id"]]["hr"] += 1
            acc[p["id"]]["rbi"] += random.randint(1, 3)

    # 남은 타점 분배
    remaining_rbi = max(0, runs - sum(
        0 for _ in range(hr_count)
    ) - hr_count)
    for _ in range(remaining_rbi):
        p = random.choices(batters, weights=hit_weights)[0]
        acc[p["id"]]["rbi"] += 1

    # 도루: speed 기반
    for p in batters:
        spd = p["speed"] or 40
        if spd >= 60 and random.random() < (spd - 55) / 200:
            acc[p["id"]]["sb"] += 1


def _record_pitching(acc, lineup, team_id, won, lost, close, runs_allowed, week):
    if not lineup:
        return

    sps = lineup["sps"]
    starter = sps[week % len(sps)] if sps else None
    cp = lineup["cp"]

    if starter:
        s = _ensure(acc, starter["id"], team_id)
        s["games"] += 1
        # 탈삼진: stuff 기반 4~9개
        stuff = starter["stuff"] or 50
        s["so"] += max(1, int(random.gauss(3 + stuff / 15, 1.5)))

        if won and random.random() < 0.65:
            s["wins"] += 1
        elif lost and random.random() < 0.7:
            s["losses"] += 1

    if cp and won and close and random.random() < 0.75:
        c = _ensure(acc, cp["id"], team_id)
        c["games"] += 1
        c["saves"] += 1
        c["so"] += random.randint(0, 2)


# =========================================
# 누적 기록 DB 반영 (시즌 단위 합산 upsert)
# =========================================
def flush_stats(save_id, season, acc):
    if not acc:
        return

    sb = get_supabase()

    player_ids = list(acc.keys())

    existing = {}
    for i in range(0, len(player_ids), 100):
        rows = (
            sb.table("dynasty_player_stats")
            .select("*")
            .eq("save_id", save_id)
            .eq("season", season)
            .in_("player_id", player_ids[i : i + 100])
            .execute()
            .data
        )
        for r in rows:
            existing[r["player_id"]] = r

    upserts = []
    for pid, s in acc.items():
        prev = existing.get(pid)
        row = {
            "save_id": save_id,
            "player_id": pid,
            "season": season,
            "team_id": s["team_id"],
            "games": s["games"] + (prev["games"] if prev else 0),
            "hits": s["hits"] + (prev["hits"] if prev else 0),
            "hr": s["hr"] + (prev["hr"] if prev else 0),
            "rbi": s["rbi"] + (prev["rbi"] if prev else 0),
            "sb": s["sb"] + (prev["sb"] if prev else 0),
            "wins": s["wins"] + (prev["wins"] if prev else 0),
            "losses": s["losses"] + (prev["losses"] if prev else 0),
            "saves": s["saves"] + (prev["saves"] if prev else 0),
            "so": s["so"] + (prev["so"] if prev else 0),
        }
        if prev:
            row["id"] = prev["id"]
        upserts.append(row)

    for i in range(0, len(upserts), 100):
        sb.table("dynasty_player_stats").upsert(
            upserts[i : i + 100], on_conflict="save_id,player_id,season"
        ).execute()

    print(f"[dynasty_stats] 기록 반영={len(upserts)}명")
