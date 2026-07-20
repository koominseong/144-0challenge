# scout.py
# =========================================
# KBO Dynasty - 스카우트 블라인드 테스트 v3
# 랜덤 연도 + 드래프트 순번 추첨 + 웨이브제 + 함정 카드
# AI: 진짜 가치(WAR)를 노이즈 낀 채로 보는 3단계 안목
# =========================================

import os
import json
import random
import glob


def find_data_dir():
    env = os.environ.get("KBO_DATA_DIR")
    if env and os.path.isdir(env):
        return env
    base = os.path.dirname(os.path.abspath(__file__))
    for cand in [os.path.join(base, "Data", "kbo_json_v5"),
                 os.path.join(base, "data", "kbo_json_v5"),
                 os.path.join(base, "kbo_json_v5")]:
        if os.path.isdir(cand):
            return cand
    return None


ROUNDS = 5
AI_SCOUTS = 3
WAVE_SIZE = 15
POOL_SIZE = ROUNDS * WAVE_SIZE   # 40
PITCHER_POS = {"P", "SP", "RP", "CP"}

# AI 안목: WAR을 얼마나 정확히 보는가 (0=겉기록만, 1=완벽)
AI_SKILL = {"ai1": 0.75, "ai2": 0.5, "ai3": 0.25}


# =========================================
# 연도 랜덤 선택 + 풀 로드
# =========================================
def load_year_pool():
    data_dir = find_data_dir()
    if not data_dir:
        return None, []

    files = glob.glob(os.path.join(data_dir, "*.json"))
    years = sorted({os.path.basename(f).rsplit("_", 1)[-1].replace(".json", "")
                    for f in files})
    years = [y for y in years if y.isdigit()]
    if not years:
        return None, []

    year = random.choice(years)
    players = []
    for f in files:
        if not f.endswith(f"_{year}.json"):
            continue
        try:
            with open(f, encoding="utf-8") as fp:
                rows = json.load(fp)
        except Exception:
            continue
        if isinstance(rows, list):
            players.extend(rows)

    return year, players


# =========================================
# 힌트: 실제 기록 그대로
# =========================================
def build_hint(p):
    pos_list = p.get("positions") or []
    is_pitcher = bool(set(pos_list) & PITCHER_POS) or (p.get("IP") or 0) > 0

    if is_pitcher:
        era = p.get("ERA")
        so = p.get("SO") or 0
        ip = p.get("IP") or 0
        return {"type": "P",
                "ERA": f"{era:.2f}" if era is not None else "-",
                "SO": int(so),
                "IP": f"{ip:.0f}"}
    else:
        avg = p.get("AVG")
        ops = p.get("ops")
        return {"type": "B",
                "AVG": f"{avg:.3f}" if avg is not None else "-",
                "OPS": f"{ops:.3f}" if ops is not None else "-",
                "HR": int(p.get("HR") or 0),
                "SB": int(p.get("SB") or 0)}


def _apparent_raw(p):
    """원본 레코드 기준 겉보기 점수 (함정 카드 선별용)"""
    ip = p.get("IP") or 0
    if ip > 0:
        era = p.get("ERA")
        if era is None:
            return 0
        return (6.0 - era) * 20 + (p.get("SO") or 0) * 0.15
    avg = p.get("AVG")
    if avg is None:
        return 0
    return avg * 250 + (p.get("HR") or 0) * 1.5 + (p.get("SB") or 0) * 0.8


# =========================================
# 라운드 생성
# =========================================
def create_round():
    year, players = load_year_pool()
    if not year:
        return None

    players = [p for p in players
               if (p.get("PA") or 0) >= 30 or (p.get("IP") or 0) >= 15]
    if len(players) < POOL_SIZE:
        return None

    players.sort(key=lambda p: -(p.get("war") or 0))
    third = max(1, len(players) // 3)
    top = players[:third]
    mid = players[third: 2 * third]
    low = players[2 * third:]

    # 함정 카드: 하위 WAR인데 겉기록 화려한 선수 3장 보장
    traps = sorted(low, key=lambda p: -_apparent_raw(p))[:3]
    low_rest = [p for p in low if p not in traps]

    pool = (random.sample(top, min(13, len(top)))
            + random.sample(mid, min(14, len(mid)))
            + traps
            + random.sample(low_rest, min(10, len(low_rest))))
    random.shuffle(pool)
    pool = pool[:POOL_SIZE]

    cards = []
    for i, p in enumerate(pool):
        pos_list = p.get("positions") or []
        war = round(float(p.get("war") or 0), 2)
        cards.append({
            "cid": i,
            "wave": i // WAVE_SIZE + 1,
            "hint": build_hint(p),
            "positions": "/".join(pos_list) if pos_list else "?",
            "name": p.get("name"),
            "team": p.get("team_kr") or p.get("team") or "?",
            "war": war,
        })

    return {
        "year": year,
        "cards": cards,
        "picks": {"user": [], "ai1": [], "ai2": [], "ai3": []},
        "order": _snake_order(),
        "turn": 0,
        "done": False,
    }


def _snake_order():
    seats = ["user", "ai1", "ai2", "ai3"]
    random.shuffle(seats)
    order = []
    for r in range(ROUNDS):
        order += seats if r % 2 == 0 else seats[::-1]
    return order


def current_round(state):
    return min(ROUNDS, state["turn"] // (AI_SCOUTS + 1) + 1)


# =========================================
# AI 평가/픽
# =========================================
def _apparent_score(c):
    h = c["hint"]
    try:
        if h["type"] == "P":
            era = float(h["ERA"])
            return (6.0 - era) * 20 + h["SO"] * 0.15
        else:
            avg = float(h["AVG"])
            return avg * 250 + h["HR"] * 1.5 + h["SB"] * 0.8
    except (ValueError, TypeError):
        return 0


def _ai_eval(c, skill):
    apparent = _apparent_score(c) / 8.0     # WAR×10 스케일 근사 정규화
    true_val = c["war"] * 10
    noise = random.gauss(0, 6) * (1 - skill)
    return true_val * skill + apparent * (1 - skill) + noise


def _ai_pick(seat, avail):
    skill = AI_SKILL.get(seat, 0.5)
    return max(avail, key=lambda c: _ai_eval(c, skill))


# =========================================
# 픽 진행
# =========================================
def advance(state, user_cid=None):
    cards = {c["cid"]: c for c in state["cards"]}
    taken = {cid for picks in state["picks"].values() for cid in picks}

    while state["turn"] < len(state["order"]):
        seat = state["order"][state["turn"]]
        rnd = current_round(state)

        if seat == "user":
            if user_cid is None:
                return state
            c = cards.get(user_cid)
            if user_cid in taken or c is None or c["wave"] > rnd:
                return state
            state["picks"]["user"].append(user_cid)
            taken.add(user_cid)
            user_cid = None
        else:
            avail = [c for c in state["cards"]
                     if c["cid"] not in taken and c["wave"] <= rnd]
            if not avail:
                break
            pick = _ai_pick(seat, avail)
            state["picks"][seat].append(pick["cid"])
            taken.add(pick["cid"])

        state["turn"] += 1

    if state["turn"] >= len(state["order"]):
        state["done"] = True
    return state


# =========================================
# 채점: WAR 기반 + 발굴 보너스
# =========================================
def score_round(state):
    cards = {c["cid"]: c for c in state["cards"]}
    ranked = sorted(state["cards"], key=lambda c: -c["war"])
    war_rank = {c["cid"]: i + 1 for i, c in enumerate(ranked)}

    results = {}
    for seat, picks in state["picks"].items():
        total = 0
        detail = []
        for order_idx, cid in enumerate(picks):
            c = cards[cid]
            base = c["war"] * 10
            overall_pick_no = order_idx * 4
            steal_bonus = max(0, (overall_pick_no - war_rank[cid]) * 1.5)
            pts = base + steal_bonus
            total += pts
            detail.append({
                "name": c["name"], "team": c["team"], "positions": c["positions"],
                "war": c["war"], "war_rank": war_rank[cid],
                "hint": c["hint"],
                "pts": round(pts, 1),
            })
        results[seat] = {"total": round(total, 1), "detail": detail}

    user_total = results["user"]["total"]
    others = sorted((r["total"] for s, r in results.items() if s != "user"), reverse=True)
    place = 1 + sum(1 for o in others if o > user_total)

    if place == 1 and others and user_total >= others[0] + 12:
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
