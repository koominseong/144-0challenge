# auction.py
# =========================================
# 144-0 Challenge - PLAYER AUCTION
# 가상 예산으로 선수 영입 시장을 즐기는 미니게임
# player_pool.json 기반
# =========================================

import json
import os
import random

ROUNDS = 10
START_BUDGET = 100

AI_NAMES = {
    "ai1": "🦉 베테랑",
    "ai2": "📋 정석파",
    "ai3": "🎲 승부사",
}


def load_pool():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "player_pool.json"
    )

    with open(path, encoding="utf-8") as f:
        rows = json.load(f)

    pool = []

    for p in rows:
        if not isinstance(p, dict):
            continue

        if not p.get("name"):
            continue

        try:
            overall = float(p.get("overall"))
        except (TypeError, ValueError):
            continue

        pool.append({
            "name": p["name"],
            "team": p.get("team", "?"),
            "position": p.get("position", "?"),
            "overall": round(overall, 1),
            "rank": int(p.get("rank") or 9999),
        })

    return pool


def position_group(position):
    if position in ("선발", "SP"):
        return "SP"

    if position in ("불펜", "마무리", "RP", "CP"):
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

    if position in ("좌익수", "LF"):
        return "LF"

    if position in ("중견수", "CF"):
        return "CF"

    if position in ("우익수", "RF"):
        return "RF"

    return "OF"


def start_price(player):
    """
    선수 Overall을 기준으로 시작가 결정.
    매 게임마다 약간의 랜덤 변동.
    """

    base = 2 + max(
        0,
        player["overall"] - 65
    ) * 0.38

    price = base + random.uniform(-2, 2)

    return max(
        2,
        min(
            18,
            int(round(price))
        )
    )


def ai_max_bid(player, ai, budget):
    """
    AI별 최대 입찰가.

    ai1:
        강한 선수에게 적극적

    ai2:
        가성비 중심

    ai3:
        공격적으로 베팅
    """

    overall = player["overall"]

    if ai == "ai1":
        value = (
            (overall - 60) * 0.72
            + 5
            + random.uniform(-2, 3)
        )

    elif ai == "ai2":
        value = (
            (overall - 60) * 0.60
            + 3
            + random.uniform(-2, 2)
        )

    else:
        value = (
            (overall - 60) * 0.68
            + 2
            + random.uniform(-5, 6)
        )

        if random.random() < 0.15:
            value += random.uniform(3, 8)

    return max(
        0,
        min(
            float(budget),
            round(value, 1)
        )
    )


def pick_player(pool, used):
    """
    아직 등장하지 않은 선수 중 한 명 선택.
    """

    candidates = [
        p
        for p in pool
        if p["name"] not in used
    ]

    if not candidates:
        return None

    weights = []

    for p in candidates:
        overall = p["overall"]

        weight = max(
            0.25,
            1.0 + (
                1 - abs(overall - 82) / 35
            )
        )

        weights.append(weight)

    return random.choices(
        candidates,
        weights=weights,
        k=1
    )[0]


def _next_round(state):
    player = pick_player(
        state["_pool"],
        set(state["used_names"])
    )

    if player is None:
        state["done"] = True
        return state

    state["round"] += 1

    state["used_names"].append(
        player["name"]
    )

    state["current"] = player

    state["price"] = start_price(
        player
    )

    state["leader"] = "market"

    state["ai_max"] = {
        ai: ai_max_bid(
            player,
            ai,
            state["ai_budget"][ai]
        )
        for ai in AI_NAMES
    }

    state["message"] = (
        f"{player['name']}의 "
        "영입 경쟁이 시작됐습니다."
    )

    return state


def new_game():
    pool = load_pool()

    state = {
        "round": 0,

        "budget": START_BUDGET,

        "ai_budget": {
            ai: START_BUDGET
            for ai in AI_NAMES
        },

        "roster": [],

        "ai_roster": {
            ai: []
            for ai in AI_NAMES
        },

        "used_names": [],

        "current": None,

        "price": 0,

        "leader": "market",

        "ai_max": {},

        "message": "",

        "done": False,

        # DB에는 저장하지 않는 서버 내부 데이터
        "_pool": pool,
    }

    return _next_round(state)


def public_state(state):
    """
    Supabase에 저장할 공개 게임 상태.

    player_pool 전체와
    AI의 숨겨진 최대 입찰가는 저장하지 않는다.
    """

    return {
        key: value
        for key, value in state.items()
        if key not in (
            "_pool",
            "ai_max",
        )
    }


def restore_state(state):
    """
    Supabase에서 불러온 게임 상태에
    서버의 player_pool을 다시 붙인다.
    """

    state = dict(state)

    state["_pool"] = load_pool()

    state.setdefault(
        "ai_max",
        {}
    )

    return state


def _ai_compete(state):
    """
    유저가 입찰했을 때 AI가 따라올지 결정.
    """

    challengers = [
        ai
        for ai in AI_NAMES
        if (
            state["ai_budget"][ai]
            >= state["price"]
            and
            state["ai_max"].get(ai, 0)
            > state["price"]
        )
    ]

    if not challengers:
        return None

    random.shuffle(challengers)

    for ai in challengers:

        chance = {
            "ai1": 0.78,
            "ai2": 0.62,
            "ai3": 0.70,
        }[ai]

        if random.random() > chance:
            continue

        next_price = min(
            state["ai_max"][ai],
            state["price"]
            + random.choice(
                [1, 1, 2, 3]
            )
        )

        next_price = int(
            next_price
        )

        if next_price <= state["price"]:
            continue

        state["price"] = next_price

        state["leader"] = ai

        state["message"] = (
            f"{AI_NAMES[ai]}이(가) "
            f"{next_price}억까지 "
            "따라왔습니다."
        )

        return ai

    return None


def _finish(state, winner):
    """
    현재 경매 종료.
    """

    player = state["current"]

    price = state["price"]

    if winner == "user":

        state["budget"] -= price

        state["roster"].append({
            **player,
            "price": price,
        })

        label = "🙋 나"

    elif winner in AI_NAMES:

        state["ai_budget"][winner] -= price

        state["ai_roster"][winner].append({
            **player,
            "price": price,
        })

        label = AI_NAMES[winner]

    else:
        label = "시장"

    state["message"] = (
        f"{label} · "
        f"{player['name']} · "
        f"{price}억"
    )

    state["current"] = None

    state["ai_max"] = {}

    if state["round"] >= ROUNDS:

        state["done"] = True

    else:

        _next_round(state)

    return state


def user_action(state, action):
    """
    유저의 입찰 / 포기 처리.
    """

    if (
        state.get("done")
        or not state.get("current")
    ):
        return state

    # -----------------------------
    # 포기
    # -----------------------------

    if action == "pass":

        viable = [
            ai
            for ai in AI_NAMES
            if (
                state["ai_budget"][ai]
                >= state["price"]
                and
                state["ai_max"].get(ai, 0)
                >= state["price"]
            )
        ]

        if viable:

            winner = max(
                viable,
                key=lambda ai:
                    state["ai_max"][ai]
                    + random.uniform(-1, 1)
            )

            return _finish(
                state,
                winner
            )

        state["message"] = (
            f"{state['current']['name']}"
            "은(는) 유찰됐습니다."
        )

        state["current"] = None

        if state["round"] >= ROUNDS:
            state["done"] = True
        else:
            _next_round(state)

        return state

    # -----------------------------
    # 입찰
    # -----------------------------

    try:
        increment = int(action)

    except (
        TypeError,
        ValueError
    ):
        return state

    if increment not in (
        1,
        3,
        5,
    ):
        return state

    next_price = (
        state["price"]
        + increment
    )

    if next_price > state["budget"]:

        state["message"] = (
            "현재 예산으로는 "
            "그 금액까지 올릴 수 없습니다."
        )

        return state

    state["price"] = next_price

    state["leader"] = "user"

    state["message"] = (
        f"내가 {next_price}억까지 "
        "제시했습니다."
    )

    # AI가 경쟁
    if _ai_compete(state):

        return state

    # 아무 AI도 안 따라오면 낙찰
    return _finish(
        state,
        "user"
    )


def score_game(state):
    """
    최종 점수 계산.

    전력 60%
    가성비 25%
    포지션 밸런스 15%
    """

    roster = state.get(
        "roster",
        []
    )

    total = sum(
        p["overall"]
        for p in roster
    )

    avg = (
        total / len(roster)
        if roster
        else 0
    )

    spent = (
        START_BUDGET
        - state.get(
            "budget",
            START_BUDGET
        )
    )

    if spent > 0:
        efficiency = (
            total / spent * 10
        )
    else:
        efficiency = 0

    efficiency_score = min(
        100,
        efficiency * 8
    )

    groups = [
        position_group(
            p["position"]
        )
        for p in roster
    ]

    unique = len(
        set(groups)
    )

    balance = min(
        100,
        55 + unique * 5
    )

    power_score = min(
        100,
        avg
    )

    final = round(
        power_score * 0.60
        + efficiency_score * 0.25
        + balance * 0.15,
        1
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

        "avg_overall": round(
            avg,
            1
        ),

        "total_overall": round(
            total,
            1
        ),

        "spent": spent,

        "remaining": state.get(
            "budget",
            START_BUDGET
        ),

        "efficiency": round(
            efficiency,
            1
        ),

        "balance": round(
            balance,
            1
        ),
    }
