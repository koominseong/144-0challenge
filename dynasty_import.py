# dynasty_import.py - Part1
# =========================================
# KBO Dynasty - 실존 선수 Import
# data/kbo_json_v5/팀이름_연도.json 사용
# 실제 스탯(WAR/AVG/OPS/ERA/SO/IP...) → 게임 능력치 변환
# Season1 = 1982~1984, Season2 = 1985~1987 ...
# =========================================

import os
import json
import glob
import random
import hashlib
from dynasty_utils import get_supabase

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "kbo_json_v5")

BASE_YEAR = 1982
YEARS_PER_SEASON = 3

BATTER_POS = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH", "OF", "IF"}
PITCHER_POS = {"P", "SP", "RP", "CP"}


# =========================================
# 시즌 → 연도 범위
# =========================================
def season_years(season):
    start = BASE_YEAR + (season - 1) * YEARS_PER_SEASON
    return list(range(start, start + YEARS_PER_SEASON))


# =========================================
# 특정 연도들의 JSON 전부 로드
# return: list[dict]
# =========================================
def _load_year_records(years):
    records = []
    for year in years:
        pattern = os.path.join(Data/kbo_json_v5,f"*_{year}.json")
        for path in glob.glob(pattern):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
    return records


# =========================================
# 선수 키 (동명이인 최소화: 이름+원소속팀)
# =========================================
def _player_key(rec):
    return f"{rec.get('name', '')}|{rec.get('team', '')}"


# =========================================
# 같은 선수의 여러 해 기록 병합
# =========================================
def _merge_records(recs):
    recs = sorted(recs, key=lambda r: r.get("Year", 0))

    merged = {
        "name": recs[0].get("name", ""),
        "team": recs[0].get("team", ""),
        "first_year": recs[0].get("Year", BASE_YEAR),
        "positions": [],
        "war": 0.0,
        "AVG": None,
        "ops": None,
        "ERA": None,
        "HR": 0,
        "SB": 0,
        "SO": 0,
        "IP": 0.0,
        "PA": 0,
        "years": len(recs),
    }

    pos_set = []
    avg_list = []
    ops_list = []
    era_list = []

    for r in recs:
        for p in r.get("positions") or []:
            if p not in pos_set:
                pos_set.append(p)

        w = r.get("war")
        if w is not None:
            merged["war"] += float(w)

        if r.get("AVG") is not None:
            avg_list.append(float(r["AVG"]))
        if r.get("ops") is not None:
            ops_list.append(float(r["ops"]))
        if r.get("ERA") is not None:
            era_list.append(float(r["ERA"]))

        for k in ("HR", "SB", "SO", "PA"):
            v = r.get(k)
            if v is not None:
                merged[k] += int(v)

        ip = r.get("IP")
        if ip is not None:
            merged["IP"] += float(ip)

    merged["positions"] = pos_set
    merged["AVG"] = sum(avg_list) / len(avg_list) if avg_list else None
    merged["ops"] = sum(ops_list) / len(ops_list) if ops_list else None
    merged["ERA"] = sum(era_list) / len(era_list) if era_list else None

    return merged


# =========================================
# 투수/타자 판별
# =========================================
def _is_pitcher(merged):
    pos = set(merged["positions"])
    if pos & PITCHER_POS:
        return True
    if merged["IP"] and merged["IP"] > 0:
        return True
    return False


# =========================================
# 값 클램프
# =========================================
def _clamp(v, lo=20, hi=99):
    return max(lo, min(hi, int(round(v))))

# dynasty_import.py - Part2

# =========================================
# 타자 스탯 → 능력치 변환
# AVG → contact / ops·HR → power / ops → eye
# SB → speed / 포지션 → defense·arm
# =========================================
def _batter_stats(merged, rng):
    avg = merged["AVG"]
    ops = merged["ops"]
    hr = merged["HR"] or 0
    sb = merged["SB"] or 0
    pa = merged["PA"] or 0
    years = max(1, merged["years"])

    hr_py = hr / years
    sb_py = sb / years

    # contact: 타율 0.240 → 55, 0.300 → 75, 0.330 → 85
    if avg is not None:
        contact = 55 + (avg - 0.240) * 333
    else:
        contact = 45 + rng.randint(-5, 5)

    # power: OPS 0.650 → 50, 0.850 → 75 + 홈런 보정
    if ops is not None:
        power = 50 + (ops - 0.650) * 125
    else:
        power = 45 + rng.randint(-5, 5)
    power += min(15, hr_py * 1.2)

    # eye: OPS 기반 (출루 요소 근사)
    if ops is not None:
        eye = 48 + (ops - 0.650) * 110
    else:
        eye = 45 + rng.randint(-5, 5)

    # speed: 도루 0 → 45, 20/년 → 75, 40/년 → 90
    speed = 45 + min(45, sb_py * 1.5)

    # defense/arm: 포지션 기반 + 랜덤
    pos = set(merged["positions"])
    if pos & {"C", "SS", "CF"}:
        defense = 62 + rng.randint(-6, 12)
        arm = 60 + rng.randint(-6, 12)
    elif pos & {"2B", "3B"}:
        defense = 57 + rng.randint(-7, 10)
        arm = 56 + rng.randint(-7, 10)
    else:
        defense = 50 + rng.randint(-8, 10)
        arm = 50 + rng.randint(-8, 10)

    # 표본 작은 선수 하향
    if pa and pa / years < 100:
        contact -= 6
        power -= 6
        eye -= 6

    return {
        "contact": _clamp(contact),
        "power": _clamp(power),
        "eye": _clamp(eye),
        "speed": _clamp(speed),
        "defense": _clamp(defense),
        "arm": _clamp(arm),
        "stuff": 25,
        "control": 25,
        "stamina": 25,
    }


# =========================================
# 투수 스탯 → 능력치 변환
# ERA → stuff·control / IP → stamina / SO → stuff 보정
# =========================================
def _pitcher_stats(merged, rng):
    era = merged["ERA"]
    ip = merged["IP"] or 0.0
    so = merged["SO"] or 0
    years = max(1, merged["years"])

    ip_py = ip / years
    so9 = (so / ip * 9) if ip > 0 else 4.0

    # stuff: ERA 4.50 → 55, 3.00 → 72, 2.00 → 84 + K/9 보정
    if era is not None:
        stuff = 55 + (4.50 - era) * 11.5
    else:
        stuff = 45 + rng.randint(-5, 5)
    stuff += (so9 - 5.0) * 2.0

    # control: ERA 기반 + 랜덤 분산
    if era is not None:
        control = 53 + (4.50 - era) * 9.0
    else:
        control = 45 + rng.randint(-5, 5)
    control += rng.randint(-5, 5)

    # stamina: 이닝 50/년 → 50, 150/년 → 78, 200/년 → 90
    stamina = 36 + min(56, ip_py * 0.27)

    # 표본 작은 투수 하향
    if ip_py < 20:
        stuff -= 7
        control -= 7

    defense = 45 + rng.randint(-8, 10)
    arm = 60 + rng.randint(-5, 12)

    return {
        "stuff": _clamp(stuff),
        "control": _clamp(control),
        "stamina": _clamp(stamina),
        "defense": _clamp(defense),
        "arm": _clamp(arm),
        "contact": 25,
        "power": 25,
        "eye": 25,
        "speed": _clamp(40 + rng.randint(-10, 10), 20, 75),
    }


# =========================================
# overall 계산
# =========================================
def _calc_overall(stats, is_pitcher):
    if is_pitcher:
        return _clamp(
            stats["stuff"] * 0.4
            + stats["control"] * 0.4
            + stats["stamina"] * 0.2
        )
    return _clamp(
        stats["contact"] * 0.25
        + stats["power"] * 0.25
        + stats["eye"] * 0.15
        + stats["speed"] * 0.1
        + stats["defense"] * 0.15
        + stats["arm"] * 0.1
    )


# =========================================
# potential: WAR + 기량 기반
# =========================================
def _calc_potential(overall, merged, rng):
    war_py = merged["war"] / max(1, merged["years"])

    bonus = 0
    if war_py >= 4.0:
        bonus = rng.randint(8, 15)
    elif war_py >= 2.0:
        bonus = rng.randint(4, 10)
    elif war_py >= 0.5:
        bonus = rng.randint(2, 6)
    else:
        bonus = rng.randint(0, 4)

    return _clamp(overall + bonus, overall, 99)


# =========================================
# positions 리스트 → DB 문자열
# =========================================
def _positions_str(merged, is_pitcher):
    pos = merged["positions"]
    if is_pitcher:
        return "P"
    cleaned = [p for p in pos if p in BATTER_POS]
    if not cleaned:
        cleaned = ["DH"]
    # OF/IF 일반화 포지션 구체화
    result = []
    for p in cleaned:
        if p == "OF":
            p = "LF"
        elif p == "IF":
            p = "2B"
        if p not in result:
            result.append(p)
    return ",".join(result[:3])

# dynasty_import.py - Part3

# =========================================
# 시즌 선수 Import (메인 진입점)
# 해당 시즌 연도 범위(3년치) JSON 로드
# → 선수 병합 → 능력치 변환 → insert
# 이미 등록된 시즌이면 skip
# =========================================
def import_players_for_season(save_id, season):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_player")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .eq("appear_season", season)
        .execute()
        .count
    )
    if existing and existing > 0:
        return 0

    years = season_years(season)
    records = _load_year_records(years)

    if not records:
        return 0

    # 이번 시즌 이전에 이미 등록된 선수 이름+팀 키 수집
    # (이전 시즌에 등장한 선수는 다시 넣지 않음)
    prev_players = (
        sb.table("dynasty_player")
        .select("name")
        .eq("save_id", save_id)
        .lt("appear_season", season)
        .execute()
        .data
    )
    prev_names = {p["name"] for p in prev_players}

    # 선수별 병합
    grouped = {}
    for rec in records:
        if not rec.get("name"):
            continue
        key = _player_key(rec)
        grouped.setdefault(key, []).append(rec)

    seed = f"{save_id}-{season}"
    rng = random.Random(hashlib.md5(seed.encode()).hexdigest())

    rows = []
    used_names = set()

    for key, recs in grouped.items():
        merged = _merge_records(recs)
        name = merged["name"]

        # 이전 시즌에 이미 등장한 선수 skip
        if name in prev_names:
            continue

        # 같은 시즌 내 동명이인 처리 (팀명 접미)
        if name in used_names:
            name = f"{merged['name']}({merged['team']})"
            if name in used_names:
                continue
        used_names.add(name)

        is_pitcher = _is_pitcher(merged)

        if is_pitcher:
            stats = _pitcher_stats(merged, rng)
        else:
            stats = _batter_stats(merged, rng)

        overall = _calc_overall(stats, is_pitcher)
        potential = _calc_potential(overall, merged, rng)
        positions = _positions_str(merged, is_pitcher)

        rows.append(
            {
                "save_id": save_id,
                "name": name,
                "positions": positions,
                "overall": overall,
                "potential": potential,
                "war": round(merged["war"], 2),
                "appear_season": season,
                "drafted": False,
                "retired": False,
                "contact": stats["contact"],
                "power": stats["power"],
                "eye": stats["eye"],
                "speed": stats["speed"],
                "defense": stats["defense"],
                "arm": stats["arm"],
                "stuff": stats["stuff"],
                "control": stats["control"],
                "stamina": stats["stamina"],
            }
        )

    for i in range(0, len(rows), 100):
        sb.table("dynasty_player").insert(rows[i : i + 100]).execute()

    return len(rows)
