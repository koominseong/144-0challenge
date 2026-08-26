# auction.py

import json
import math
import random
import time
from copy import deepcopy


# ============================================================
# CONFIG
# ============================================================

INITIAL_BUDGET = 100

BID_TIMEOUT = 5.0

ROUNDS = 24

BID_AMOUNTS = (1, 3, 5)


# ============================================================
# ROSTER
# ============================================================

# OF는 LF / CF / RF 중 아무 선수나 3명
#
# 총 16명
#
# C   1
# 1B  1
# 2B  1
# 3B  1
# SS  1
# OF  3
# DH  1
# SP  3
# RP  2
# CP  1

ROSTER_LIMITS = {

    "C": 1,

    "1B": 1,

    "2B": 1,

    "3B": 1,

    "SS": 1,

    "OF": 3,

    "DH": 1,

    "SP": 3,

    "RP": 2,

    "CP": 1,
}


# ============================================================
# AI
# ============================================================

AI_NAMES = {

    "veteran":
        "베테랑",

    "data":
        "데이터파",

    "gambler":
        "승부사",
}


AI_PROFILES = {

    "veteran": {

        "aggression": 0.70,

        "star_bias": 1.00,

        "risk": 0.55,

        "randomness": 0.08,

    },

    "data": {

        "aggression": 0.58,

        "star_bias": 0.90,

        "risk": 0.35,

        "randomness": 0.04,

    },

    "gambler": {

        "aggression": 0.94,

        "star_bias": 1.18,

        "risk": 0.95,

        "randomness": 0.18,

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

            if isinstance(
                data.get(key),
                list,
            ):

                return data[key]

    raise ValueError(
        "player_pool.json 형식이 올바르지 않습니다."
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


def raw_position(player):

    value = player.get(
        "position",
        player.get(
            "pos",
            player.get(
                "POSITION",
                "",
            ),
        ),
    )

    return str(value).upper().strip()


def player_position(player):

    pos = raw_position(player)

    # 포수
    if pos in (
        "C",
        "포수",
    ):
        return "C"

    # 내야
    if pos in (
        "1B",
        "1루",
        "1루수",
    ):
        return "1B"

    if pos in (
        "2B",
        "2루",
        "2루수",
    ):
        return "2B"

    if pos in (
        "3B",
        "3루",
        "3루수",
    ):
        return "3B"

    if pos in (
        "SS",
        "유격수",
    ):
        return "SS"

    # 외야
    if pos in (
        "LF",
        "CF",
        "RF",
        "OF",
        "외야",
        "좌익수",
        "중견수",
        "우익수",
    ):
        return "OF"

    # 지명타자
    if pos in (
        "DH",
        "지명타자",
    ):
        return "DH"

    # 투수
    if pos in (
        "SP",
        "선발",
        "선발투수",
    ):
        return "SP"

    if pos in (
        "RP",
        "중계",
        "중계투수",
        "불펜",
    ):
        return "RP"

    if pos in (
        "CP",
        "마무리",
        "마무리투수",
    ):
        return "CP"

    # 투수 세부정보가 있는 경우
    if "P" in pos:

        if "SP" in pos:
            return "SP"

        if "CP" in pos:
            return "CP"

        return "RP"

    return pos


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

    ovr = player_overall(player)

    return max(
        1.0,
        (ovr - 55.0) * 0.30,
    )


# ============================================================
# ROSTER HELPERS
# ============================================================

def roster_counts(roster):

    counts = {
        key: 0
        for key in ROSTER_LIMITS
    }

    for player in roster:

        pos = player_position(
            player
        )

        if pos in counts:

            counts[pos] += 1

    return counts


def roster_total_slots():

    return sum(
        ROSTER_LIMITS.values()
    )


def roster_filled(roster):

    return len(roster)


def roster_complete(roster):

    counts = roster_counts(
        roster
    )

    for pos, limit in ROSTER_LIMITS.items():

        if counts.get(pos, 0) < limit:

            return False

    return True


def can_add_player(
    roster,
    player,
):

    pos = player_position(
        player
    )

    if pos not in ROSTER_LIMITS:

        return False

    counts = roster_counts(
        roster
    )

    return (
        counts.get(pos, 0)
        <
        ROSTER_LIMITS[pos]
    )


def missing_positions(roster):

    counts = roster_counts(
        roster
    )

    missing = {}

    for pos, limit in ROSTER_LIMITS.items():

        remain = (
            limit
            -
            counts.get(pos, 0)
        )

        if remain > 0:

            missing[pos] = remain

    return missing


# ============================================================
# BID LOG
# ============================================================

def add_bid_log(
    state,
    bidder,
    price,
    amount,
):

    if bidder == "user":

        name = "나"

    else:

        name = AI_NAMES.get(
            bidder,
            bidder,
        )

    state.setdefault(
        "bid_log",
        [],
    ).append({

        "bidder":
            bidder,

        "name":
            name,

        "price":
            int(price),

        "amount":
            int(amount),

        "timestamp":
            time.time(),

    })


# ============================================================
# TIMER
# ============================================================

def reset_timer(state):

    state[
        "bid_deadline"
    ] = (
        time.time()
        +
        state.get(
            "bid_timeout",
            BID_TIMEOUT,
        )
    )


def seconds_left(state):

    return max(
        0,
        state.get(
            "bid_deadline",
            0,
        )
        -
        time.time(),
    )


def is_bid_expired(state):

    return (
        seconds_left(state)
        <=
        0
    )


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

    if (
        index < 0
        or
        index >= len(players)
    ):

        return None

    return players[index]


# ============================================================
# AI CAN BID
# ============================================================

def ai_can_bid(
    state,
    ai_key,
    player,
):

    roster = state[
        "ai_rosters"
    ].get(
        ai_key,
        [],
    )

    # 선수 수/포지션 제한
    if not can_add_player(
        roster,
        player,
    ):

        return False

    budget = state[
        "ai_budgets"
    ].get(
        ai_key,
        0,
    )

    if budget <= state.get(
        "price",
        1,
    ):

        return False

    return True


# ============================================================
# CREATE GAME
# ============================================================

def create_game():

    players = load_players()

    valid_players = []

    for player in players:

        pos = player_position(
            player
        )

        if pos in ROSTER_LIMITS:

            valid_players.append(
                deepcopy(player)
            )

    random.shuffle(
        valid_players
    )

    # 실제 경매에서는
    # 필요한 포지션이 충분히 나오도록
    # 우선 포지션별 후보를 확보한다.

    selected = []

    for pos, limit in ROSTER_LIMITS.items():

        candidates = [

            player

            for player in valid_players

            if player_position(
                player
            ) == pos

        ]

        random.shuffle(
            candidates
        )

        # 한 팀이 완성될 수 있는 정도의
        # 후보를 확보
        selected.extend(
            candidates[
                :max(
                    limit + 2,
                    limit * 2,
                )
            ]
        )

    random.shuffle(
        selected
    )

    # 너무 긴 게임 방지
    selected = selected[
        :ROUNDS
    ]

    # 부족한 경우 전체 pool에서 추가
    if len(selected) < ROUNDS:

        used = {
            id(player)
            for player in selected
        }

        for player in valid_players:

            if id(player) in used:
                continue

            selected.append(
                deepcopy(player)
            )

            if len(selected) >= ROUNDS:
                break

    total_rounds = len(
        selected
    )

    current = (
        selected[0]
        if selected
        else None
    )

    return {

        "round":
            1,

        "total_rounds":
            total_rounds,

        "player_index":
            0,

        "players":
            selected,

        "current":
            current,

        # USER
        "budget":
            INITIAL_BUDGET,

        "roster":
            [],

        # AI
        "ai_budgets": {

            key:
                INITIAL_BUDGET

            for key in AI_NAMES
        },

        "ai_rosters": {

            key: []

            for key in AI_NAMES
        },

        "ai_names":
            AI_NAMES,

        # AUCTION
        "price":
            1,

        "leader":
            None,

        "bid_log":
            [],

        "bid_timeout":
            BID_TIMEOUT,

        "bid_deadline":
            time.time()
            +
            BID_TIMEOUT,

        # HISTORY
        "history":
            [],

        # GAME
        "message":
            "경매 시작!",

        "finished":
            False,

        "result":
            None,
    }


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

    value = player_value(
        player
    )

    ovr = player_overall(
        player
    )

    missing = missing_positions(
        state[
            "ai_rosters"
        ][ai_key]
    )

    pos = player_position(
        player
    )

    # 부족한 포지션이면 가치 상승
    positional_need = 1.0

    if pos in missing:

        positional_need += (
            0.18
            *
            min(
                2,
                missing[pos],
            )
        )

    # 선수가 매우 좋은 경우
    star_multiplier = (
        1.0
        +
        max(
            0,
            ovr - 75,
        )
        / 100
        *
        profile[
            "star_bias"
        ]
    )

    target = (
        value
        *
        profile[
            "aggression"
        ]
        *
        star_multiplier
        *
        positional_need
    )

    # 후반부에는 부족한 포지션에 돈을 집중
    if state["round"] >= 16:

        if pos in missing:

            target *= 1.20

        else:

            target *= 0.82

    # 승부사는 후반에도 적극적
    if (
        ai_key == "gambler"
        and
        pos in missing
    ):

        target *= 1.15

    # 데이터파는 과소비 억제
    if ai_key == "data":

        target *= 0.90

    target *= random.uniform(
        1.0 - profile[
            "randomness"
        ],
        1.0 + profile[
            "randomness"
        ],
    )

    reserve = max(
        5,
        budget * 0.08,
    )

    usable = max(
        0,
        budget - reserve,
    )

    return max(
        0,
        int(
            math.floor(
                min(
                    target,
                    usable,
                )
            )
        ),
    )


# ============================================================
# AI SHOULD BID
# ============================================================

def ai_should_bid(
    ai_key,
    player,
    state,
):

    if not ai_can_bid(
        state,
        ai_key,
        player,
    ):

        return False

    current = state[
        "price"
    ]

    maximum = ai_max_bid(
        ai_key,
        player,
        state,
    )

    if maximum <= current:
        return False

    profile = AI_PROFILES[
        ai_key
    ]

    # 현재 가격이 한계에 가까워질수록
    # 입찰 확률 감소
    ratio = (
        current
        /
        max(
            1,
            maximum,
        )
    )

    chance = profile[
        "aggression"
    ]

    chance -= (
        ratio
        *
        0.20
    )

    # 승부사는 공격적
    if ai_key == "gambler":

        chance += 0.16

    # 포지션이 급하면 상승
    pos = player_position(
        player
    )

    missing = missing_positions(
        state[
            "ai_rosters"
        ][ai_key]
    )

    if pos in missing:

        chance += 0.10

    chance = max(
        0.05,
        min(
            0.98,
            chance,
        ),
    )

    return random.random() < chance


# ============================================================
# AI ACTION
# ============================================================

def choose_ai_amount(
    ai_key,
    possible,
):

    if not possible:
        return None

    # 승부사
    if ai_key == "gambler":

        roll = random.random()

        if (
            5 in possible
            and roll < 0.35
        ):

            return 5

        if (
            3 in possible
            and roll < 0.80
        ):

            return 3

        return 1 if 1 in possible else max(
            possible
        )

    # 베테랑
    if ai_key == "veteran":

        if (
            3 in possible
            and random.random() < 0.28
        ):

            return 3

        return 1 if 1 in possible else max(
            possible
        )

    # 데이터파
    if (
        3 in possible
        and random.random() < 0.12
    ):

        return 3

    return 1 if 1 in possible else max(
        possible
    )


def ai_response(state):

    player = get_current_player(
        state
    )

    if not player:
        return None

    candidates = []

    for ai_key in AI_NAMES:

        if not ai_should_bid(
            ai_key,
            player,
            state,
        ):
            continue

        maximum = ai_max_bid(
            ai_key,
            player,
            state,
        )

        priority = (
            AI_PROFILES[
                ai_key
            ][
                "aggression"
            ]
        )

        # 승부사 우선권
        if ai_key == "gambler":

            priority += 0.12

        # 필요한 포지션이면 우선
        pos = player_position(
            player
        )

        missing = missing_positions(
            state[
                "ai_rosters"
            ][ai_key]
        )

        if pos in missing:

            priority += 0.15

        priority *= random.uniform(
            0.90,
            1.10,
        )

        candidates.append({

            "key":
                ai_key,

            "maximum":
                maximum,

            "priority":
                priority,

        })

    if not candidates:

        return None

    candidates.sort(
        key=lambda x:
            x["priority"],
        reverse=True,
    )

    # 이번 턴에는 한 명만 입찰
    # 다음 요청에서 다시 경쟁
    selected = candidates[0]

    ai_key = selected[
        "key"
    ]

    maximum = selected[
        "maximum"
    ]

    possible = [

        amount

        for amount in BID_AMOUNTS

        if (

            state["price"]
            +
            amount
            <= maximum

            and

            state["price"]
            +
            amount
            <=
            state[
                "ai_budgets"
            ][ai_key]

        )

    ]

    amount = choose_ai_amount(
        ai_key,
        possible,
    )

    if amount is None:
        return None

    new_price = (
        state["price"]
        +
        amount
    )

    state["price"] = new_price

    state["leader"] = ai_key

    add_bid_log(
        state,
        ai_key,
        new_price,
        amount,
    )

    reset_timer(
        state
    )

    state["message"] = (

        f"🤖 "
        f"{AI_NAMES[ai_key]} "
        f"+{amount}P → "
        f"{new_price}P"

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

        finish_game(
            state
        )

        return state

    # 포지션 슬롯
    if not can_add_player(
        state["roster"],
        player,
    ):

        state["message"] = (

            f"내 팀의 "
            f"{player_position(player)} "
            f"자리가 이미 찼습니다."

        )

        return state

    try:

        amount = int(
            amount
        )

    except (
        ValueError,
        TypeError,
    ):

        state["message"] = (
            "잘못된 입찰입니다."
        )

        return state

    if amount not in BID_AMOUNTS:

        state["message"] = (
            "입찰 금액 오류"
        )

        return state

    new_price = (
        state["price"]
        +
        amount
    )

    if new_price > state[
        "budget"
    ]:

        state["message"] = (
            "예산이 부족합니다."
        )

        return state

    state["price"] = new_price

    state["leader"] = "user"

    add_bid_log(
        state,
        "user",
        new_price,
        amount,
    )

    reset_timer(
        state
    )

    state["message"] = (

        f"👤 나 +{amount}P → "
        f"{new_price}P"

    )

    # AI 반응
    ai_response(
        state
    )

    return state


# ============================================================
# USER SOLD
# ============================================================

def user_sold(state):

    if state.get("finished"):
        return state

    if state.get(
        "leader"
    ) != "user":

        state["message"] = (
            "현재 최고 입찰자가 아닙니다."
        )

        return state

    settle_current_auction(
        state
    )

    return state


# ============================================================
# PASS
# ============================================================

def user_pass(state):

    if state.get("finished"):
        return state

    # 내가 최고가인데 PASS
    if state.get(
        "leader"
    ) == "user":

        state["message"] = (
            "입찰을 포기했습니다."
        )

        # 현재 최고가를 AI가 가져갈 수 있도록
        settle_after_pass(
            state
        )

        return state

    # AI가 최고가라면
    # 내가 빠지고 바로 낙찰
    if state.get(
        "leader"
    ) not in (
        None,
        "user",
    ):

        settle_current_auction(
            state
        )

        return state

    # 아무도 입찰하지 않았다면
    ai = ai_response(
        state
    )

    if ai:
        return state

    next_round(
        state
    )

    return state


# ============================================================
# PASS SETTLEMENT
# ============================================================

def settle_after_pass(state):

    player = get_current_player(
        state
    )

    if not player:

        next_round(
            state
        )

        return

    # 현재 최고 AI가 있으면 낙찰
    leader = state.get(
        "leader"
    )

    if leader in AI_NAMES:

        settle_current_auction(
            state
        )

        return

    # 새로운 AI에게 기회
    ai = ai_response(
        state
    )

    if ai:

        return

    next_round(
        state
    )


# ============================================================
# AWARD
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
        return False

    player_copy = deepcopy(
        player
    )

    player_copy[
        "cost"
    ] = int(price)

    player_copy[
        "auction_price"
    ] = int(price)

    pos = player_position(
        player
    )

    if winner == "user":

        if not can_add_player(
            state["roster"],
            player,
        ):

            return False

        state[
            "budget"
        ] -= price

        state[
            "roster"
        ].append(
            player_copy
        )

        winner_name = "나"

    else:

        roster = state[
            "ai_rosters"
        ][winner]

        if not can_add_player(
            roster,
            player,
        ):

            return False

        state[
            "ai_budgets"
        ][winner] -= price

        roster.append(
            player_copy
        )

        winner_name = AI_NAMES[
            winner
        ]

    state[
        "history"
    ].append({

        "round":
            state["round"],

        "player":
            player_name(player),

        "position":
            pos,

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

    })

    state["message"] = (

        f"🔨 {winner_name} "
        f"→ {player_name(player)} "
        f"({pos}) "
        f"{price}P 낙찰!"

    )

    return True


# ============================================================
# SETTLE
# ============================================================

def settle_current_auction(state):

    player = get_current_player(
        state
    )

    if not player:

        finish_game(
            state
        )

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

    if winner is None:

        next_round(
            state
        )

        return

    success = award_player(
        state,
        winner,
        price,
    )

    if not success:

        # 잘못된 낙찰이면 유찰
        state["message"] = (
            "해당 포지션을 채울 수 없어 유찰되었습니다."
        )

    next_round(
        state
    )


# ============================================================
# NEXT ROUND
# ============================================================

def next_round(state):

    # 현재 선수 기록 초기화
    state[
        "player_index"
    ] += 1

    state[
        "round"
    ] += 1

    state[
        "price"
    ] = 1

    state[
        "leader"
    ] = None

    state[
        "bid_log"
    ] = []

    # ========================================================
    # 팀 완성
    # ========================================================

    if roster_complete(
        state["roster"]
    ):

        finish_game(
            state
        )

        return

    # ========================================================
    # 모든 AI가 완성된 경우도 체크
    # ========================================================

    all_done = True

    for ai_key in AI_NAMES:

        if not roster_complete(
            state[
                "ai_rosters"
            ][ai_key]
        ):

            all_done = False

            break

    if all_done:

        finish_game(
            state
        )

        return

    # ========================================================
    # 선수 소진
    # ========================================================

    if (
        state["player_index"]
        >=
        state["total_rounds"]
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

        f"ROUND "
        f"{state['round']} "
        f"— "
        f"{player_name(player)} "
        f"등장!"

    )


# ============================================================
# USER ACTION
# ============================================================

def user_action(
    state,
    action,
):

    if state.get("finished"):
        return state

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    if action == "timeout":

        if not is_bid_expired(
            state
        ):

            return state

        # 최고가가 있으면 자동 낙찰
        if state.get(
            "leader"
        ):

            settle_current_auction(
                state
            )

            return state

        # 아무도 안 샀으면 AI에게 기회
        ai = ai_response(
            state
        )

        if ai:

            return state

        next_round(
            state
        )

        return state

    # --------------------------------------------------------
    # USER BID
    # --------------------------------------------------------

    if action in (
        "1",
        "3",
        "5",
    ):

        return user_bid(
            state,
            int(action),
        )

    # --------------------------------------------------------
    # SOLD
    # --------------------------------------------------------

    if action == "sold":

        return user_sold(
            state
        )

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if action == "pass":

        return user_pass(
            state
        )

    state["message"] = (
        "알 수 없는 행동입니다."
    )

    return state


# ============================================================
# SCORE
# ============================================================

def roster_score(
    roster,
):

    if not roster:
        return 0.0

    total_ovr = sum(
        player_overall(player)
        for player in roster
    )

    average = (
        total_ovr
        /
        len(roster)
    )

    # 팀 완성도
    counts = roster_counts(
        roster
    )

    completed_slots = 0

    total_slots = (
        roster_total_slots()
    )

    for pos, limit in ROSTER_LIMITS.items():

        completed_slots += min(
            counts.get(pos, 0),
            limit,
        )

    completion = (
        completed_slots
        /
        total_slots
    )

    completion_bonus = (
        completion
        *
        25
    )

    # 가성비
    spent = sum(
        float(
            player.get(
                "cost",
                1,
            )
        )
        for player in roster
    )

    efficiency = (
        total_ovr
        /
        max(
            1,
            spent,
        )
    )

    efficiency_bonus = min(
        efficiency * 3,
        15,
    )

    return round(
        average
        +
        completion_bonus
        +
        efficiency_bonus,
        2,
    )


# ============================================================
# BEST BARGAIN
# ============================================================

def find_best_signing(
    roster,
):

    if not roster:
        return None

    best = None

    best_value = -999999

    for player in roster:

        value = (
            player_overall(player)
            /
            max(
                1,
                float(
                    player.get(
                        "cost",
                        1,
                    )
                ),
            )
        )

        if value > best_value:

            best_value = value

            best = deepcopy(
                player
            )

            best[
                "value"
            ] = round(
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

    if rank == 1:

        if len(results) > 1:

            gap = (
                score
                -
                results[1]["score"]
            )

        else:

            gap = 999

        if (
            gap >= 12
            and score >= 100
        ):

            return "S+"

        return "S"

    if rank == 2:

        if score >= 95:
            return "A+"

        return "A"

    if rank == 3:

        if score >= 90:
            return "B+"

        return "B"

    if score >= 85:
        return "B"

    if score >= 75:
        return "C"

    return "D"


# ============================================================
# FINISH
# ============================================================

def finish_game(state):

    if state.get("finished"):
        return state

    results = []

    # USER
    user_roster = state.get(
        "roster",
        [],
    )

    user_budget = state.get(
        "budget",
        INITIAL_BUDGET,
    )

    results.append({

        "key":
            "user",

        "name":
            "나",

        "score":
            roster_score(
                user_roster
            ),

        "roster":
            deepcopy(
                user_roster
            ),

        "is_user":
            True,

        "spent":
            INITIAL_BUDGET
            -
            user_budget,

        "remaining":
            user_budget,

        "complete":
            roster_complete(
                user_roster
            ),

    })

    # AI
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

            "key":
                ai_key,

            "name":
                ai_name,

            "score":
                roster_score(
                    roster
                ),

            "roster":
                deepcopy(
                    roster
                ),

            "is_user":
                False,

            "spent":
                INITIAL_BUDGET
                -
                budget,

            "remaining":
                budget,

            "complete":
                roster_complete(
                    roster
                ),

        })

    # 순위
    results.sort(
        key=lambda x:
            x["score"],
        reverse=True,
    )

    for index, result in enumerate(
        results,
        start=1,
    ):

        result[
            "rank"
        ] = index

    # 등급
    for result in results:

        result[
            "grade"
        ] = calculate_grade(
            result["rank"],
            result["score"],
            results,
        )

    user = next(
        x
        for x in results
        if x["is_user"]
    )

    # 1등과의 차이
    if user["rank"] == 1:

        margin = (
            user["score"]
            -
            results[1]["score"]
            if len(results) > 1
            else 0
        )

    else:

        margin = (
            user["score"]
            -
            results[0]["score"]
        )

    user[
        "win_margin"
    ] = round(
        margin,
        2,
    )

    user[
        "efficiency"
    ] = round(
        user["score"]
        /
        max(
            1,
            user["spent"],
        ),
        2,
    )

    state[
        "result"
    ] = {

        "user":
            user,

        "results":
            results,

        "best_bargain":
            find_best_signing(
                user["roster"]
            ),

        "history":
            deepcopy(
                state.get(
                    "history",
                    [],
                )
            ),

        "roster_limits":
            ROSTER_LIMITS,

    }

    state[
        "finished"
    ] = True

    state[
        "message"
    ] = (
        "🏆 팀 완성! "
        "경매 시즌 종료!"
    )

    return state
