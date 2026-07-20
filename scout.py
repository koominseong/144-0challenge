# scout.py
# =========================================
# KBO Dynasty - 스카우트 블라인드 테스트
# 랜덤 연도 실존 선수 풀 → 이름/팀 가림 (기록 힌트만) → 스냅 드래프트 → 리빌/채점
# =========================================

import os
import json
import random
import glob

# dynasty_import와 동일한 데이터 탐색
def find_data_dir():
    env = os.environ.get("KBO_DATA_DIR")
    if env and os.path.isdir(env):
        return env
    for cand in ["Data/kbo_json_v5", "data/kbo_json_v5",
                 "/opt/render/project/src/Data/kbo_json_v5"]:
        if os.path.isdir(cand):
            return cand
    return None


ROUNDS = 5
AI_SCOUTS = 3          # 유저 포함 4명이 스냅 드래프트
POOL_SIZE = 28         # 라운드당 공개 풀


# =========================================
# 연도 랜덤 선택 + 풀 로드
# =========================================
def load_year_pool():
    data_dir = find_data_dir()
    if not data_dir:
        return None, []

    files = glob.glob(os.path.join(data_dir, "*.json"))
    years = sorted({f.rsplit("_", 1)[-1].replace(".json", "") for f in files})
    years = [y for y in years if y.isdigit()]
    if not years:
        return None, []

    year = random.choice(years)
    players = []
    for f in files:
        if not f.endswith(f"_{year}.json"):
            continue
        team_name = os.path.basename(f).rsplit("_", 1)[0]
        try:
            with open(f, encoding="utf-8") as fp:
                rows = json.load(fp)
        except Exception:
            continue
        for p in rows:
            p["_team"] = team_name
            players.append(p)

    return year, players


# =========================================
# 힌트 스탯: 실제 기록 필드가 있으면 사용, 없으면 능력치에서 근사
# =========================================
def _get(p, *keys):
    for k in keys:
        v = p.get(k)
        if v is not None:
            return v
    return None


def build_hint(p):
    is_pitcher = "P" in (str(p.get("positions") or p.get("position") or ""))

    if is_pitcher:
        era = _get(p, "era", "ERA")
        so = _get(p, "so", "SO", "strikeouts", "k")
        if era is None:
            stuff = p.get("stuff") or 50
            control = p.get("control") or 50
            era = round(max(1.5, 6.5 - (stuff * 0.045 + control * 0.03)), 2)
        if so is None:
            so = int(max(20, ((p.get("stuff") or 50) - 30) * 4.5 + random.randint(-10, 10)))
        return {"type": "P", "ERA": era, "SO": so}
    else:
        avg = _get(p, "avg", "AVG", "batting_avg")
        hr = _get(p, "hr", "HR", "homeruns")
        sb = _get(p, "sb", "SB", "steals")
        if avg is None:
            contact = p.get("contact") or 50
            eye = p.get("eye") or 50
            avg = round(min(0.390, max(0.180, 0.150 + contact * 0.0022 + eye * 0.0006)), 3)
        if hr is None:
            power = p.get("power") or 50
            hr = int(max(0, (power - 45) * 0.75 + random.randint(-3, 3)))
        if sb is None:
            speed = p.get("speed") or 50
            sb = int(max(0, (speed - 45) * 0.8 + random.randint(-3, 3)))
        return {"type": "B", "AVG": f"{avg:.3f}" if isinstance(avg, float) else avg, "HR": hr, "SB": sb}


# =========================================
# 라운드 생성: 풀 추출 + 가림
# state는 dynasty_live_game처럼 통째 저장 가능하지만
# 스카우트는 세션 단명이라 그냥 dict 반환 → route에서 저장
# =========================================
def create_round():
    year, players = load_year_pool()
    if not year:
        return None

    # OVR 분포 섞기: 상위/중위/하위 골고루 (전부 스타면 추리가 쉬움)
    players = [p for p in players if p.get("overall")]
    players.sort(key=lambda p: -(p.get("overall") or 0))
    top = players[: len(players) // 3]
    mid = players[len(players) // 3 : 2 * len(players) // 3]
    low = players[2 * len(players) // 3 :]
    pool = (random.sample(top, min(10, len(top)))
            + random.sample(mid, min(10, len(mid)))
            + random.sample(low, min(8, len(low))))
    random.shuffle(pool)
    pool = pool[:POOL_SIZE]

    cards = []
    for i, p in enumerate(pool):
        cards.append({
            "cid": i,
            "hint": build_hint(p),
            "positions": str(p.get("positions") or p.get("position") or "?"),
            "age_hint": _age_hint(p, year),
            # 리빌용 실체 (화면엔 절대 노출 금지)
            "name": p.get("name"),
            "team": p.get("_team"),
            "overall": p.get("overall"),
            "potential": p.get("potential") or p.get("overall"),
        })

    return {
        "year": year,
        "cards": cards,
        "picks": {"user": [], "ai1": [], "ai2": [], "ai3": []},
        "order": _snake_order(),
        "turn": 0,
        "done": False,
    }


def _age_hint(p, year):
    born = _get(p, "born", "birth_year")
    if born:
        try:
            age = int(year) - int(str(born)[:4])
            return f"{age}세"
        except Exception:
            pass
    return "?"


def _snake_order():
    seats = ["user", "ai1", "ai2", "ai3"]
    order = []
    for r in range(ROUNDS):
        order += seats if r % 2 == 0 else seats[::-1]
    return order


# =========================================
# 픽 진행: 유저 픽 반영 → AI 픽 자동 → 다음 유저 차례까지
# =========================================
def advance(state, user_cid=None):
    cards = {c["cid"]: c for c in state["cards"]}
    taken = {cid for picks in state["picks"].values() for cid in picks}

    while state["turn"] < len(state["order"]):
        seat = state["order"][state["turn"]]

        if seat == "user":
            if user_cid is None:
                return state  # 유저 입력 대기
            if user_cid in taken or user_cid not in cards:
                return state
            state["picks"]["user"].append(user_cid)
            taken.add(user_cid)
            user_cid = None
        else:
            # AI: 당해 힌트 기준 겉보기 좋은 선수 + 랜덤 (potential은 못 봄)
            avail = [c for c in state["cards"] if c["cid"] not in taken]
            if not avail:
                break
            avail.sort(key=lambda c: -_apparent_score(c))
            pick = random.choice(avail[: min(4, len(avail))])
            state["picks"][seat].append(pick["cid"])
            taken.add(pick["cid"])

        state["turn"] += 1

    if state["turn"] >= len(state["order"]):
        state["done"] = True
    return state


def _apparent_score(c):
    h = c["hint"]
    if h["type"] == "P":
        era = float(h["ERA"])
        return (6.0 - era) * 20 + h["SO"] * 0.15
    else:
        avg = float(h["AVG"])
        return avg * 250 + h["HR"] * 1.5 + h["SB"] * 0.8


# =========================================
# 채점: potential(미래 가치) 기반 + 저평가 발굴 보너스
# =========================================
def score_round(state):
    cards = {c["cid"]: c for c in state["cards"]}
    results = {}

    # 풀 전체 potential 순위 (발굴 판정용)
    ranked = sorted(state["cards"], key=lambda c: -c["potential"])
    pot_rank = {c["cid"]: i + 1 for i, c in enumerate(ranked)}

    for seat, picks in state["picks"].items():
        total = 0
        detail = []
        for order_idx, cid in enumerate(picks):
            c = cards[cid]
            base = c["potential"]
            # 발굴 보너스: 늦은 픽에 상위 잠재력
            overall_pick_no = order_idx * 4  # 대략 전체 픽 순번
            steal_bonus = max(0, (overall_pick_no - pot_rank[cid]) * 1.5)
            pts = base + steal_bonus
            total += pts
            detail.append({
                "name": c["name"], "team": c["team"], "positions": c["positions"],
                "overall": c["overall"], "potential": c["potential"],
                "pot_rank": pot_rank[cid], "pts": round(pts),
            })
        results[seat] = {"total": round(total), "detail": detail}

    user_total = results["user"]["total"]
    others = sorted(r["total"] for s, r in results.items() if s != "user")
    place = 1 + sum(1 for o in others if o > user_total)

    if place == 1 and user_total >= max(others) + 30:
        grade = "S"
    elif place == 1:
        grade = "A"
    elif place == 2:
        grade = "B"
    elif place == 3:
        grade = "C"
    else:
        grade = "D"

    return {"results": results, "place": place, "grade": grade}
