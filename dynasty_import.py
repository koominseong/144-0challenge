# dynasty_import.py - Part1
# =========================================
# KBO Dynasty - 실존 선수 Import
# Season1 = 1982~1989 (80년대 전체)
# Season2 = 1990~1992, Season3 = 1993~1995 ...
# 실존 데이터 부족/소진 시 랜덤 생성 선수로 보충
# =========================================

import os
import re
import json
import glob
import random
import hashlib
from dynasty_utils import get_supabase

# 시즌 연도 매핑
SEASON1_YEARS = list(range(1982, 1990))   # 80년대 전체
NEXT_BASE_YEAR = 1990                      # Season2 시작 연도
YEARS_PER_SEASON = 3

# 최소 보장 인원 (부족하면 랜덤 생성으로 채움)
MIN_PLAYERS_FIRST = 280   # 10팀 × 25라운드 = 250 + 여유
MIN_PLAYERS_NEXT = 150     # 신인 드래프트 풀

BATTER_POS = {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH", "OF", "IF"}
PITCHER_POS = {"P", "SP", "RP", "CP"}

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

YEAR_RE = re.compile(r"(19\d{2}|20\d{2})")


# =========================================
# 데이터 폴더 탐색
# =========================================
def find_data_dir():
    env_dir = os.environ.get("KBO_DATA_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    candidates = [
        os.path.join(_BASE_DIR, "data", "kbo_json_v5"),
        os.path.join(_BASE_DIR, "Data", "kbo_json_v5"),
        os.path.join(_BASE_DIR, "kbo_json_v5"),
        os.path.join(_BASE_DIR, "data"),
        os.path.join(_BASE_DIR, "static", "data", "kbo_json_v5"),
    ]
    for c in candidates:
        if os.path.isdir(c) and glob.glob(os.path.join(c, "*.json")):
            return c

    for root, dirs, files in os.walk(_BASE_DIR):
        depth = root[len(_BASE_DIR):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        if os.path.basename(root) == "kbo_json_v5":
            if glob.glob(os.path.join(root, "*.json")):
                return root

    return None


DATA_DIR = find_data_dir()


# =========================================
# 시즌 → 연도 범위
# =========================================
def season_years(season):
    if season == 1:
        return SEASON1_YEARS
    start = NEXT_BASE_YEAR + (season - 2) * YEARS_PER_SEASON
    return list(range(start, start + YEARS_PER_SEASON))


# =========================================
# 파일명에서 연도 추출
# =========================================
def _file_year(path):
    m = YEAR_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


# =========================================
# 특정 연도들의 JSON 전부 로드
# =========================================
def _load_year_records(years):
    records = []

    if DATA_DIR is None:
        print("[dynasty_import] ERROR: 데이터 폴더를 찾지 못했습니다.")
        return records

    all_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    target = set(years)

    matched = [f for f in all_files if _file_year(f) in target]

    print(f"[dynasty_import] DATA_DIR={DATA_DIR}")
    print(f"[dynasty_import] 전체 json={len(all_files)}개, 연도 {years[0]}~{years[-1]} 매칭={len(matched)}개")

    for path in matched:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[dynasty_import] 파일 읽기 실패: {os.path.basename(path)} ({e})")
            continue

        if isinstance(data, list):
            records.extend(data)
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    records.extend(v)
                    break
            else:
                records.append(data)

    print(f"[dynasty_import] 로드된 선수 기록={len(records)}건")
    return records


# =========================================
# 선수 키 (이름+원소속팀)
# =========================================
def _player_key(rec):
    return f"{rec.get('name', '')}|{rec.get('team', '')}"


# =========================================
# 값 클램프
# =========================================
def _clamp(v, lo=20, hi=99):
    return max(lo, min(hi, int(round(v))))


# =========================================
# 랜덤 선수 생성용 이름 풀
# =========================================
SURNAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
    "전", "고", "문", "손", "양", "배", "백", "허", "유", "남",
]

GIVEN_FIRST = [
    "민", "성", "정", "재", "동", "현", "승", "진", "태", "종",
    "영", "상", "병", "광", "용", "석", "창", "기", "우", "형",
]

GIVEN_SECOND = [
    "수", "호", "훈", "석", "일", "규", "철", "만", "식", "환",
    "혁", "준", "범", "권", "빈", "욱", "찬", "율", "국", "섭",
]

RANDOM_BATTER_POS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]

# dynasty_import.py - Part2

# =========================================
# 같은 선수의 여러 해 기록 병합
# =========================================
def _merge_records(recs):
    recs = sorted(recs, key=lambda r: r.get("Year", 0) or 0)

    merged = {
        "name": recs[0].get("name", ""),
        "team": recs[0].get("team", ""),
        "first_year": recs[0].get("Year", 1982),
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
            try:
                merged["war"] += float(w)
            except (TypeError, ValueError):
                pass

        if r.get("AVG") is not None:
            try:
                avg_list.append(float(r["AVG"]))
            except (TypeError, ValueError):
                pass
        if r.get("ops") is not None:
            try:
                ops_list.append(float(r["ops"]))
            except (TypeError, ValueError):
                pass
        if r.get("ERA") is not None:
            try:
                era_list.append(float(r["ERA"]))
            except (TypeError, ValueError):
                pass

        for k in ("HR", "SB", "SO", "PA"):
            v = r.get(k)
            if v is not None:
                try:
                    merged[k] += int(v)
                except (TypeError, ValueError):
                    pass

        ip = r.get("IP")
        if ip is not None:
            try:
                merged["IP"] += float(ip)
            except (TypeError, ValueError):
                pass

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
# 타자 스탯 → 능력치 변환
# =========================================
def _batter_stats(merged, rng):
    avg = merged["AVG"]
    ops = merged["ops"]
    hr = merged["HR"] or 0
    sb_cnt = merged["SB"] or 0
    pa = merged["PA"] or 0
    years = max(1, merged["years"])

    hr_py = hr / years
    sb_py = sb_cnt / years

    if avg is not None:
        contact = 55 + (avg - 0.240) * 333
    else:
        contact = 45 + rng.randint(-5, 5)

    if ops is not None:
        power = 50 + (ops - 0.650) * 125
    else:
        power = 45 + rng.randint(-5, 5)
    power += min(15, hr_py * 1.2)

    if ops is not None:
        eye = 48 + (ops - 0.650) * 110
    else:
        eye = 45 + rng.randint(-5, 5)

    speed = 45 + min(45, sb_py * 1.5)

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
# =========================================
def _pitcher_stats(merged, rng):
    era = merged["ERA"]
    ip = merged["IP"] or 0.0
    so = merged["SO"] or 0
    years = max(1, merged["years"])

    ip_py = ip / years
    so9 = (so / ip * 9) if ip > 0 else 4.0

    if era is not None:
        stuff = 55 + (4.50 - era) * 11.5
    else:
        stuff = 45 + rng.randint(-5, 5)
    stuff += (so9 - 5.0) * 2.0

    if era is not None:
        control = 53 + (4.50 - era) * 9.0
    else:
        control = 45 + rng.randint(-5, 5)
    control += rng.randint(-5, 5)

    stamina = 36 + min(56, ip_py * 0.27)

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
# overall / potential / positions
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


def _calc_potential(overall, merged, rng):
    war_py = merged["war"] / max(1, merged["years"])

    if war_py >= 4.0:
        bonus = rng.randint(8, 15)
    elif war_py >= 2.0:
        bonus = rng.randint(4, 10)
    elif war_py >= 0.5:
        bonus = rng.randint(2, 6)
    else:
        bonus = rng.randint(0, 4)

    return _clamp(overall + bonus, overall, 99)


def _positions_str(merged, is_pitcher):
    pos = merged["positions"]
    if is_pitcher:
        return "P"
    cleaned = [p for p in pos if p in BATTER_POS]
    if not cleaned:
        cleaned = ["DH"]
    result = []
    for p in cleaned:
        if p == "OF":
            p = "LF"
        elif p == "IF":
            p = "2B"
        if p not in result:
            result.append(p)
    return ",".join(result[:3])


# =========================================
# 랜덤 선수 생성 (실존 데이터 부족 시 보충)
# =========================================
def _make_random_name(rng, used_names):
    for _ in range(60):
        name = (
            rng.choice(SURNAMES)
            + rng.choice(GIVEN_FIRST)
            + rng.choice(GIVEN_SECOND)
        )
        if name not in used_names:
            used_names.add(name)
            return name
    base = rng.choice(SURNAMES) + rng.choice(GIVEN_FIRST) + rng.choice(GIVEN_SECOND)
    n = 2
    while f"{base}{n}" in used_names:
        n += 1
    name = f"{base}{n}"
    used_names.add(name)
    return name


# =========================================
# [교체] 랜덤 선수 overall 분포 (실존 선수 수준으로 상향)
# 엘리트 8%, 상위 25%, 중위 45%, 하위 22%
# =========================================
def _roll_random_overall(rng):
    r = rng.random()
    if r < 0.08:
        return rng.randint(78, 90)
    if r < 0.33:
        return rng.randint(65, 80)
    if r < 0.78:
        return rng.randint(55, 70)
    return rng.randint(46, 65)

# =========================================
# [교체] 랜덤 선수 생성 (능력치 하향 재계산 방지)
# 목표 overall을 정하고 개별 능력치를 그 주변에 배치한 뒤
# overall은 재계산하지 않고 목표값 유지
# =========================================
def _make_random_player(rng, used_names, save_id, season):
    is_pitcher = rng.random() < 0.42
    name = _make_random_name(rng, used_names)
    overall = _roll_random_overall(rng)
    potential = _clamp(overall + rng.randint(3, 20), overall, 99)

    def v(spread=8):
        return _clamp(overall + rng.randint(-spread, spread))

    if is_pitcher:
        positions = "P"
        stats = {
            "stuff": v(), "control": v(), "stamina": v(),
            "defense": _clamp(overall + rng.randint(-12, 4)),
            "arm": v(),
            "contact": 25, "power": 25, "eye": 25,
            "speed": _clamp(40 + rng.randint(-10, 10), 20, 75),
        }
    else:
        main_pos = rng.choice(RANDOM_BATTER_POS)
        positions = main_pos
        if rng.random() < 0.3:
            sub = rng.choice([p for p in RANDOM_BATTER_POS if p != main_pos])
            positions = main_pos + "," + sub
        stats = {
            "contact": v(), "power": v(), "eye": v(),
            "speed": v(), "defense": v(), "arm": v(),
            "stuff": 25, "control": 25, "stamina": 25,
        }

    return {
        "save_id": save_id,
        "name": name,
        "positions": positions,
        "overall": overall,
        "potential": potential,
        "war": 0,
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

# dynasty_import.py - Part3

# =========================================
# 시즌 선수 Import (메인 진입점)
# 실존 선수 로드 → 부족분 랜덤 생성으로 보충
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
        print(f"[dynasty_import] season {season} 이미 {existing}명 등록됨 → skip")
        return 0

    min_players = MIN_PLAYERS_FIRST if season == 1 else MIN_PLAYERS_NEXT

    years = season_years(season)
    records = _load_year_records(years)

    # 이전 시즌에 이미 등장한 선수 이름 수집
    prev_players = (
        sb.table("dynasty_player")
        .select("name")
        .eq("save_id", save_id)
        .lt("appear_season", season)
        .execute()
        .data
    )
    prev_names = {p["name"] for p in prev_players}

    seed = f"{save_id}-{season}"
    rng = random.Random(hashlib.md5(seed.encode()).hexdigest())

    rows = []
    used_names = set(prev_names)
    skipped_prev = 0

    # ---------- 실존 선수 ----------
    if records:
        grouped = {}
        for rec in records:
            if not isinstance(rec, dict) or not rec.get("name"):
                continue
            key = _player_key(rec)
            grouped.setdefault(key, []).append(rec)

        print(f"[dynasty_import] 고유 실존 선수={len(grouped)}명")

        for key, recs in grouped.items():
            merged = _merge_records(recs)
            name = merged["name"]

            if name in prev_names:
                skipped_prev += 1
                continue

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
    else:
        print(f"[dynasty_import] season {season}: 실존 기록 없음 → 전원 랜덤 생성")

    real_count = len(rows)

    # ---------- 부족분 랜덤 생성 ----------
    random_count = 0
    while len(rows) < min_players:
        rows.append(_make_random_player(rng, used_names, save_id, season))
        random_count += 1

    # ---------- insert ----------
    inserted = 0
    for i in range(0, len(rows), 100):
        chunk = rows[i : i + 100]
        try:
            sb.table("dynasty_player").insert(chunk).execute()
            inserted += len(chunk)
        except Exception as e:
            print(f"[dynasty_import] insert 실패 ({i}~{i+len(chunk)}): {e}")

    print(
        f"[dynasty_import] season {season} 완료: 등록={inserted}명 "
        f"(실존={real_count}, 랜덤생성={random_count}, 이전시즌중복 skip={skipped_prev})"
    )
    return inserted
