"""144-0 Challenge - Career Simulator engine.

This module is intentionally self-contained so the existing modes are not touched.
Career state lives in Flask session; only compact JSON-compatible data is stored.
"""
from __future__ import annotations

import random
from copy import deepcopy

KBO_TEAMS = [
    ("KBO", "LG 트윈스"), ("KBO", "KT 위즈"), ("KBO", "SSG 랜더스"),
    ("KBO", "NC 다이노스"), ("KBO", "두산 베어스"), ("KBO", "KIA 타이거즈"),
    ("KBO", "롯데 자이언츠"), ("KBO", "삼성 라이온즈"), ("KBO", "한화 이글스"),
    ("KBO", "키움 히어로즈"),
]
NPB_TEAMS = [
    ("NPB", x) for x in ["한신 타이거스", "요코하마 DeNA 베이스타스", "요미우리 자이언츠",
    "주니치 드래건스", "히로시마 도요 카프", "도쿄 야쿠르트 스왈로스",
    "후쿠오카 소프트뱅크 호크스", "홋카이도 닛폰햄 파이터스", "오릭스 버펄로스",
    "도호쿠 라쿠텐 골든이글스", "사이타마 세이부 라이온스", "치바 롯데 마린스"]
]
MLB_TEAMS = [
    ("MLB", x) for x in ["애리조나 다이아몬드백스", "애틀랜타 브레이브스", "볼티모어 오리올스",
    "보스턴 레드삭스", "시카고 컵스", "시카고 화이트삭스", "신시내티 레즈", "클리블랜드 가디언스",
    "콜로라도 로키스", "디트로이트 타이거스", "휴스턴 애스트로스", "캔자스시티 로열스",
    "LA 에인절스", "LA 다저스", "마이애미 말린스", "밀워키 브루어스", "미네소타 트윈스",
    "뉴욕 메츠", "뉴욕 양키스", "오클랜드 애슬레틱스", "필라델피아 필리스", "피츠버그 파이리츠",
    "샌디에이고 파드리스", "샌프란시스코 자이언츠", "시애틀 매리너스", "세인트루이스 카디널스",
    "탬파베이 레이스", "텍사스 레인저스", "토론토 블루제이스", "워싱턴 내셔널스"]]
CPBL_TEAMS = [("CPBL", x) for x in ["CTBC 브라더스", "퉁이 라이온스", "라쿠텐 몽키스", "푸방 가디언스", "웨이취안 드래곤스", "타이강 호크스"]]

LEAGUE_TEAMS = {"KBO": KBO_TEAMS, "NPB": NPB_TEAMS, "MLB": MLB_TEAMS, "CPBL": CPBL_TEAMS}

NATIONS = {
    "KOR": "대한민국", "JPN": "일본", "USA": "미국", "TPE": "대만",
    "MEX": "멕시코", "DOM": "도미니카공화국", "VEN": "베네수엘라", "CUB": "쿠바",
    "AUS": "호주", "NED": "네덜란드", "PUR": "푸에르토리코",
}

POSITIONS = {"타자": "타자", "내야수": "내야수", "외야수": "외야수", "포수": "포수", "투수": "투수"}


def _team(league, name):
    return {"league": league, "name": name}


def create_player(name, nationality, position, age, mode, start_team):
    p = {
        "name": (name or "이름 없음").strip()[:20],
        "nationality": nationality if nationality in NATIONS else "KOR",
        "position": POSITIONS.get(position, position if position in POSITIONS.values() else "내야수"),
        "age": max(16, min(int(age), 30)),
        "mode": mode if mode in ("intense", "normal", "express") else "normal",
        "team": deepcopy(start_team),
        "ovr": random.randint(48, 61),
        "value": 0,
        "reputation": 0,
        "season": 1,
        "career_stats": {"G": 0, "H": 0, "HR": 0, "RBI": 0, "W": 0, "SO": 0, "SV": 0},
        "trophies": [],
        "timeline": [],
        "national_team": [],
        "pending_event": None,
        "retired": False,
        "retirement_reason": None,
    }
    return p


def start_career(player):
    player = deepcopy(player)
    player["value"] = _value(player["ovr"], player["reputation"])
    player["timeline"] = []
    return player


def _value(ovr, rep):
    return max(0, int((ovr - 42) ** 2 * 0.8 + rep * 120))


def _decision_every(mode):
    return {"intense": 1, "normal": 3, "express": 99}.get(mode, 3)


def _age_growth(age):
    if age <= 22: return random.randint(1, 4)
    if age <= 27: return random.randint(0, 3)
    if age <= 31: return random.randint(-1, 2)
    if age <= 35: return random.randint(-2, 1)
    return random.randint(-4, 0)


def _season_stats(p):
    o = p["ovr"]
    age = p["age"]
    pos = p["position"]
    rng = random.Random()
    stats = {"G": 0, "H": 0, "HR": 0, "RBI": 0, "W": 0, "SO": 0, "SV": 0, "AVG": "-", "ERA": "-"}
    if pos == "투수":
        g = max(8, int((o - 30) * rng.uniform(.45, .75)))
        w = max(0, int(g * rng.uniform(.25, .58)))
        so = max(5, int(g * rng.uniform(3.5, 7.8) + (o - 60) * 1.5))
        era = max(1.5, min(7.5, 5.8 - o * .045 + rng.uniform(-.7, .8) + max(0, age-31)*.08))
        sv = max(0, int(g * rng.uniform(.0, .12))) if o >= 72 else 0
        stats.update(G=g, W=w, SO=so, SV=sv, ERA=f"{era:.2f}")
    else:
        g = max(20, int((o - 28) * rng.uniform(.9, 1.25)))
        avg = max(.170, min(.380, .205 + o * .00145 + rng.uniform(-.025, .025) - max(0, age-34)*.003))
        hr = max(0, int(g * max(.002, (o-52)/260) * rng.uniform(.65, 1.2)))
        h = max(1, int(g * avg * rng.uniform(3.5, 4.7)))
        rbi = max(0, int(hr * rng.uniform(1.8, 2.7) + g * rng.uniform(.10, .25)))
        stats.update(G=g, H=h, HR=hr, RBI=rbi, AVG=f"{avg:.3f}")
    return stats


def _apply_growth(p, stats):
    old = p["ovr"]
    form = 0
    if p["position"] == "투수":
        era = float(stats["ERA"])
        form = 2 if era <= 2.8 else 1 if era <= 3.7 else -1 if era >= 5.2 else 0
    else:
        avg = float(stats["AVG"])
        form = 2 if avg >= .320 else 1 if avg >= .280 else -1 if avg < .220 else 0
    delta = _age_growth(p["age"]) + form
    p["ovr"] = max(35, min(99, old + delta))
    return p["ovr"] - old


def _maybe_awards(p, stats):
    age = p["age"]
    o = p["ovr"]
    awards = []
    if age <= 24 and o >= 68 and random.random() < .10: awards.append("신인왕")
    if o >= 78 and random.random() < .10: awards.append("골든글러브")
    if o >= 83 and random.random() < .055: awards.append("MVP")
    if o >= 76 and random.random() < .08: awards.append("한국시리즈 우승")
    if awards: p["trophies"].extend(awards)


def _eligible_event(p):
    candidates = []
    o, age, rep = p["ovr"], p["age"], p["reputation"]
    if age <= 25 and o >= 55: candidates.append("callup")
    if o >= 58: candidates.append("breakout")
    if o <= 67: candidates.append("slump")
    if o >= 70 and rep >= 10: candidates.append("national")
    if o >= 72 and rep >= 15 and p["team"]["league"] in ("KBO", "CPBL"): candidates.append("overseas")
    if o >= 78 and rep >= 25: candidates.append("contract")
    if age >= 32 and o >= 55: candidates.append("veteran")
    return random.choice(candidates) if candidates and random.random() < _event_probability(p["mode"]) else None


def _event_probability(mode):
    return {"intense": .78, "normal": .42, "express": .15}.get(mode, .42)


def _event_payload(kind, p):
    events = {
        "callup": ("1군 콜업 경쟁", "코칭스태프가 1군에서 기회를 줄지 고민하고 있습니다.", [
            ("주전 경쟁", "경쟁을 택했다.", {"ovr": 2, "reputation": 3}),
            ("차분히 육성", "성장에 집중하기로 했다.", {"ovr": 4, "reputation": 0})]),
        "breakout": ("깜짝 활약", "최근 성적이 예상보다 훨씬 좋습니다.", [
            ("공격적으로 밀어붙인다", "자신감을 앞세웠다.", {"ovr": 3, "reputation": 5}),
            ("현재 페이스를 유지한다", "안정적인 선택을 했다.", {"ovr": 2, "reputation": 3})]),
        "slump": ("슬럼프 탈출", "성적이 흔들리고 있어 선택이 필요합니다.", [
            ("훈련 방식을 바꾼다", "훈련 계획을 크게 바꿨다.", {"ovr": 4, "reputation": -1}),
            ("기존 루틴을 지킨다", "자신의 루틴을 믿었다.", {"ovr": 1, "reputation": 2})]),
        "national": ("국가대표 승선", "대표팀 후보 명단에 이름을 올렸습니다.", [
            ("대표팀에 참가한다", "국제무대에 도전했다.", {"ovr": 1, "reputation": 6, "national": True}),
            ("소속팀에 집중한다", "이번에는 팀에 남았다.", {"ovr": 2, "reputation": 2})]),
        "overseas": ("해외 구단의 관심", "해외 리그에서 영입 제안이 들어왔습니다.", [
            ("도전한다", "해외 무대에 도전했다.", {"ovr": 1, "reputation": 7, "transfer": True}),
            ("잔류한다", "소속팀에서 더 성장하기로 했다.", {"ovr": 2, "reputation": 3})]),
        "contract": ("대형 계약 협상", "커리어 가치가 크게 올라 계약 협상이 시작됐습니다.", [
            ("장기 계약", "안정적인 장기 계약을 선택했다.", {"ovr": 2, "reputation": 4, "value": 15}),
            ("단기 고액 계약", "짧고 강한 계약을 선택했다.", {"ovr": 4, "reputation": 6, "value": 8})]),
        "veteran": ("베테랑의 선택", "경험을 활용할 시기입니다.", [
            ("후배를 이끈다", "라커룸의 리더가 됐다.", {"ovr": 2, "reputation": 5}),
            ("경쟁을 계속한다", "경쟁력을 끝까지 유지했다.", {"ovr": 3, "reputation": 2})]),
    }
    title, text, choices = events[kind]
    return {"id": kind, "title": title, "text": text, "choices": [
        {"id": str(i), "label": c[0], "result": c[1], "effect": c[2]} for i, c in enumerate(choices)
    ]}


def _overseas_team():
    league = random.choice(["NPB", "MLB", "CPBL"])
    return deepcopy(random.choice(LEAGUE_TEAMS[league]))


def simulate_season(p):
    if p["retired"]:
        return p
    p = deepcopy(p)
    season_number = p["season"]
    stats = _season_stats(p)
    for k in ("G", "H", "HR", "RBI", "W", "SO", "SV"):
        p["career_stats"][k] += stats.get(k, 0)
    growth = _apply_growth(p, stats)
    _maybe_awards(p, stats)
    p["reputation"] = max(0, p["reputation"] + (2 if p["ovr"] >= 75 else 1 if p["ovr"] >= 65 else 0))
    p["value"] = _value(p["ovr"], p["reputation"])

    p["timeline"].append({
        "season": season_number, "age": p["age"], "team": p["team"]["name"],
        "league": p["team"]["league"], "ovr": p["ovr"], "stats": stats,
        "growth": growth,
    })

    p["pending_event"] = None
    if season_number % _decision_every(p["mode"]) == 0:
        kind = _eligible_event(p)
        if kind:
            p["pending_event"] = _event_payload(kind, p)

    p["age"] += 1
    p["season"] += 1
    if p["age"] >= 40 or p["ovr"] <= 37:
        p["retired"] = True
        p["retirement_reason"] = "나이와 커리어 곡선을 고려해 은퇴를 결정했습니다."
        p["pending_event"] = None
    return p


def apply_choice(p, choice_id):
    p = deepcopy(p)
    event = p.get("pending_event")
    if not event:
        return p
    try:
        choice = next(c for c in event["choices"] if c["id"] == str(choice_id))
    except StopIteration:
        return p
    effect = choice["effect"]
    p["ovr"] = max(35, min(99, p["ovr"] + effect.get("ovr", 0)))
    p["reputation"] = max(0, p["reputation"] + effect.get("reputation", 0))
    p["value"] = max(0, p["value"] + effect.get("value", 0) * 1_000_000)
    if effect.get("national"):
        p["national_team"].append({"year": p["age"], "country": NATIONS[p["nationality"]]})
    if effect.get("transfer"):
        p["team"] = _overseas_team()
    p["timeline"][-1]["event"] = {"title": event["title"], "choice": choice["label"], "result": choice["result"]}
    p["pending_event"] = None
    p["value"] = _value(p["ovr"], p["reputation"]) + effect.get("value", 0) * 1_000_000
    return p


def retire(p, reason=None):
    p = deepcopy(p)
    p["retired"] = True
    p["pending_event"] = None
    p["retirement_reason"] = reason or "스스로 현역 생활을 마무리했습니다."
    return p
