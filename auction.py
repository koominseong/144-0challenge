import copy
import random
import time
from datetime import datetime


# ============================================================
# CONFIG
# ============================================================

START_BUDGET = 100

AUCTION_SECONDS = 5

BID_AMOUNTS = [1, 3, 5]


ROSTER_LIMITS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "LF": 1,
    "CF": 1,
    "RF": 1,
    "DH": 1,

    "SP": 5,
    "RP": 3,
    "CP": 1,
}


TOTAL_SLOTS = sum(
    ROSTER_LIMITS.values()
)


AI_NAMES = {
    "ai_1": "승부사",
    "ai_2": "데이터파",
    "ai_3": "베테랑",
    "ai_4": "알뜰단장",
}


AI_STYLE = {
    "ai_1": {
        "aggression": 0.72,
        "value": 1.20,
    },

    "ai_2": {
        "aggression": 0.55,
        "value": 1.08,
    },

    "ai_3": {
        "aggression": 0.45,
        "value": 1.00,
    },

    "ai_4": {
        "aggression": 0.32,
        "value": 0.88,
    },
}


# ============================================================
# UTIL
# ============================================================

def now_text():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def safe_int(
    value,
    default=0
):

    try:
        return int(value)
    except (
        TypeError,
        ValueError
    ):
        return default


def player_name(player):

    if not player:
        return "-"

    return (
        player.get("name")
        or player.get("player_name")
        or player.get("playerName")
        or player.get("선수명")
        or "이름없음"
    )


def player_team(player):

    if not player:
        return "-"

    return (
        player.get("team")
        or player.get("team_name")
        or player.get("teamName")
        or player.get("구단")
        or "-"
    )


def player_position(player):

    if not player:
        return "-"

    return (
        player.get("position")
        or player.get("pos")
        or player.get("position_name")
        or player.get("포지션")
        or "-"
    )


def player_overall(player):

    if not player:
        return 0

    return safe_int(
        player.get("overall")
        or player.get("ovr")
        or player.get("rating")
        or player.get("능력치")
        or 0
    )


def normalize_player(player):

    p = copy.deepcopy(player)

    p["name"] = player_name(p)
    p["team"] = player_team(p)
    p["position"] = player_position(p)
    p["overall"] = player_overall(p)

    return p


# ============================================================
# POSITION
# ============================================================

def get_position_count(
    roster,
    position
):

    return sum(
        1
        for player in roster
        if player_position(player) == position
    )


def can_add_player(
    roster,
    player
):

    position = player_position(
        player
    )

    limit = ROSTER_LIMITS.get(
        position,
        0
    )

    if limit <= 0:
        return False

    return (
        get_position_count(
            roster,
            position
        )
        < limit
    )


def roster_complete(roster):

    for position, limit in ROSTER_LIMITS.items():

        if get_position_count(
            roster,
            position
        ) < limit:

            return False

    return True


# ============================================================
# SCORE
# ============================================================

def roster_score(roster):

    total = 0

    for player in roster:

        total += player_overall(
            player
        )

    return round(
        total,
        1
    )


def efficiency_score(
    roster,
    spent
):

    if spent <= 0:
        return 0

    return round(
        roster_score(roster)
        / spent
        * 100,
        1
    )


# ============================================================
# GRADE
# ============================================================

def grade_from_rank(
    rank
):

    if rank == 1:
        return "S"

    if rank == 2:
        return "A+"

    if rank == 3:
        return "A"

    if rank == 4:
        return "B+"

    return "B"


# ============================================================
# CREATE GAME
# ============================================================

def create_game(players):

    normalized_players = []

    for player in players:

        try:

            p = normalize_player(
                player
            )

            if (
                p["position"]
                not in ROSTER_LIMITS
            ):
                continue

            normalized_players.append(
                p
            )

        except Exception:
            continue

    if not normalized_players:

        raise ValueError(
            "사용 가능한 선수가 없습니다."
        )

    random.shuffle(
        normalized_players
    )

    game = {

        "created_at":
            now_text(),

        "budget":
            START_BUDGET,

        "start_budget":
            START_BUDGET,

        "players":
            normalized_players,

        "roster":
            [],

        "ai_rosters": {
            ai: []
            for ai in AI_NAMES
        },

        "ai_budgets": {
            ai: START_BUDGET
            for ai in AI_NAMES
        },

        "ai_names":
            copy.deepcopy(
                AI_NAMES
            ),

        "roster_limits":
            copy.deepcopy(
                ROSTER_LIMITS
            ),

        "round":
            0,

        "total_rounds":
            TOTAL_SLOTS,

        "current":
            None,

        "price":
            0,

        "leader":
            None,

        "last_bid_at":
            time.time(),

        "finished":
            False,

        "message":
            "",

        "bid_log":
            [],

        "auction_history":
            [],

        "passed_players":
            [],

        "ai_last_bid_at": {
            ai: 0
            for ai in AI_NAMES
        },

        "result":
            None,
    }

    next_round(
        game
    )

    return game


# ============================================================
# NEXT PLAYER
# ============================================================

def next_round(game):

    if game.get("finished"):
        return

    if roster_complete(
        game["roster"]
    ):

        finish_game(
            game
        )

        return

    candidates = []

    for player in game["players"]:

        if player in game.get(
            "passed_players",
            []
        ):
            continue

        if can_add_player(
            game["roster"],
            player
        ):

            candidates.append(
                player
            )

    if not candidates:

        finish_game(
            game
        )

        return

    # OVR이 너무 낮은 선수만 계속 나오지 않게
    # 랜덤 후보 중 상위권을 선택
    candidates.sort(
        key=lambda p:
            player_overall(p),
        reverse=True
    )

    top_count = min(
        5,
        len(candidates)
    )

    player = random.choice(
        candidates[:top_count]
    )

    game["current"] = player

    game["round"] += 1

    game["price"] = 0

    game["leader"] = None

    game["last_bid_at"] = time.time()

    game["ai_last_bid_at"] = {
        ai: 0
        for ai in AI_NAMES
    }

    game["message"] = (
        f"📢 {player_name(player)} "
        f"선수가 경매에 등장했습니다!"
    )


# ============================================================
# TIMER
# ============================================================

def seconds_left(game):

    last_bid = game.get(
        "last_bid_at",
        time.time()
    )

    elapsed = (
        time.time()
        - last_bid
    )

    return max(
        0,
        AUCTION_SECONDS
        - int(elapsed)
    )


def is_expired(game):

    return seconds_left(
        game
    ) <= 0


def reset_timer(game):

    game["last_bid_at"] = time.time()


# ============================================================
# LOG
# ============================================================

def add_bid_log(
    game,
    bidder,
    amount,
    price
):

    if bidder == "user":

        name = "나"

    else:

        name = AI_NAMES.get(
            bidder,
            bidder
        )

    player = game.get(
        "current"
    )

    game.setdefault(
        "bid_log",
        []
    ).append({

        "player":
            player_name(player),

        "bidder":
            bidder,

        "name":
            name,

        "amount":
            amount,

        "price":
            price,

        "time":
            now_text(),
    })


# ============================================================
# USER BID
# ============================================================

def user_bid(
    game,
    amount
):

    if game.get("finished"):
        return False

    player = game.get(
        "current"
    )

    if not player:
        return False

    amount = safe_int(
        amount
    )

    if amount not in BID_AMOUNTS:

        game["message"] = (
            "잘못된 입찰입니다."
        )

        return False

    new_price = (
        game["price"]
        + amount
    )

    if new_price > game["budget"]:

        game["message"] = (
            "💸 예산이 부족합니다."
        )

        return False

    game["price"] = new_price

    game["leader"] = "user"

    reset_timer(
        game
    )

    add_bid_log(
        game,
        "user",
        amount,
        new_price
    )

    game["message"] = (
        f"👤 나 +{amount}P "
        f"→ {new_price}P"
    )

    return True


# ============================================================
# AI VALUE
# ============================================================

def base_player_value(
    player
):

    ovr = player_overall(
        player
    )

    position = player_position(
        player
    )

    value = (
        ovr * 0.65
    )

    if position in (
        "SP",
        "RP",
        "CP"
    ):

        value += 5

    return max(
        5,
        value
    )


def ai_need(
    game,
    ai_key,
    player
):

    roster = game[
        "ai_rosters"
    ][ai_key]

    position = player_position(
        player
    )

    limit = ROSTER_LIMITS.get(
        position,
        0
    )

    current = get_position_count(
        roster,
        position
    )

    if current >= limit:
        return 0

    return min(
        1,
        0.5
        +
        (
            limit
            - current
        )
        * 0.1
    )


def ai_max_bid(
    game,
    ai_key,
    player
):

    style = AI_STYLE[
        ai_key
    ]

    budget = game[
        "ai_budgets"
    ][ai_key]

    base = base_player_value(
        player
    )

    need = ai_need(
        game,
        ai_key,
        player
    )

    value = (
        base
        *
        style["value"]
        *
        (
            0.7
            +
            need
        )
    )

    return min(
        budget,
        max(
            1,
            int(value)
        )
    )


# ============================================================
# AI BID
# ============================================================

def ai_should_bid(
    game,
    ai_key,
    player
):

    if not can_add_player(
        game[
            "ai_rosters"
        ][ai_key],
        player
    ):
        return False

    budget = game[
        "ai_budgets"
    ][ai_key]

    if budget <= game["price"]:
        return False

    maximum = ai_max_bid(
        game,
        ai_key,
        player
    )

    if game["price"] >= maximum:
        return False

    style = AI_STYLE[
        ai_key
    ]

    ratio = (
        game["price"]
        /
        max(
            1,
            maximum
        )
    )

    probability = (
        style["aggression"]
        *
        (
            1
            -
            ratio * 0.65
        )
    )

    # 최고 입찰자면 연속 입찰 확률 감소
    if game.get(
        "leader"
    ) == ai_key:

        probability *= 0.15

    return (
        random.random()
        < probability
    )


def ai_bid(
    game,
    ai_key
):

    player = game.get(
        "current"
    )

    if not player:
        return False

    if not ai_should_bid(
        game,
        ai_key,
        player
    ):
        return False

    maximum = ai_max_bid(
        game,
        ai_key,
        player
    )

    budget = game[
        "ai_budgets"
    ][ai_key]

    possible = []

    for amount in BID_AMOUNTS:

        price = (
            game["price"]
            + amount
        )

        if (
            price <= maximum
            and
            price <= budget
        ):

            possible.append(
                amount
            )

    if not possible:
        return False

    # 공격적 AI일수록 큰 금액
    style = AI_STYLE[
        ai_key
    ]

    if (
        style["aggression"] > 0.65
        and
        5 in possible
        and
        random.random() < 0.4
    ):

        amount = 5

    elif (
        3 in possible
        and
        random.random() < 0.5
    ):

        amount = 3

    else:

        amount = 1

    new_price = (
        game["price"]
        + amount
    )

    game["price"] = new_price

    game["leader"] = ai_key

    game[
        "ai_last_bid_at"
    ][ai_key] = time.time()

    reset_timer(
        game
    )

    add_bid_log(
        game,
        ai_key,
        amount,
        new_price
    )

    game["message"] = (
        f"🤖 {AI_NAMES[ai_key]} "
        f"+{amount}P "
        f"→ {new_price}P"
    )

    return True


# ============================================================
# RUN AI
# ============================================================

def run_ai_battle(
    game
):

    if game.get("finished"):
        return False

    player = game.get(
        "current"
    )

    if not player:
        return False

    candidates = []

    for ai_key in AI_NAMES:

        last = game[
            "ai_last_bid_at"
        ].get(
            ai_key,
            0
        )

        if (
            time.time()
            - last
            < 1.0
        ):
            continue

        if ai_should_bid(
            game,
            ai_key,
            player
        ):

            candidates.append(
                ai_key
            )

    if not candidates:
        return False

    # 특정 AI만 계속 선택되지 않도록 랜덤
    selected = random.choice(
        candidates
    )

    return ai_bid(
        game,
        selected
    )


# ============================================================
# SETTLE
# ============================================================

def settle_current_auction(
    game
):

    player = game.get(
        "current"
    )

    leader = game.get(
        "leader"
    )

    if not player:
        return False

    if not leader:
        return False

    price = game.get(
        "price",
        0
    )

    # --------------------------------
    # USER
    # --------------------------------

    if leader == "user":

        if price > game["budget"]:

            game["message"] = (
                "예산이 부족합니다."
            )

            return False

        game["budget"] -= price

        p = copy.deepcopy(
            player
        )

        p["cost"] = price

        game["roster"].append(
            p
        )

        winner_name = "나"

    # --------------------------------
    # AI
    # --------------------------------

    else:

        budget = game[
            "ai_budgets"
        ][leader]

        if price > budget:
            return False

        game[
            "ai_budgets"
        ][leader] -= price

        p = copy.deepcopy(
            player
        )

        p["cost"] = price

        game[
            "ai_rosters"
        ][leader].append(
            p
        )

        winner_name = AI_NAMES[
            leader
        ]

    game[
        "auction_history"
    ].append({

        "player":
            player_name(player),

        "team":
            player_team(player),

        "position":
            player_position(player),

        "overall":
            player_overall(player),

        "price":
            price,

        "winner":
            leader,

        "winner_name":
            winner_name,

        "time":
            now_text(),
    })

    try:

        game["players"].remove(
            player
        )

    except ValueError:
        pass

    game["current"] = None

    game["leader"] = None

    game["price"] = 0

    if roster_complete(
        game["roster"]
    ):

        finish_game(
            game
        )

        return True

    next_round(
        game
    )

    return True


# ============================================================
# PASS
# ============================================================

def user_pass(
    game
):

    if game.get("finished"):
        return False

    # 최고 입찰자가 나면
    # PASS가 아니라 AI에게 마지막 도전 기회를 줌
    if game.get(
        "leader"
    ) == "user":

        return run_ai_battle(
            game
        )

    # AI가 최고면 낙찰
    if game.get(
        "leader"
    ) in AI_NAMES:

        return settle_current_auction(
            game
        )

    # 아무도 입찰하지 않은 경우
    return run_ai_battle(
        game
    )


# ============================================================
# RESULT
# ============================================================

def build_result(
    game
):

    result_players = []

    # USER
    user_roster = game[
        "roster"
    ]

    user_spent = (
        game["start_budget"]
        -
        game["budget"]
    )

    result_players.append({

        "key":
            "user",

        "name":
            "나",

        "roster":
            user_roster,

        "score":
            roster_score(
                user_roster
            ),

        "spent":
            user_spent,

        "remaining":
            game["budget"],

        "efficiency":
            efficiency_score(
                user_roster,
                user_spent
            ),

        "is_user":
            True,
    })

    # AI
    for ai_key in AI_NAMES:

        roster = game[
            "ai_rosters"
        ][ai_key]

        spent = (
            START_BUDGET
            -
            game[
                "ai_budgets"
            ][ai_key]
        )

        result_players.append({

            "key":
                ai_key,

            "name":
                AI_NAMES[ai_key],

            "roster":
                roster,

            "score":
                roster_score(
                    roster
                ),

            "spent":
                spent,

            "remaining":
                game[
                    "ai_budgets"
                ][ai_key],

            "efficiency":
                efficiency_score(
                    roster,
                    spent
                ),

            "is_user":
                False,
        })

    # 점수 순
    result_players.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    for rank, result in enumerate(
        result_players,
        start=1
    ):

        result["rank"] = rank

        result["grade"] = (
            grade_from_rank(
                rank
            )
        )

    user_result = next(
        x
        for x in result_players
        if x["is_user"]
    )

    # 최고 영입
    best_bargain = None

    for player in user_roster:

        cost = safe_int(
            player.get(
                "cost",
                0
            ),
            1
        )

        value = (
            player_overall(player)
            /
            max(
                1,
                cost
            )
        )

        p = copy.deepcopy(
            player
        )

        p["value"] = round(
            value,
            2
        )

        if (
            best_bargain is None
            or
            p["value"]
            >
            best_bargain["value"]
        ):

            best_bargain = p

    return {

        "results":
            result_players,

        "user":
            user_result,

        "history":
            game[
                "auction_history"
            ],

        "best_bargain":
            best_bargain,

        "roster_limits":
            ROSTER_LIMITS.copy(),
    }


# ============================================================
# FINISH
# ============================================================

def finish_game(
    game
):

    if game.get("finished"):
        return

    game["finished"] = True

    game["current"] = None

    game["result"] = build_result(
        game
    )

    game["message"] = (
        "🏆 경기가 종료되었습니다!"
    )


# ============================================================
# ACTION
# ============================================================

def user_action(
    game,
    action
):

    if game.get("finished"):
        return

    if action in (
        "1",
        "3",
        "5"
    ):

        user_bid(
            game,
            int(action)
        )

        return

    if action == "pass":

        user_pass(
            game
        )

        return

    if action == "sold":

        if game.get(
            "leader"
        ) != "user":

            game["message"] = (
                "현재 최고 입찰자가 아닙니다."
            )

            return

        settle_current_auction(
            game
        )

        return

    if action == "timeout":

        if not is_expired(
            game
        ):
            return

        # 최고 입찰자가 있으면 낙찰
        if game.get(
            "leader"
        ):

            settle_current_auction(
                game
            )

            return

        # 아무도 안 샀으면
        # AI에게 마지막 기회
        if run_ai_battle(
            game
        ):

            return

        # 아무도 관심 없음
        current = game.get(
            "current"
        )

        if current:

            game[
                "passed_players"
            ].append(
                current
            )

        next_round(
            game
        )
