# auction.py
# =========================================
# 144-0 Challenge - PLAYER AUCTION
# 가상 예산 100억으로 선수들을 영입하는 미니게임
# =========================================

import json
import os
import random

ROUNDS = 10
START_BUDGET = 100

AI_NAMES = {
    "ai1": "🦉 베테랑",
    "ai2": "📋 정석파",
    "ai3": "🎲 도박사",
}


def _pool_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_pool.json")


def load_pool():
    with open(_pool_path(), encoding="utf-8") as f:
        rows = json.load(f)

    return [
        {
            "name": p.get("name", "?"),
            "team": p.get("team", "?"),
            "position": p.get("position", "?"),
            "overall": float(p.get("overall") or 0),
            "rank": int(p.get("rank") or 9999),
        }
        for p in rows
        if isinstance(p, dict)
        and p.get("name")
        and p.get("overall") is not None
    ]


def _category(position):
    if position in ("선발", "SP"):
        return "SP"
    if position in ("중간", "불펜", "마무리", "RP", "CP"):
        return "RP"
    if position in ("포수", "C"):
        return "C"
    if position in ("1루", "1B"):
        return "1B"
    if position in ("2루", "2B"):
        return "2B"
    if position in ("3루", "3B"):
        return "3B"
    if position in ("유격수", "SS"):
        return "SS"
    if position in ("좌익수", "LF", "중견수", "CF", "우익수", "RF", "외야", "OF"):
        return "OF"
    return "DH"


def _start_price(player):
    # 100억 예산에서 최상위 선수도 과도하게 비싸지 않도록 3~18억
    base = 3 + max(0, player["overall"] - 65) * 0.42
    jitter = random.uniform(-2.5, 2.5)
    return max(2, min(18, int(round(base + jitter))))


def _ai_max_bid(player, ai, budget):
    overall = player["overall"]

    if ai == "ai1":
        value = overall * 0.48 + random.uniform(-2, 4)
    elif ai == "ai2":
        value = overall * 0.40 + random.uniform(-3, 3)
    else:
        value = overall * 0.55 + random.uniform(-8, 8)
        if random.random() < 0.18:
            value += random.uniform(4, 9)

    return min(budget, max(0, round(value - 30, 1)))


def _new_player(pool, used_names):
    candidates = [p for p in pool if p["name"] not in used_names]

    if not candidates:
        return None

    # 상위 선수만 몰리지 않도록 중상위권도 충분히 등장
    weights = []
    for p in candidates:
        overall = p["overall"]
        weights.append(max(0.2, 1.0 + (82 - abs(overall - 82)) / 30))

    return random.choices(candidates, weights=weights, k=1)[0]


def _init_round(state):
    player = _new_player(state["_pool"], set(state["used_names"]))

    if player is None:
        state["done"] = True
        return state

    state["used_names"].append(player["name"])
    state["round"] += 1
    state["current"] = player
    state["price"] = _start_price(player)
    state["leader"] = "시장"

    state["ai_max"] = {
        ai: _ai_max_bid(player, ai, state["ai_budget"][ai])
        for ai in AI_NAMES
    }

    state["message"] = f"{player['name']} 선수가 경매에 나왔습니다."
    return state


def new_game():
    pool = load_pool()

    state = {
        "round": 0,
        "budget": START_BUDGET,
        "ai_budget": {
            "ai1": START_BUDGET,
            "ai2": START_BUDGET,
            "ai3": START_BUDGET,
        },
        "roster": [],
        "ai_roster": {
            "ai1": [],
            "ai2": [],
            "ai3": [],
        },
        "used_names": [],
        "current": None,
        "price": 0,
        "leader": "시장",
        "ai_max": {},
        "message": "",
        "done": False,

        # 세션 저장 시 다시 저장할 필요가 없는 내부 데이터
        "_pool": pool,
    }

    return _init_round(state)


def _finish_round(state, winner):
    player = state["current"]
    price = state["price"]

    if winner == "user":
        state["budget"] -= price
        state["roster"].append({**player, "price": price})
        label = "🙋 나"
    else:
        state["ai_budget"][winner] -= price
        state["ai_roster"][winner].append({**player, "price": price})
        label = AI_NAMES[winner]

    state["message"] = f"{label}이(가) {price}억에 낙찰받았습니다."
    state["current"] = None
    state["leader"] = winner
    state["ai_max"] = {}

    if state["round"] >= ROUNDS:
        state["done"] = True
    else:
        _init_round(state)

    return state


def user_action(state, action):
    if state.get("done") or not state.get("current"):
        return state

    player = state["current"]

    if action == "pass":
        viable = [
            ai
            for ai in AI_NAMES
            if state["ai_budget"][ai] >= state["price"]
            and state["ai_max"].get(ai, 0) >= state["price"]
        ]

        if viable:
            winner = max(
                viable,
                key=lambda ai: state["ai_max"][ai] + random.uniform(-1, 1),
            )
            return _finish_round(state, winner)

        state["message"] = f"{player['name']} 선수는 유찰되었습니다."
        state["current"] = None

        if state["round"] >= ROUNDS:
            state["done"] = True
        else:
            _init_round(state)

        return state

    try:
        inc = int(action)
    except (TypeError, ValueError):
        return state

    if inc not in (1, 3, 5):
        return state

    next_price = state["price"] + inc

    if next_price > state["budget"]:
        state["message"] = "예산을 초과할 수 없습니다."
        return state

    state["price"] = next_price
    state["leader"] = "user"

    # CPU들이 자신이 정한 최대 입찰가까지 따라온다.
    challengers = [
        ai
        for ai in AI_NAMES
        if state["ai_budget"][ai] >= state["price"]
        and state["ai_max"].get(ai, 0) > state["price"]
    ]

    random.shuffle(challengers)

    for ai in challengers:
        chance = (
            0.78 if ai == "ai1"
            else 0.60 if ai == "ai2"
            else 0.68
        )

        if random.random() > chance:
            continue

        cpu_next = min(
            state["ai_max"][ai],
            state["price"] + random.choice([1, 1, 2, 3]),
        )
        cpu_next = int(cpu_next)

        if cpu_next <= state["price"]:
            continue

        state["price"] = cpu_next
        state["leader"] = ai
        state["message"] = (
            f"{AI_NAMES[ai]}이(가) {state['price']}억까지 따라왔습니다."
        )
        return state

    # 아무도 따라오지 않으면 사용자 낙찰
    return _finish_round(state, "user")


def score_game(state):
    roster = state["roster"]

    total_overall = sum(p["overall"] for p in roster)
    avg_overall = total_overall / len(roster) if roster else 0

    spent = START_BUDGET - state["budget"]
    efficiency = (total_overall / spent * 10) if spent else 0

    categories = [_category(p["position"]) for p in roster]
    counts = {c: categories.count(c) for c in set(categories)}

    balance = 100

    if len(roster) >= 6:
        if counts.get("C", 0) == 0:
            balance -= 8
        if counts.get("SS", 0) == 0:
            balance -= 8
        if counts.get("SP", 0) == 0:
            balance -= 8
        if counts.get("OF", 0) == 0:
            balance -= 8

    balance = max(0, balance)

    power = min(100, avg_overall)
    efficiency_score = min(100, efficiency * 8)

    final = round(
        power * 0.60
        + efficiency_score * 0.25
        + balance * 0.15,
        1,
    )

    if final >= 90:
        grade = "S"
    elif final >= 82:
        grade = "A"
    elif final >= 74:
        grade = "B"
    elif final >= 65:
        grade = "C"
    else:
        grade = "D"

    return {
        "final": final,
        "grade": grade,
        "avg_overall": round(avg_overall, 1),
        "total_overall": round(total_overall, 1),
        "spent": spent,
        "remaining": state["budget"],
        "efficiency": round(efficiency, 1),
        "balance": balance,
    }
