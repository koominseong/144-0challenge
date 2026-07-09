# dynasty_import.py
# =========================================
# KBO Dynasty - 선수 Import
# Season별 실존 선수 데이터 생성/등록
# 실제 연도 1982~ 를 3년 단위로 Season에 매핑
# 실선수 데이터 소스가 없을 경우 절차적 생성으로 대체
# =========================================

import random
import hashlib
from dynasty_utils import get_supabase

# Season1 = 1982~1984, Season2 = 1985~1987 ...
BASE_YEAR = 1982
YEARS_PER_SEASON = 3

PLAYERS_PER_SEASON_FIRST = 320   # 시즌1 (초기 드래프트 풀)
PLAYERS_PER_SEASON_NEXT = 60     # 시즌2 이후 (신인 풀)

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

BATTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


# =========================================
# 시즌 선수 Import (메인 진입점)
# 이미 해당 시즌 선수가 있으면 skip
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

    if season == 1:
        count = PLAYERS_PER_SEASON_FIRST
    else:
        count = PLAYERS_PER_SEASON_NEXT

    year_start = BASE_YEAR + (season - 1) * YEARS_PER_SEASON

    rows = []
    seed = f"{save_id}-{season}"
    rng = random.Random(hashlib.md5(seed.encode()).hexdigest())

    used_names = set()

    for i in range(count):
        is_pitcher = rng.random() < 0.42

        name = _make_name(rng, used_names)

        if season == 1:
            overall = _roll_overall(rng, elite_chance=0.06)
        else:
            overall = _roll_overall(rng, elite_chance=0.10, rookie=True)

        potential = min(99, overall + rng.randint(0, 22))

        if is_pitcher:
            positions = "P"
            stats = _make_pitcher_stats(rng, overall)
        else:
            main_pos = rng.choice(BATTER_POSITIONS)
            positions = main_pos
            # 멀티 포지션 30%
            if rng.random() < 0.3:
                sub = rng.choice(
                    [p for p in BATTER_POSITIONS if p != main_pos]
                )
                positions = main_pos + "," + sub
            stats = _make_batter_stats(rng, overall)

        rows.append(
            {
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
        )

    for i in range(0, len(rows), 100):
        sb.table("dynasty_player").insert(rows[i : i + 100]).execute()

    return len(rows)


# =========================================
# 이름 생성 (중복 방지)
# =========================================
def _make_name(rng, used_names):
    for _ in range(50):
        name = (
            rng.choice(SURNAMES)
            + rng.choice(GIVEN_FIRST)
            + rng.choice(GIVEN_SECOND)
        )
        if name not in used_names:
            used_names.add(name)
            return name
    # 극단적 중복 시 숫자 접미
    base = rng.choice(SURNAMES) + rng.choice(GIVEN_FIRST) + rng.choice(GIVEN_SECOND)
    n = 2
    while f"{base}{n}" in used_names:
        n += 1
    name = f"{base}{n}"
    used_names.add(name)
    return name


# =========================================
# overall 분포
# 평균 58~62, 엘리트 소수
# =========================================
def _roll_overall(rng, elite_chance=0.06, rookie=False):
    r = rng.random()
    if r < elite_chance:
        return rng.randint(78, 92)
    if r < elite_chance + 0.20:
        return rng.randint(68, 77)
    if r < elite_chance + 0.55:
        return rng.randint(56, 67)
    if rookie:
        return rng.randint(42, 58)
    return rng.randint(40, 55)


# =========================================
# 타자 능력치 생성
# =========================================
def _make_batter_stats(rng, overall):
    def v():
        return max(20, min(99, overall + rng.randint(-10, 10)))

    return {
        "contact": v(),
        "power": v(),
        "eye": v(),
        "speed": v(),
        "defense": v(),
        "arm": v(),
        "stuff": 25,
        "control": 25,
        "stamina": 25,
    }


# =========================================
# 투수 능력치 생성
# =========================================
def _make_pitcher_stats(rng, overall):
    def v():
        return max(20, min(99, overall + rng.randint(-10, 10)))

    return {
        "stuff": v(),
        "control": v(),
        "stamina": v(),
        "defense": max(20, min(99, overall + rng.randint(-15, 5))),
        "arm": v(),
        "contact": 25,
        "power": 25,
        "eye": 25,
        "speed": max(20, min(80, overall + rng.randint(-25, 0))),
    }
