# auction.py

import json
import random
import math
from copy import deepcopy


# ============================================================
# 기본 설정
# ============================================================

INITIAL_BUDGET = 100
ROUNDS = 12


AI_NAMES = {
    "veteran": "베테랑",
    "data": "데이터파",
    "gambler": "승부사",
}


# ============================================================
# 선수 풀
# ============================================================

def load_players():

    paths = [
        "player_pool.json",
        "data/player_pool.json",
    ]

    data = None

    for path in paths:

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                break

        except FileNotFoundError:
            continue

    if data is None:
        raise FileNotFoundError(
            "player_pool.json을 찾을 수 없습니다."
        )

    # 배열 자체인 경우
    if isinstance(data, list):
        return data

    # {"players": [...]}
    if isinstance(data, dict):

        for key in (
            "players",
            "player_pool",
            "data",
            "pool"
        ):

            value = data.get(key)

            if isinstance(value, list):
                return value

    raise ValueError(
        "player_pool.json의 선수 데이터 형식을 확인해주세요."
    )


# ============================================================
# 선수 정보
# ============================================================

def player_name(player):

    return str(
        player.get(
            "name",
            player.get(
                "player_name",
                player.get(
                    "NAME",
                    "이름없음"
                )
            )
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
                    "UTIL"
                )
            )
        )
    )


def player_overall(player):

    keys = [
        "overall",
        "ovr",
        "rating",
        "OVR",
        "Overall",
    ]

    for key in keys:

        value = player.get(key)

        if value is None:
            continue

        try:
            return float(value)
        except:
            pass

    return 70.0


def player_value(player):

    """
    선수의 원시 가치.

    OVR만 있는 player_pool도 작동하도록 설계.
    """

    ovr = player_overall(player)

    # OVR 70 → 약 4
    # OVR 80 → 약 7
    # OVR 90 → 약 11
    return max(
        1.0,
        (ovr - 55.0) * 0.30
    )


# ============================================================
# AI
# ============================================================

AI_PROFILES = {

    "veteran": {
        "risk": 0.70,
        "aggression": 0.75,
        "star_bias": 1.05,
        "randomness": 0.10,
    },

    "data": {
        "risk": 0.45,
        "aggression": 0.58,
        "star_bias": 0.95,
        "randomness": 0.05,
    },

    "gambler": {
        "risk": 0.95,
        "aggression": 1.00,
        "star_bias": 1.15,
        "randomness": 0.30,
    },
}


# ============================================================
# 게임 상태
# ============================================================

def create_game():

    players = load_players()

    random.shuffle(players)

    # 라운드 수보다 선수가 적으면 반복하지 않고
    # 풀 전체를 사용
    if len(players) < ROUNDS:

        rounds = len(players)

    else:

        rounds = ROUNDS

    return {

        "round": 1,

        "total_rounds": rounds,

        "budget": INITIAL_BUDGET,

        "roster": [],

        "ai_budgets": {
            key: INITIAL_BUDGET
            for key in AI_NAMES
        },

        "ai_rosters": {
            key: []
            for key in AI_NAMES
        },

        "players": players,

        "current": players[0] if players else {},

        "price": 1,

        "leader": None,

        "passed": False,

        "message": "경매가 시작되었습니다.",

        "finished": False,

        "result": None,

        "history": [],

        "player_index": 0,

    }


# ============================================================
# 현재 선수
# ============================================================

def get_current_player(state):

    players = state.get("players", [])

    index = state.get(
        "player_index",
        0
    )

    if not players:
        return None

    if index >= len(players):
        return None

    return players[index]


# ============================================================
# AI가 원하는 가격
# ============================================================

def ai_max_bid(
    ai_key,
    player,
    state
):

    profile = AI_PROFILES[ai_key]

    budget = state[
        "ai_budgets"
    ][ai_key]

    ovr = player_overall(player)

    base = player_value(player)

    # 남은 라운드
    remaining_rounds = max(
        1,
        state["total_rounds"]
        - state["round"]
        + 1
    )

    # 예산을 전부 한 선수에게 쓰지 않도록
    reserve = max(
        5,
        budget * 0.08
    )

    usable_budget = max(
        0,
        budget - reserve
    )

    # 좋은 선수일수록 적극적
    star_multiplier = (
        1
        + (
            max(
                0,
                ovr - 75
            ) / 100
            * profile["star_bias"]
        )
    )

    target = (
        base
        * profile["aggression"]
        * star_multiplier
    )

    # 예산 상황에 따른 보정
    if remaining_rounds <= 3:
        target *= 1.15

    elif remaining_rounds >= 9:
        target *= 0.90

    # 성향 랜덤
    random_factor = random.uniform(
        1.0 - profile["randomness"],
        1.0 + profile["randomness"]
    )

    target *= random_factor

    target = min(
        target,
        usable_budget
    )

    return max(
        0,
        int(
            math.floor(target)
        )
    )


# ============================================================
# AI 입찰 판단
# ============================================================

def ai_should_bid(
    ai_key,
    player,
    current_price,
    state
):

    budget = state[
        "ai_budgets"
    ][ai_key]

    if budget <= current_price:
        return False

    maximum = ai_max_bid(
        ai_key,
        player,
        state
    )

    return current_price < maximum


# ============================================================
# AI 경쟁
# ============================================================

def run_ai_competition(
    state
):

    player = get_current_player(state)

    if not player:
        return None

    current_price = state.get(
        "price",
        1
    )

    leader = state.get(
        "leader"
    )

    competitors = []

    for ai_key in AI_NAMES:

        if not ai_should_bid(
            ai_key,
            player,
            current_price,
            state
        ):
            continue

        maximum = ai_max_bid(
            ai_key,
            player,
            state
        )

        competitors.append(
            (
                ai_key,
                maximum
            )
        )

    if not competitors:
        return None

    # 최대 지불 의향이 높은 AI부터
    competitors.sort(
        key=lambda x: x[1],
        reverse=True
    )

    winner = competitors[0]

    ai_key = winner[0]

    maximum = winner[1]

    # 현재 가격에서 한 단계 올림
    new_price = min(
        maximum,
        current_price + 1
    )

    if new_price <= current_price:
        return None

    state["price"] = new_price

    state["leader"] = ai_key

    return ai_key


# ============================================================
# 선수 낙찰
# ============================================================

def award_player(
    state,
    winner,
    price
):

    player = deepcopy(
        get_current_player(state)
    )

    if not player:
        return

    player["cost"] = price

    player["auction_price"] = price

    # USER
    if winner == "user":

        state["budget"] -= price

        state["roster"].append(
            player
        )

        winner_name = "나"

    # AI
    else:

        state[
            "ai_budgets"
        ][winner] -= price

        state[
            "ai_rosters"
        ][winner].append(
            player
        )

        winner_name = AI_NAMES.get(
            winner,
            winner
        )

    # 히스토리
    state["history"].append({

        "round": state["round"],

        "player": player_name(player),

        "position": player_position(player),

        "overall": player_overall(player),

        "price": price,

        "winner": winner,

        "winner_name": winner_name,

    })

    state["message"] = (
        f"{winner_name}이(가) "
        f"{player_name(player)}을(를) "
        f"{price}P에 영입했습니다."
    )


# ============================================================
# 다음 라운드
# ============================================================

def next_round(state):

    state["player_index"] += 1

    state["round"] += 1

    state["leader"] = None

    state["price"] = 1

    if (
        state["round"]
        > state["total_rounds"]
    ):

        finish_game(state)

        return

    player = get_current_player(
        state
    )

    if not player:

        finish_game(state)

        return

    state["current"] = player

    state["message"] = (
        f"다음 선수 "
        f"{player_name(player)} "
        f"등장!"
    )


# ============================================================
# USER 액션
# ============================================================

def user_action(
    state,
    action
):

    if state.get("finished"):
        return state

    player = get_current_player(
        state
    )

    if not player:
        finish_game(state)
        return state

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if action == "pass":

        # 유저가 빠지면 AI끼리 경쟁
        ai_winner = run_ai_competition(
            state
        )

        if ai_winner:

            # AI가 가격을 올렸으므로
            # 추가 AI 경쟁
            for _ in range(8):

                next_ai = run_ai_competition(
                    state
                )

                if next_ai is None:
                    break

            winner = state.get(
                "leader"
            )

            if winner:

                award_player(
                    state,
                    winner,
                    state["price"]
                )

        else:

            state["message"] = (
                "모든 단장이 패스했습니다."
            )

        next_round(state)

        return state

    # --------------------------------------------------------
    # BID
    # --------------------------------------------------------

    try:
        amount = int(action)

    except:
        amount = 1

    amount = max(
        1,
        min(
            amount,
            10
        )
    )

    new_price = (
        state.get(
            "price",
            1
        )
        + amount
    )

    # 예산 검사
    if new_price > state["budget"]:

        state["message"] = (
            "포인트가 부족합니다."
        )

        return state

    state["price"] = new_price

    state["leader"] = "user"

    state["message"] = (
        f"나 → "
        f"{new_price}P 입찰"
    )

    # --------------------------------------------------------
    # AI 응답
    # --------------------------------------------------------

    ai_actions = []

    for _ in range(3):

        ai_key = run_ai_competition(
            state
        )

        if ai_key is None:
            break

        ai_actions.append(
            ai_key
        )

        # AI가 가격을 올렸다면
        # 다른 AI가 다시 대응
        if state["leader"] != "user":

            continue

    # --------------------------------------------------------
    # AI가 경쟁을 안 하면
    # 현재 유저가 최고가
    # --------------------------------------------------------

    if state["leader"] == "user":

        state["message"] = (
            f"현재 최고 입찰자: 나 "
            f"({state['price']}P)"
        )

        return state

    # --------------------------------------------------------
    # AI가 최고가라면
    # 유저에게 다시 선택권
    # --------------------------------------------------------

    leader = state.get(
        "leader"
    )

    if leader:

        state["message"] = (
            f"{AI_NAMES.get(leader, leader)}이(가) "
            f"{state['price']}P로 "
            f"앞섰습니다!"
        )

    return state


# ============================================================
# 경매 종료 판정
# ============================================================

def settle_current_auction(
    state
):

    player = get_current_player(
        state
    )

    if not player:
        return

    leader = state.get(
        "leader"
    )

    price = state.get(
        "price",
        1
    )

    # 아무도 입찰하지 않았으면
    # 랜덤 AI가 아주 낮은 가격으로 영입
    if not leader:

        available = [
            key
            for key in AI_NAMES
            if state["ai_budgets"][key] >= 1
        ]

        if available:

            leader = random.choice(
                available
            )

            price = 1

        elif state["budget"] >= 1:

            leader = "user"

            price = 1

        else:

            next_round(state)

            return

    # --------------------------------------------------------
    # 최종 낙찰
    # --------------------------------------------------------

    if leader == "user":

        if price <= state["budget"]:

            award_player(
                state,
                "user",
                price
            )

        else:

            # 돈 부족 시 AI에게 넘김
            ai_winner = run_ai_competition(
                state
            )

            if ai_winner:

                award_player(
                    state,
                    ai_winner,
                    state["price"]
                )

    else:

        if price <= state[
            "ai_budgets"
        ][leader]:

            award_player(
                state,
                leader,
                price
            )

    next_round(state)


# ============================================================
# 점수 계산
# ============================================================

def roster_score(
    roster
):

    if not roster:
        return 0.0

    total_ovr = sum(
        player_overall(p)
        for p in roster
    )

    total_cost = sum(
        float(
            p.get(
                "cost",
                1
            )
        )
        for p in roster
    )

    count = len(roster)

    average_ovr = (
        total_ovr / count
    )

    # 선수 수 보너스
    roster_bonus = min(
        count * 1.5,
        12
    )

    # 좋은 선수 확보
    quality_bonus = max(
        0,
        average_ovr - 70
    ) * 0.45

    # 효율
    efficiency = (
        total_ovr
        /
        max(
            1,
            total_cost
        )
    )

    efficiency_bonus = min(
        efficiency * 3,
        15
    )

    return round(
        average_ovr
        + roster_bonus
        + quality_bonus
        + efficiency_bonus,
        2
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
                1
            )
        )

        # 비싸게 산 선수보다
        # 싸게 좋은 선수를 산 경우 높게
        value = (
            ovr
            /
            max(
                1,
                cost
            )
        )

        if value > best_value:

            best_value = value

            best = deepcopy(
                player
            )

            best["value"] = round(
                value,
                2
            )

    return best


# ============================================================
# 등급
# ============================================================

def calculate_grade(
    rank,
    score,
    results
):

    if not results:
        return "D"

    top_score = float(
        results[0]["score"]
    )

    second_score = (
        float(results[1]["score"])
        if len(results) >= 2
        else top_score
    )

    # 압도적 우승
    if (
        rank == 1
        and score >= 105
        and (
            score - second_score
        ) >= 10
    ):
        return "S+"

    # 우승
    if rank == 1:
        return "S"

    if rank == 2:
        return "B"

    if rank == 3:
        return "C"

    return "D"


# ============================================================
# 최종 결과
# ============================================================

def finish_game(
    state
):

    if state.get("finished"):
        return state

    players = []

    # USER
    players.append({

        "key": "user",

        "name": "나",

        "score": roster_score(
            state.get(
                "roster",
                []
            )
        ),

        "roster": state.get(
            "roster",
            []
        ),

        "is_user": True,

        "spent": (
            INITIAL_BUDGET
            - state.get(
                "budget",
                INITIAL_BUDGET
            )
        ),

        "remaining":
            state.get(
                "budget",
                0
            ),

    })

    # AI
    for ai_key, ai_name in AI_NAMES.items():

        roster = state[
            "ai_rosters"
        ].get(
            ai_key,
            []
        )

        budget = state[
            "ai_budgets"
        ].get(
            ai_key,
            INITIAL_BUDGET
        )

        players.append({

            "key": ai_key,

            "name": ai_name,

            "score": roster_score(
                roster
            ),

            "roster": roster,

            "is_user": False,

            "spent": (
                INITIAL_BUDGET
                - budget
            ),

            "remaining": budget,

        })

    # 점수순
    players.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # 순위
    for index, row in enumerate(
        players,
        start=1
    ):

        row["rank"] = index

    # 등급
    for row in players:

        row["grade"] = calculate_grade(
            row["rank"],
            row["score"],
            players
        )

    # USER
    user = next(
        row
        for row in players
        if row["is_user"]
    )

    # 2위와의 차이
    if user["rank"] == 1:

        if len(players) > 1:

            win_margin = (
                user["score"]
                - players[1]["score"]
            )

        else:

            win_margin = 0

    else:

        win_margin = (
            user["score"]
            - players[0]["score"]
        )

    # 효율
    user["efficiency"] = round(
        user["score"]
        /
        max(
            1,
            user["spent"]
        ),
        2
    )

    user["win_margin"] = round(
        win_margin,
        2
    )

    best = find_best_signing(
        user["roster"]
    )

    result = {

        "user": user,

        "results": players,

        "best_bargain": best,

        "history":
            deepcopy(
                state.get(
                    "history",
                    []
                )
            ),

    }

    state["result"] = result

    state["finished"] = True

    state["message"] = (
        "경매 시즌이 종료되었습니다."
    )

    return state
