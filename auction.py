# auction.py

import json
import math
import random
import time
from copy import deepcopy


# ============================================================
# AUCTION CONFIG
# ============================================================

INITIAL_BUDGET = 100
ROUNDS = 12

BID_TIMEOUT = 5.0

BID_AMOUNTS = (1, 3, 5)


AI_NAMES = {
    "veteran": "베테랑",
    "data": "데이터파",
    "gambler": "승부사",
}


# ============================================================
# AI PROFILES
# ============================================================

AI_PROFILES = {

    # 안정적으로 좋은 선수 위주
    "veteran": {
        "aggression": 0.78,
        "star_bias": 1.05,
        "risk": 0.65,
        "randomness": 0.08,
    },

    # 효율을 중요시
    "data": {
        "aggression": 0.62,
        "star_bias": 0.92,
        "risk": 0.45,
        "randomness": 0.05,
    },

    # 가끔 미친 듯이 지름
    "gambler": {
        "aggression": 1.00,
        "star_bias": 1.18,
        "risk": 0.95,
        "randomness": 0.25,
    },
}


# ============================================================
# PLAYER POOL
# ============================================================

def load_players():

    paths = (
        "player_pool.json",
        "data/player_pool.json",
    )

    data = None

    for path in paths:

        try:

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

            break

        except FileNotFoundError:
            continue

    if data is None:

        raise FileNotFoundError(
            "player_pool.json을 찾을 수 없습니다."
        )

    if isinstance(data, list):

        return data

    if isinstance(data, dict):

        for key in (
            "players",
            "player_pool",
            "data",
            "pool",
        ):

            value = data.get(key)

            if isinstance(value, list):

                return value

    raise ValueError(
        "player_pool.json의 선수 데이터 형식이 올바르지 않습니다."
    )


# ============================================================
# PLAYER HELPERS
# ============================================================

def player_name(player):

    return str(
        player.get(
            "name",
            player.get(
                "player_name",
                player.get(
                    "NAME",
                    "이름없음",
                ),
            ),
        )
    )


def player_position(player):

    return str(
        player.get(
            "position",
            player.get(
                "pos",
                player.get(
                    "POSITION",
                    "UTIL",
                ),
            ),
        )
    )


def player_team(player):

    return str(
        player.get(
            "team",
            player.get(
                "TEAM",
                "-",
            ),
        )
    )


def player_overall(player):

    for key in (
        "overall",
        "ovr",
        "rating",
        "OVR",
        "Overall",
    ):

        value = player.get(key)

        if value is None:
            continue

        try:

            return float(value)

        except (
            ValueError,
            TypeError,
        ):

            pass

    return 70.0


def player_value(player):

    """
    OVR → 기본 경매 가치

    70 OVR ≈ 4P
    80 OVR ≈ 7P
    90 OVR ≈ 10P
    """

    ovr = player_overall(player)

    return max(
        1.0,
        (ovr - 55.0) * 0.30,
    )


# ============================================================
# BID LOG
# ============================================================

def add_bid_log(
    state,
    bidder,
    price,
    amount=None,
):

    if bidder == "user":

        name = "나"

    else:

        name = AI_NAMES.get(
            bidder,
            bidder,
        )

    log = {

        "bidder": bidder,

        "name": name,

        "price": int(price),

        "amount": (
            int(amount)
            if amount is not None
            else None
        ),

        "timestamp": time.time(),

    }

    state.setdefault(
        "bid_log",
        [],
    ).append(log)

    # 한 화면에 너무 많지 않게
    state["bid_log"] = state[
        "bid_log"
    ][-20:]


# ============================================================
# CURRENT PLAYER
# ============================================================

def get_current_player(state):

    players = state.get(
        "players",
        [],
    )

    index = state.get(
        "player_index",
        0,
    )

    if not players:
        return None

    if index < 0:
        index = 0

    if index >= len(players):
        return None

    return players[index]


# ============================================================
# TIMER
# ============================================================

def reset_timer(state):

    state["bid_deadline"] = (
        time.time()
        + state.get(
            "bid_timeout",
            BID_TIMEOUT,
        )
    )


def seconds_left(state):

    deadline = state.get(
        "bid_deadline",
        0,
    )

    return max(
        0,
        deadline - time.time(),
    )


def is_bid_expired(state):

    return (
        seconds_left(state)
        <= 0
    )


# ============================================================
# CREATE GAME
# ============================================================

def create_game():

    players = load_players()

    # 원본 변경 방지
    players = [
        deepcopy(player)
        for player in players
    ]

    random.shuffle(players)

    total_rounds = min(
        ROUNDS,
        len(players),
    )

    players = players[
        :total_rounds
    ]

    current = (
        players[0]
        if players
        else None
    )

    state = {

        # --------------------------------------------
        # 기본
        # --------------------------------------------

        "round": 1,

        "total_rounds": total_rounds,

        "player_index": 0,

        "players": players,

        "current": current,

        # --------------------------------------------
        # USER
        # --------------------------------------------

        "budget": INITIAL_BUDGET,

        "roster": [],

        # --------------------------------------------
        # AI
        # --------------------------------------------

        "ai_budgets": {
            key: INITIAL_BUDGET
            for key in AI_NAMES
        },

        "ai_rosters": {
            key: []
            for key in AI_NAMES
        },

        # --------------------------------------------
        # CURRENT AUCTION
        # --------------------------------------------

        "price": 1,

        "leader": None,

        "bid_log": [],

        "bid_timeout": BID_TIMEOUT,

        "bid_deadline": (
            time.time()
            + BID_TIMEOUT
        ),

        # --------------------------------------------
        # GAME
        # --------------------------------------------

        "message": (
            "경매가 시작되었습니다."
        ),

        "history": [],

        "finished": False,

        "result": None,

    }

    return state


# ============================================================
# AI MAX BID
# ============================================================

def ai_max_bid(
    ai_key,
    player,
    state,
):

    profile = AI_PROFILES[
        ai_key
    ]

    budget = state[
        "ai_budgets"
    ][ai_key]

    if budget <= 1:

        return 0

    ovr = player_overall(
        player
    )

    base = player_value(
        player
    )

    remaining_rounds = max(
        1,
        state["total_rounds"]
        - state["round"]
        + 1,
    )

    # 남겨둘 최소 예산
    reserve = max(
        5,
        budget * 0.08,
    )

    usable = max(
        0,
        budget - reserve,
    )

    # 스타 선수 선호
    star_multiplier = (
        1.0
        + (
            max(
                0,
                ovr - 75,
            )
            / 100.0
            * profile["star_bias"]
        )
    )

    target = (
        base
        * profile["aggression"]
        * star_multiplier
    )

    # 막판이면 조금 공격적으로
    if remaining_rounds <= 3:

        target *= 1.15

    # 초반에는 예산 아낌
    elif remaining_rounds >= 9:

        target *= 0.90

    # 랜덤 성향
    randomness = profile[
        "randomness"
    ]

    target *= random.uniform(
        1.0 - randomness,
        1.0 + randomness,
    )

    target = min(
        target,
        usable,
    )

    return max(
        0,
        int(
            math.floor(target)
        ),
    )


# ============================================================
# AI SHOULD BID
# ============================================================

def ai_should_bid(
    ai_key,
    player,
    current_price,
    state,
):

    budget = state[
        "ai_budgets"
    ].get(
        ai_key,
        0,
    )

    if budget <= current_price:
        return False

    maximum = ai_max_bid(
        ai_key,
        player,
        state,
    )

    return maximum > current_price


# ============================================================
# AI RESPONSE
# ============================================================

def ai_response(state):

    player = get_current_player(
        state
    )

    if not player:
        return None

    current_price = state.get(
        "price",
        1,
    )

    candidates = []

    for ai_key in AI_NAMES:

        if not ai_should_bid(
            ai_key,
            player,
            current_price,
            state,
        ):

            continue

        maximum = ai_max_bid(
            ai_key,
            player,
            state,
        )

        candidates.append(
            (
                ai_key,
                maximum,
            )
        )

    # 아무 AI도 안 올라옴
    if not candidates:

        return None

    # 최고 의향가가 높은 AI
    candidates.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    ai_key, maximum = candidates[0]

    # AI도 한 번에 너무 많이 올리지 않음
    possible_amounts = [
        amount
        for amount in BID_AMOUNTS
        if current_price + amount
        <= maximum
        and current_price + amount
        <= state[
            "ai_budgets"
        ][ai_key]
    ]

    if not possible_amounts:

        return None

    # 기본 +1
    amount = 1

    # 승부사/스타 선수는 가끔 크게
    profile = AI_PROFILES[
        ai_key
    ]

    if (
        profile["risk"] > 0.8
        and random.random() < 0.25
        and 3 in possible_amounts
    ):

        amount = 3

    elif (
        profile["risk"] > 0.9
        and random.random() < 0.10
        and 5 in possible_amounts
    ):

        amount = 5

    if amount not in possible_amounts:

        amount = max(
            possible_amounts
        )

    new_price = (
        current_price
        + amount
    )

    # --------------------------------------------
    # AI 입찰
    # --------------------------------------------

    state["price"] = new_price

    state["leader"] = ai_key

    add_bid_log(
        state,
        ai_key,
        new_price,
        amount,
    )

    reset_timer(state)

    state["message"] = (
        f"🤖 {AI_NAMES[ai_key]} "
        f"+{amount}P! "
        f"현재 {new_price}P"
    )

    return ai_key


# ============================================================
# USER BID
# ============================================================

def user_bid(
    state,
    amount,
):

    if state.get("finished"):
        return state

    player = get_current_player(
        state
    )

    if not player:

        finish_game(state)

        return state

    try:

        amount = int(amount)

    except (
        ValueError,
        TypeError,
    ):

        amount = 1

    if amount not in BID_AMOUNTS:

        state["message"] = (
            "올릴 금액이 올바르지 않습니다."
        )

        return state

    current_price = state.get(
        "price",
        1,
    )

    new_price = (
        current_price
        + amount
    )

    # 예산
    if new_price > state[
        "budget"
    ]:

        state["message"] = (
            f"예산 부족! "
            f"현재 보유 "
            f"{state['budget']}P"
        )

        return state

    # --------------------------------------------
    # USER BID
    # --------------------------------------------

    state["price"] = new_price

    state["leader"] = "user"

    add_bid_log(
        state,
        "user",
        new_price,
        amount,
    )

    reset_timer(state)

    state["message"] = (
        f"👤 나 +{amount}P → "
        f"{new_price}P"
    )

    # --------------------------------------------
    # AI 응답
    #
    # 딱 한 번만 반응
    # --------------------------------------------

    ai_response(state)

    return state


# ============================================================
# PASS
# ============================================================

def user_pass(state):

    if state.get("finished"):
        return state

    # 내가 최고 입찰자일 때 PASS
    if state.get(
        "leader"
    ) == "user":

        state["message"] = (
            "입찰을 포기했습니다."
        )

        # AI에게 현재 가격으로 낙찰될 수 있게
        ai = ai_response(state)

        if ai:

            return state

        # 아무 AI도 못 사면
        # 그냥 현재 최고였던 내가 낙찰되는 것을
        # 방지하기 위해 자동 낙찰 처리
        #
        # PASS는 경매 포기이므로
        # 다음 가능한 AI가 가져간다.
        settle_after_pass(
            state
        )

        return state

    # AI가 최고일 때 PASS
    if state.get(
        "leader"
    ) not in (
        None,
        "user",
    ):

        state["message"] = (
            f"{AI_NAMES.get(state['leader'], state['leader'])}"
            "에게 낙찰되었습니다."
        )

        settle_current_auction(
            state
        )

        return state

    # 아무도 입찰 안 했다면
    ai = ai_response(state)

    if ai:

        return state

    # 정말 아무도 안 삼
    next_round(state)

    return state


# ============================================================
# PASS AFTER USER
# ============================================================

def settle_after_pass(state):

    player = get_current_player(
        state
    )

    if not player:

        next_round(state)

        return

    candidates = []

    for ai_key in AI_NAMES:

        budget = state[
            "ai_budgets"
        ].get(
            ai_key,
            0,
        )

        if budget >= state[
            "price"
        ]:

            maximum = ai_max_bid(
                ai_key,
                player,
                state,
            )

            candidates.append(
                (
                    ai_key,
                    maximum,
                )
            )

    if candidates:

        candidates.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        winner = candidates[0][0]

        award_player(
            state,
            winner,
            state["price"],
        )

    else:

        next_round(state)


# ============================================================
# SOLD
# ============================================================

def user_sold(state):

    if state.get("finished"):
        return state

    # 내가 최고가 아니면 낙찰 불가
    if state.get(
        "leader"
    ) != "user":

        state["message"] = (
            "현재 최고 입찰자가 아닙니다."
        )

        return state

    # 현재 가격으로 낙찰
    settle_current_auction(
        state
    )

    return state


# ============================================================
# SETTLE CURRENT AUCTION
# ============================================================

def settle_current_auction(state):

    player = get_current_player(
        state
    )

    if not player:

        finish_game(state)

        return

    winner = state.get(
        "leader"
    )

    price = int(
        state.get(
            "price",
            1,
        )
    )

    # 아무도 없으면
    if winner is None:

        next_round(state)

        return

    # --------------------------------------------
    # USER
    # --------------------------------------------

    if winner == "user":

        if price > state[
            "budget"
        ]:

            state["message"] = (
                "예산 부족으로 낙찰할 수 없습니다."
            )

            next_round(state)

            return

        award_player(
            state,
            "user",
            price,
        )

        next_round(state)

        return

    # --------------------------------------------
    # AI
    # --------------------------------------------

    ai_budget = state[
        "ai_budgets"
    ].get(
        winner,
        0,
    )

    if price > ai_budget:

        # AI가 돈이 없으면
        # 유저에게 기회
        state["leader"] = None

        state["message"] = (
            "AI의 예산이 부족합니다."
        )

        reset_timer(state)

        return

    award_player(
        state,
        winner,
        price,
    )

    next_round(state)


# ============================================================
# AWARD PLAYER
# ============================================================

def award_player(
    state,
    winner,
    price,
):

    player = get_current_player(
        state
    )

    if not player:
        return

    player_copy = deepcopy(
        player
    )

    player_copy["cost"] = int(
        price
    )

    player_copy[
        "auction_price"
    ] = int(price)

    # --------------------------------------------
    # USER
    # --------------------------------------------

    if winner == "user":

        state["budget"] -= price

        state[
            "roster"
        ].append(
            player_copy
        )

        winner_name = "나"

    # --------------------------------------------
    # AI
    # --------------------------------------------

    else:

        state[
            "ai_budgets"
        ][winner] -= price

        state[
            "ai_rosters"
        ][winner].append(
            player_copy
        )

        winner_name = AI_NAMES.get(
            winner,
            winner,
        )

    # --------------------------------------------
    # HISTORY
    # --------------------------------------------

    history_item = {

        "round":
            state["round"],

        "player":
            player_name(player),

        "position":
            player_position(player),

        "team":
            player_team(player),

        "overall":
            player_overall(player),

        "price":
            int(price),

        "winner":
            winner,

        "winner_name":
            winner_name,

        "bid_log":
            deepcopy(
                state.get(
                    "bid_log",
                    [],
                )
            ),

    }

    state[
        "history"
    ].append(
        history_item
    )

    state["message"] = (
        f"🔨 {winner_name} "
        f"→ {player_name(player)} "
        f"{price}P 낙찰!"
    )


# ============================================================
# NEXT ROUND
# ============================================================

def next_round(state):

    state[
        "player_index"
    ] += 1

    state[
        "round"
    ] += 1

    state[
        "leader"
    ] = None

    state[
        "price"
    ] = 1

    state[
        "bid_log"
    ] = []

    # --------------------------------------------
    # 종료
    # --------------------------------------------

    if (
        state["round"]
        > state["total_rounds"]
    ):

        finish_game(
            state
        )

        return

    player = get_current_player(
        state
    )

    if not player:

        finish_game(
            state
        )

        return

    state[
        "current"
    ] = player

    reset_timer(
        state
    )

    state["message"] = (
        f"ROUND {state['round']} "
        f"— {player_name(player)} 등장!"
    )


# ============================================================
# GENERIC USER ACTION
# ============================================================

def user_action(
    state,
    action,
):

    if state.get("finished"):
        return state

    # --------------------------------------------
    # TIMER CHECK
    # --------------------------------------------

    if is_bid_expired(state):

        # 최고 입찰자가 있으면 자동 낙찰
        if state.get("leader"):

            settle_current_auction(
                state
            )

            return state

        # 아무도 없으면
        # AI가 마지막으로 반응
        ai = ai_response(
            state
        )

        if ai:

            return state

        next_round(
            state
        )

        return state

    # --------------------------------------------
    # BID
    # --------------------------------------------

    if action in (
        "1",
        "3",
        "5",
    ):

        return user_bid(
            state,
            int(action),
        )

    # --------------------------------------------
    # SOLD
    # --------------------------------------------

    if action == "sold":

        return user_sold(
            state
        )

    # --------------------------------------------
    # PASS
    # --------------------------------------------

    if action == "pass":

        return user_pass(
            state
        )

    # --------------------------------------------
    # UNKNOWN
    # --------------------------------------------

    state["message"] = (
        "알 수 없는 행동입니다."
    )

    return state


# ============================================================
# ROSTER SCORE
# ============================================================

def roster_score(roster):

    if not roster:
        return 0.0

    total_ovr = sum(
        player_overall(player)
        for player in roster
    )

    total_cost = sum(
        float(
            player.get(
                "cost",
                1,
            )
        )
        for player in roster
    )

    count = len(roster)

    average_ovr = (
        total_ovr
        / count
    )

    # 선수 수 보너스
    roster_bonus = min(
        count * 1.5,
        12,
    )

    # 선수 퀄리티
    quality_bonus = max(
        0,
        average_ovr - 70,
    ) * 0.45

    # 영입 효율
    efficiency = (
        total_ovr
        /
        max(
            1,
            total_cost,
        )
    )

    efficiency_bonus = min(
        efficiency * 3,
        15,
    )

    return round(
        average_ovr
        + roster_bonus
        + quality_bonus
        + efficiency_bonus,
        2,
    )


# ============================================================
# BEST SIGNING
# ============================================================

def find_best_signing(
    roster
):

    if not roster:
        return None

    best = None

    best_value = -999999

    for player in roster:

        ovr = player_overall(
            player
        )

        cost = float(
            player.get(
                "cost",
                1,
            )
        )

        value = (
            ovr
            /
            max(
                1,
                cost,
            )
        )

        if value > best_value:

            best_value = value

            best = deepcopy(
                player
            )

            best["value"] = round(
                value,
                2,
            )

    return best


# ============================================================
# GRADE
# ============================================================

def calculate_grade(
    rank,
    score,
    results,
):

    if not results:
        return "D"

    top_score = float(
        results[0]["score"]
    )

    second_score = (
        float(
            results[1]["score"]
        )
        if len(results) > 1
        else top_score
    )

    # --------------------------------------------
    # S+
    #
    # 압도적인 1위
    # --------------------------------------------

    if (
        rank == 1
        and score >= 105
        and score - second_score >= 10
    ):

        return "S+"

    # --------------------------------------------
    # 1위
    # --------------------------------------------

    if rank == 1:

        return "S"

    # --------------------------------------------
    # 2위
    # --------------------------------------------

    if rank == 2:

        if score >= 95:
            return "A+"

        return "A"

    # --------------------------------------------
    # 3위
    # --------------------------------------------

    if rank == 3:

        if score >= 90:
            return "B+"

        return "B"

    # --------------------------------------------
    # 4위
    # --------------------------------------------

    if score >= 85:
        return "B"

    if score >= 75:
        return "C"

    return "D"


# ============================================================
# FINISH GAME
# ============================================================

def finish_game(state):

    if state.get(
        "finished"
    ):

        return state

    results = []

    # --------------------------------------------
    # USER
    # --------------------------------------------

    user_roster = state.get(
        "roster",
        [],
    )

    user_budget = state.get(
        "budget",
        INITIAL_BUDGET,
    )

    results.append({

        "key": "user",

        "name": "나",

        "score": roster_score(
            user_roster
        ),

        "roster": deepcopy(
            user_roster
        ),

        "is_user": True,

        "spent": (
            INITIAL_BUDGET
            - user_budget
        ),

        "remaining": user_budget,

    })

    # --------------------------------------------
    # AI
    # --------------------------------------------

    for ai_key, ai_name in AI_NAMES.items():

        roster = state[
            "ai_rosters"
        ].get(
            ai_key,
            [],
        )

        budget = state[
            "ai_budgets"
        ].get(
            ai_key,
            INITIAL_BUDGET,
        )

        results.append({

            "key": ai_key,

            "name": ai_name,

            "score": roster_score(
                roster
            ),

            "roster": deepcopy(
                roster
            ),

            "is_user": False,

            "spent": (
                INITIAL_BUDGET
                - budget
            ),

            "remaining": budget,

        })

    # --------------------------------------------
    # SCORE SORT
    # --------------------------------------------

    results.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    # --------------------------------------------
    # RANK
    # --------------------------------------------

    for index, result in enumerate(
        results,
        start=1,
    ):

        result[
            "rank"
        ] = index

    # --------------------------------------------
    # GRADE
    # --------------------------------------------

    for result in results:

        result[
            "grade"
        ] = calculate_grade(
            result["rank"],
            result["score"],
            results,
        )

    # --------------------------------------------
    # USER RESULT
    # --------------------------------------------

    user = next(
        item
        for item in results
        if item["is_user"]
    )

    if user["rank"] == 1:

        if len(results) > 1:

            margin = (
                user["score"]
                - results[1]["score"]
            )

        else:

            margin = 0

    else:

        margin = (
            user["score"]
            - results[0]["score"]
        )

    user["win_margin"] = round(
        margin,
        2,
    )

    user["efficiency"] = round(
        user["score"]
        /
        max(
            1,
            user["spent"],
        ),
        2,
    )

    best_signing = find_best_signing(
        user["roster"]
    )

    # --------------------------------------------
    # RESULT
    # --------------------------------------------

    state["result"] = {

        "user": user,

        "results": results,

        "best_bargain":
            best_signing,

        "history":
            deepcopy(
                state.get(
                    "history",
                    [],
                )
            ),

    }

    state[
        "finished"
    ] = True

    state[
        "message"
    ] = (
        "🏆 경매 시즌 종료!"
    )

    return state
