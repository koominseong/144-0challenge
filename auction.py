# auction.py
# Auction V2 - 4 GM 경쟁 로직

from __future__ import annotations

import copy
import random
from typing import Any


START_BUDGET = 100
TOTAL_ROUNDS = 12

AI_NAMES = {
    "veteran": "🦉 베테랑",
    "data": "📊 데이터파",
    "gambler": "🎲 승부사",
}


# ============================================================
# 기본 유틸
# ============================================================

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def player_name(player):
    return str(
        player.get("name")
        or player.get("player_name")
        or "이름 없음"
    )


def player_position(player):
    return str(
        player.get("position")
        or player.get("pos")
        or player.get("position_name")
        or "UTIL"
    )


def player_overall(player):
    """
    player_pool.json의 필드명이 조금 달라도
    최대한 호환되도록 처리.
    """
    for key in (
        "overall",
        "ovr",
        "rating",
        "score",
        "ability",
    ):
        if player.get(key) is not None:
            return _num(player.get(key))

    return 70.0


def normalize_player(player):
    p = copy.deepcopy(player)

    p["name"] = player_name(p)
    p["position"] = player_position(p)
    p["overall"] = player_overall(p)

    return p


# ============================================================
# 선수 가치
# ============================================================

def market_value(player):
    """
    게임 내부 포인트 기준 예상 선수 가치.
    실제 화폐가 아님.
    """

    ovr = player_overall(player)

    # OVR 70 = 3
    # OVR 80 = 7
    # OVR 90 = 18 정도
    value = 3 + max(0, ovr - 70) * 0.65

    # 약간의 시장 변동
    return round(max(2, value), 1)


def value_ratio(player, cost):
    value = market_value(player)

    if cost <= 0:
        return value

    return value / cost


# ============================================================
# 포지션
# ============================================================

def position_group(position):
    p = str(position).upper()

    if p in {"SP", "선발", "STARTER"}:
        return "SP"

    if p in {"RP", "CP", "불펜", "RELIEF", "CLOSER"}:
        return "RP"

    if p in {"C", "포수"}:
        return "C"

    if p in {"1B", "2B", "3B", "SS", "내야"}:
        return "IF"

    if p in {"LF", "CF", "RF", "OF", "외야"}:
        return "OF"

    return "UTIL"


def roster_needs(roster):
    counts = {
        "SP": 0,
        "RP": 0,
        "C": 0,
        "IF": 0,
        "OF": 0,
    }

    for p in roster:
        group = position_group(player_position(p))

        if group in counts:
            counts[group] += 1

    return counts


def positional_need(roster, player):
    """
    현재 선수단에서 해당 포지션이 얼마나 필요한지.
    """

    needs = roster_needs(roster)
    group = position_group(player_position(player))

    targets = {
        "SP": 3,
        "RP": 2,
        "C": 1,
        "IF": 3,
        "OF": 3,
    }

    target = targets.get(group, 1)
    current = needs.get(group, 0)

    if current >= target:
        return 0.15

    missing = target - current

    return min(1.0, 0.45 + missing * 0.2)


# ============================================================
# AI 성향
# ============================================================

def ai_max_value(ai_key, player, state):
    """
    AI가 해당 선수에게 사용할 의향이 있는
    최대 포인트.
    """

    roster = state["ai_rosters"][ai_key]
    budget = state["ai_budgets"][ai_key]

    ovr = player_overall(player)
    market = market_value(player)
    need = positional_need(roster, player)

    # --------------------------------------------------------
    # 베테랑
    # --------------------------------------------------------

    if ai_key == "veteran":

        # 스타 선수 선호
        premium = 1.0

        if ovr >= 90:
            premium = 1.65
        elif ovr >= 85:
            premium = 1.35
        elif ovr >= 80:
            premium = 1.1

        maximum = market * premium

        # 포지션이 부족하면 추가 투자
        maximum *= 0.75 + need * 0.45

        # 예산이 많이 남아 있으면 공격적
        if budget >= 70:
            maximum *= 1.12

        return min(
            budget,
            max(1, int(round(maximum)))
        )

    # --------------------------------------------------------
    # 데이터파
    # --------------------------------------------------------

    if ai_key == "data":

        # 가성비가 핵심
        maximum = market

        if ovr >= 90:
            maximum *= 1.05

        maximum *= 0.7 + need * 0.55

        # 매우 비싼 선수에는 냉정
        return min(
            budget,
            max(1, int(round(maximum)))
        )

    # --------------------------------------------------------
    # 승부사
    # --------------------------------------------------------

    if ai_key == "gambler":

        # 랜덤한 공격성
        aggression = random.uniform(
            0.75,
            1.55
        )

        if ovr >= 90:
            aggression += 0.35

        maximum = market * aggression

        maximum *= 0.8 + need * 0.35

        return min(
            budget,
            max(1, int(round(maximum)))
        )

    return min(
        budget,
        max(1, int(round(market)))
    )


# ============================================================
# AI 입찰 판단
# ============================================================

def ai_wants_player(
    ai_key,
    player,
    current_price,
    state,
):
    budget = state["ai_budgets"][ai_key]

    if budget <= current_price:
        return False

    maximum = ai_max_value(
        ai_key,
        player,
        state,
    )

    # 현재 가격이 최대 지불 의향보다 높으면 포기
    if current_price >= maximum:
        return False

    # AI별 행동 특성
    if ai_key == "veteran":
        probability = 0.82

    elif ai_key == "data":
        probability = 0.62

    else:
        probability = 0.70

    # 좋은 선수일수록 경쟁
    if player_overall(player) >= 90:
        probability += 0.12

    # 필요한 포지션
    if positional_need(
        state["ai_rosters"][ai_key],
        player,
    ) >= 0.8:
        probability += 0.08

    return random.random() < min(
        probability,
        0.95,
    )


# ============================================================
# AI 경쟁 처리
# ============================================================

def run_ai_competition(
    player,
    current_price,
    state,
):
    """
    사용자의 입찰 이후 AI들이 경쟁.
    한 번의 action에서 너무 길게 루프하지 않도록
    최대 몇 단계까지만 진행.
    """

    price = current_price
    leader = "user"

    max_cycles = 8

    for _ in range(max_cycles):

        candidates = []

        for ai_key in AI_NAMES:

            if state["ai_budgets"][ai_key] <= price:
                continue

            if ai_wants_player(
                ai_key,
                player,
                price,
                state,
            ):
                candidates.append(ai_key)

        if not candidates:
            break

        # 여러 AI가 경쟁하면 가장 적극적인 AI를 우선
        scored = []

        for ai_key in candidates:

            max_value = ai_max_value(
                ai_key,
                player,
                state,
            )

            score = (
                max_value
                + random.uniform(0, 2.5)
            )

            scored.append(
                (score, ai_key)
            )

        scored.sort(
            reverse=True
        )

        _, winner = scored[0]

        next_price = price + 1

        if state["ai_budgets"][winner] < next_price:
            break

        price = next_price
        leader = winner

        # AI가 입찰했지만 다른 AI가 다시 경쟁하도록
        # 한 사이클 진행

        # 지나치게 길어지지 않도록
        if price >= ai_max_value(
            winner,
            player,
            state,
        ):
            break

    return {
        "price": price,
        "leader": leader,
    }


# ============================================================
# 선수 영입
# ============================================================

def acquire_player(
    owner,
    player,
    price,
    state,
):
    player = normalize_player(player)

    if owner == "user":

        if state["budget"] < price:
            return False

        state["budget"] -= price
        state["roster"].append(
            {
                **player,
                "cost": price,
            }
        )

        return True

    if owner in AI_NAMES:

        if state["ai_budgets"][owner] < price:
            return False

        state["ai_budgets"][owner] -= price

        state["ai_rosters"][owner].append(
            {
                **player,
                "cost": price,
            }
        )

        return True

    return False


# ============================================================
# 새로운 게임
# ============================================================

def create_game(players):
    normalized = [
        normalize_player(p)
        for p in players
        if isinstance(p, dict)
    ]

    if len(normalized) < TOTAL_ROUNDS:
        raise ValueError(
            f"경매에 필요한 선수 수가 부족합니다. "
            f"{TOTAL_ROUNDS}명 이상 필요합니다."
        )

    # 매 게임 시장 순서를 랜덤
    random.shuffle(normalized)

    auction_players = normalized[:TOTAL_ROUNDS]

    state = {
        "version": 2,

        "round": 1,
        "total_rounds": TOTAL_ROUNDS,

        "budget": START_BUDGET,

        "roster": [],

        "ai_budgets": {
            key: START_BUDGET
            for key in AI_NAMES
        },

        "ai_rosters": {
            key: []
            for key in AI_NAMES
        },

        "players": auction_players,

        "current": auction_players[0],

        "price": 1,

        "leader": None,

        "message": "경매가 시작되었습니다.",

        "history": [],

        "finished": False,

        "result": None,
    }

    return state


# ============================================================
# 다음 선수
# ============================================================

def prepare_next_round(state):

    next_round = state["round"] + 1

    if next_round > state["total_rounds"]:
        finish_game(state)
        return state

    state["round"] = next_round

    player = state["players"][
        next_round - 1
    ]

    state["current"] = player

    state["price"] = 1

    state["leader"] = None

    state["message"] = (
        f"{player_name(player)} 선수가 "
        f"시장에 등장했습니다."
    )

    return state


# ============================================================
# 사용자 액션
# ============================================================

def user_action(
    state,
    action,
):
    if state.get("finished"):
        return state

    player = state["current"]

    # --------------------------------------------------------
    # 포기
    # --------------------------------------------------------

    if action == "pass":

        result = run_ai_competition(
            player,
            0,
            state,
        )

        price = result["price"]
        leader = result["leader"]

        if leader == "user":
            leader = None

        if leader in AI_NAMES:

            acquire_player(
                leader,
                player,
                price,
                state,
            )

            state["message"] = (
                f"{AI_NAMES[leader]}이(가) "
                f"{player_name(player)}을(를) "
                f"{price}P에 영입했습니다."
            )

            state["history"].append({
                "round": state["round"],
                "player": player_name(player),
                "position": player_position(player),
                "price": price,
                "owner": leader,
            })

        else:

            state["message"] = (
                f"{player_name(player)} 선수는 "
                f"아무도 영입하지 않았습니다."
            )

        return prepare_next_round(state)

    # --------------------------------------------------------
    # 숫자 입찰
    # --------------------------------------------------------

    try:
        increment = int(action)
    except (
        TypeError,
        ValueError,
    ):
        return state

    if increment not in (1, 3, 5):
        return state

    new_price = state["price"] + increment

    if state["budget"] < new_price:
        state["message"] = (
            "보유 포인트가 부족합니다."
        )
        return state

    # 사용자 선두
    state["price"] = new_price
    state["leader"] = "user"

    # AI 경쟁
    competition = run_ai_competition(
        player,
        new_price,
        state,
    )

    state["price"] = competition["price"]
    state["leader"] = competition["leader"]

    # AI가 이김
    if competition["leader"] in AI_NAMES:

        owner = competition["leader"]
        price = competition["price"]

        acquire_player(
            owner,
            player,
            price,
            state,
        )

        state["message"] = (
            f"🤖 {AI_NAMES[owner]}이(가) "
            f"{player_name(player)}을(를) "
            f"{price}P에 영입했습니다."
        )

        state["history"].append({
            "round": state["round"],
            "player": player_name(player),
            "position": player_position(player),
            "price": price,
            "owner": owner,
        })

        return prepare_next_round(state)

    # 사용자 선두 유지
    state["message"] = (
        f"🔥 현재 {new_price}P "
        f"최고 입찰자는 나입니다."
    )

    # 마지막 라운드에서 사용자가 입찰한 경우
    if state["round"] >= state["total_rounds"]:

        acquire_player(
            "user",
            player,
            new_price,
            state,
        )

        state["history"].append({
            "round": state["round"],
            "player": player_name(player),
            "position": player_position(player),
            "price": new_price,
            "owner": "user",
        })

        return finish_game(state)

    return state


# ============================================================
# 강제 종료/낙찰
# ============================================================

def settle_current_for_user(state):

    if state.get("finished"):
        return state

    player = state["current"]
    price = state["price"]

    if state["budget"] < price:
        return state

    acquire_player(
        "user",
        player,
        price,
        state,
    )

    state["history"].append({
        "round": state["round"],
        "player": player_name(player),
        "position": player_position(player),
        "price": price,
        "owner": "user",
    })

    return prepare_next_round(state)


# ============================================================
# 팀 평가
# ============================================================

def team_score(roster):
    if not roster:
        return 0.0

    overalls = [
        player_overall(p)
        for p in roster
    ]

    total = sum(overalls)
    average = total / len(overalls)

    # 선수 수 보정
    size_bonus = min(
        len(roster) * 0.7,
        8
    )

    # 포지션 밸런스
    needs = roster_needs(roster)

    balance = 0

    targets = {
        "SP": 3,
        "RP": 2,
        "C": 1,
        "IF": 3,
        "OF": 3,
    }

    for group, target in targets.items():

        count = needs.get(group, 0)

        if count >= target:
            balance += 1

        elif count >= target * 0.66:
            balance += 0.5

    balance_bonus = balance * 1.2

    return round(
        average
        + size_bonus
        + balance_bonus,
        2,
    )


def efficiency_score(roster, spent):
    if not roster:
        return 0

    raw = sum(
        player_overall(p)
        for p in roster
    )

    if spent <= 0:
        return 100

    efficiency = (
        raw / spent
    ) * 8

    return round(
        min(100, efficiency),
        2,
    )


def balance_score(roster):
    if not roster:
        return 0

    needs = roster_needs(roster)

    targets = {
        "SP": 3,
        "RP": 2,
        "C": 1,
        "IF": 3,
        "OF": 3,
    }

    scores = []

    for group, target in targets.items():

        current = needs[group]

        scores.append(
            min(
                1,
                current / target
            )
        )

    return round(
        sum(scores)
        / len(scores)
        * 100,
        2,
    )


# ============================================================
# 등급
# ============================================================

def calculate_grade(score, rank):

    if rank == 1 and score >= 95:
        return "S+"

    if rank == 1 and score >= 90:
        return "S"

    if score >= 90:
        return "A+"

    if score >= 85:
        return "A"

    if score >= 80:
        return "B+"

    if score >= 75:
        return "B"

    if score >= 65:
        return "C"

    return "D"


# ============================================================
# 최종 결과
# ============================================================

def finish_game(state):

    if state.get("finished"):
        return state

    teams = {
        "user": state["roster"],
        **state["ai_rosters"],
    }

    results = []

    for team_key, roster in teams.items():

        spent = sum(
            _num(
                p.get("cost"),
                0
            )
            for p in roster
        )

        power = team_score(roster)

        efficiency = efficiency_score(
            roster,
            spent,
        )

        balance = balance_score(
            roster
        )

        final_score = round(
            power * 0.65
            + efficiency * 0.20
            + balance * 0.15,
            2,
        )

        results.append({
            "team": team_key,
            "name": (
                "나"
                if team_key == "user"
                else AI_NAMES[team_key]
            ),
            "roster": roster,
            "spent": round(spent, 1),
            "remaining": round(
                (
                    state["budget"]
                    if team_key == "user"
                    else state["ai_budgets"][team_key]
                ),
                1,
            ),
            "power": round(power, 2),
            "efficiency": efficiency,
            "balance": balance,
            "score": final_score,
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    for index, result in enumerate(
        results,
        start=1,
    ):
        result["rank"] = index

        result["grade"] = calculate_grade(
            result["score"],
            index,
        )

    user_result = next(
        x
        for x in results
        if x["team"] == "user"
    )

    second_score = (
        results[1]["score"]
        if user_result["rank"] == 1
        else results[0]["score"]
    )

    user_result["win_margin"] = round(
        user_result["score"]
        - second_score,
        2,
    )

    # 최고의 영입
    best_bargain = None

    for p in state["roster"]:

        cost = _num(
            p.get("cost"),
            0,
        )

        ratio = value_ratio(
            p,
            cost,
        )

        if (
            best_bargain is None
            or ratio > best_bargain["ratio"]
        ):
            best_bargain = {
                "name": player_name(p),
                "position": player_position(p),
                "overall": player_overall(p),
                "cost": cost,
                "market_value": market_value(p),
                "ratio": ratio,
            }

    state["finished"] = True

    state["result"] = {
        "results": results,
        "user": user_result,
        "best_bargain": best_bargain,
    }

    state["message"] = (
        "🏆 경기가 종료되었습니다."
    )

    return state


# ============================================================
# 직렬화
# ============================================================

def export_state(state):
    """
    Supabase JSON 저장용.
    """

    return copy.deepcopy(state)


def import_state(data):
    """
    Supabase JSON → 게임 상태.
    """

    state = copy.deepcopy(data)

    state.setdefault(
        "version",
        2,
    )

    state.setdefault(
        "ai_budgets",
        {
            key: START_BUDGET
            for key in AI_NAMES
        },
    )

    state.setdefault(
        "ai_rosters",
        {
            key: []
            for key in AI_NAMES
        },
    )

    state.setdefault(
        "history",
        [],
    )

    state.setdefault(
        "finished",
        False,
    )

    return state
