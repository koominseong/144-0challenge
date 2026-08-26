import random
import time
import copy
from datetime import datetime


# ============================================================
# 기본 설정
# ============================================================

START_BUDGET = 100

# 팀 전체 구성
# 필요하면 여기 숫자만 바꾸면 됨.
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

# 경매 시작가
START_PRICE = 1

# 입찰 버튼
BID_AMOUNTS = [1, 3, 5]

# 한 경매의 제한시간
AUCTION_SECONDS = 5


# ============================================================
# AI
# ============================================================

AI_NAMES = {
    "ai_1": "승부사",
    "ai_2": "데이터파",
    "ai_3": "베테랑",
    "ai_4": "알뜰단장",
}


# AI 성향
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
# 공통 유틸
# ============================================================

def now_text():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def safe_int(value, default=0):
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def player_name(player):
    return (
        player.get("name")
        or player.get("player_name")
        or player.get("playerName")
        or "이름없음"
    )


def player_team(player):
    return (
        player.get("team")
        or player.get("team_name")
        or player.get("teamName")
        or "-"
    )


def player_position(player):
    return (
        player.get("position")
        or player.get("pos")
        or player.get("position_name")
        or "-"
    )


def player_overall(player):
    return safe_int(
        player.get("overall")
        or player.get("ovr")
        or player.get("rating")
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
# 포지션
# ============================================================

def get_position_count(roster, position):

    return sum(
        1
        for p in roster
        if player_position(p) == position
    )


def can_add_player(roster, player):

    position = player_position(player)

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

        if (
            get_position_count(
                roster,
                position
            )
            < limit
        ):
            return False

    return True


# ============================================================
# 점수
# ============================================================

def roster_score(roster):

    if not roster:
        return 0

    total = 0

    for player in roster:

        ovr = player_overall(
            player
        )

        total += ovr

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

    raw = (
        roster_score(roster)
        / spent
    ) * 100

    return round(
        raw,
        1
    )


# ============================================================
# 등급
# ============================================================

def grade_from_rank(
    rank,
    total
):

    if rank == 1:
        return "S"

    if rank == 2:
        return "A+"

    if rank == 3:
        return "A"

    if rank <= max(
        4,
        int(total * 0.5)
    ):
        return "B"

    return "C"


# ============================================================
# 게임 생성
# ============================================================

def create_game(players=None):

    if players is None:
        players = []

    normalized = []

    for player in players:

        p = normalize_player(
            player
        )

        position = p["position"]

        if position not in ROSTER_LIMITS:
            continue

        normalized.append(p)

    # 선수풀이 부족할 경우에도 게임 자체는 실행
    random.shuffle(
        normalized
    )

    game = {

        "created_at":
            now_text(),

        "budget":
            START_BUDGET,

        "start_budget":
            START_BUDGET,

        "roster":
            [],

        "ai_rosters": {
            key: []
            for key in AI_NAMES
        },

        "ai_budgets": {
            key: START_BUDGET
            for key in AI_NAMES
        },

        "ai_names":
            AI_NAMES.copy(),

        "roster_limits":
            ROSTER_LIMITS.copy(),

        "players":
            normalized,

        "round":
            0,

        "total_rounds":
            TOTAL_SLOTS,

        "current":
            None,

        "price":
            START_PRICE,

        "leader":
            None,

        "timer_started":
            time.time(),

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

        "result":
            None,

        # AI가 같은 턴에 무한 입찰하지 않게 함
        "ai_last_bid_at": {},

        "ai_bid_count": {
            key: 0
            for key in AI_NAMES
        },
    }

    next_round(game)

    return game


# ============================================================
# 다음 선수
# ============================================================

def next_round(game):

    if game.get("finished"):
        return

    # 팀이 완성되었으면 종료
    if roster_complete(
        game.get("roster", [])
    ):

        finish_game(game)
        return

    players = game.get(
        "players",
        []
    )

    # 남은 선수 중 내 팀에서 채울 수 있는 선수 찾기
    candidates = []

    for player in players:

        if player in game.get(
            "passed_players",
            []
        ):
            continue

        if can_add_player(
            game.get("roster", []),
            player
        ):
            candidates.append(
                player
            )

    # 후보가 없으면 종료
    if not candidates:

        finish_game(game)
        return

    # 너무 좋은 선수만 계속 나오는 것을 방지
    player = candidates[0]

    game["current"] = player

    game["round"] = (
        game.get("round", 0)
        + 1
    )

    game["price"] = START_PRICE

    game["leader"] = None

    game["timer_started"] = time.time()

    game["last_bid_at"] = time.time()

    game["message"] = (
        f"{player_name(player)} 선수가 "
        f"경매에 등장했습니다."
    )

    game["ai_last_bid_at"] = {}

    game["ai_bid_count"] = {
        key: 0
        for key in AI_NAMES
    }


# ============================================================
# 타이머
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


def is_bid_expired(game):

    return seconds_left(
        game
    ) <= 0


def reset_timer(game):

    game["last_bid_at"] = time.time()


# ============================================================
# 입찰 기록
# ============================================================

def add_bid_log(
    game,
    bidder,
    price,
    amount
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
            player_name(player)
            if player else "-",

        "position":
            player_position(player)
            if player else "-",

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
# 현재 선수 가치
# ============================================================

def base_player_value(player):

    ovr = player_overall(
        player
    )

    position = player_position(
        player
    )

    # OVR 기반 기본 가치
    value = (
        ovr * 0.65
    )

    # 투수 중요도 약간 증가
    if position in (
        "SP",
        "RP",
        "CP",
    ):
        value += 5

    return max(
        5,
        round(value, 1)
    )


# ============================================================
# AI 포지션 필요성
# ============================================================

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

    # 비어 있을수록 높은 필요도
    missing = (
        limit - current
    )

    return min(
        1.0,
        0.45
        +
        missing * 0.12
    )


# ============================================================
# AI 최대 입찰가
# ============================================================

def ai_max_bid(
    ai_key,
    player,
    game
):

    budget = game[
        "ai_budgets"
    ][ai_key]

    style = AI_STYLE[
        ai_key
    ]

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
            0.75
            +
            need
        )
    )

    # 예산에 따라 상한
    maximum = min(
        budget,
        max(
            1,
            int(value)
        )
    )

    return maximum


# ============================================================
# AI 입찰 여부
# ============================================================

def ai_should_bid(
    ai_key,
    player,
    game
):

    if not player:
        return False

    # 해당 포지션이 이미 꽉 참
    if not can_add_player(
        game["ai_rosters"][ai_key],
        player
    ):
        return False

    budget = game[
        "ai_budgets"
    ][ai_key]

    price = game[
        "price"
    ]

    if budget <= price:
        return False

    maximum = ai_max_bid(
        ai_key,
        player,
        game
    )

    if price >= maximum:
        return False

    style = AI_STYLE[
        ai_key
    ]

    need = ai_need(
        game,
        ai_key,
        player
    )

    # 가격이 가치에 가까워질수록 확률 감소
    ratio = (
        price / max(
            1,
            maximum
        )
    )

    probability = (
        style["aggression"]
        *
        (1 - ratio * 0.7)
        *
        (0.7 + need * 0.5)
    )

    # 현재 최고 입찰자가 본인이면
    # 다시 연속으로 입찰할 확률 낮춤
    if game.get("leader") == ai_key:
        probability *= 0.35

    return (
        random.random()
        < probability
    )


# ============================================================
# AI 입찰 금액
# ============================================================

def choose_ai_amount(
    ai_key,
    possible
):

    if not possible:
        return None

    style = AI_STYLE[
        ai_key
    ]

    aggression = style[
        "aggression"
    ]

    # 공격적 AI일수록 큰 금액
    if aggression >= 0.65:

        if 5 in possible and random.random() < 0.45:
            return 5

        if 3 in possible and random.random() < 0.65:
            return 3

    elif aggression >= 0.5:

        if 3 in possible and random.random() < 0.45:
            return 3

    return 1


# ============================================================
# AI 한 명 행동
# ============================================================

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
        ai_key,
        player,
        game
    ):
        return False

    maximum = ai_max_bid(
        ai_key,
        player,
        game
    )

    budget = game[
        "ai_budgets"
    ][ai_key]

    possible = []

    for amount in BID_AMOUNTS:

        new_price = (
            game["price"]
            + amount
        )

        if new_price <= maximum:
            if new_price <= budget:
                possible.append(
                    amount
                )

    if not possible:
        return False

    amount = choose_ai_amount(
        ai_key,
        possible
    )

    if amount is None:
        return False

    new_price = (
        game["price"]
        + amount
    )

    game["price"] = new_price

    game["leader"] = ai_key

    game["ai_last_bid_at"][
        ai_key
    ] = time.time()

    game["ai_bid_count"][
        ai_key
    ] += 1

    reset_timer(game)

    add_bid_log(
        game,
        ai_key,
        new_price,
        amount
    )

    game["message"] = (
        f"🤖 {AI_NAMES[ai_key]} "
        f"+{amount}P → "
        f"{new_price}P"
    )

    return True


# ============================================================
# AI 전체 행동
# ============================================================

def run_ai_battle(game):

    if game.get("finished"):
        return False

    player = game.get(
        "current"
    )

    if not player:
        return False

    # 한 번의 API 요청에서
    # AI가 최대 한 번만 입찰
    candidates = []

    for ai_key in AI_NAMES:

        last = game.get(
            "ai_last_bid_at",
            {}
        ).get(
            ai_key,
            0
        )

        # 너무 빠른 연속 입찰 방지
        if (
            time.time()
            - last
            < 0.8
        ):
            continue

        if ai_should_bid(
            ai_key,
            player,
            game
        ):
            candidates.append(
                ai_key
            )

    if not candidates:
        return False

    # AI들이 서로 경쟁하게 함
    # 가치가 높은 AI를 우선하지만
    # 항상 승부사만 선택하지 않도록 랜덤 가중
    weights = []

    for ai_key in candidates:

        style = AI_STYLE[
            ai_key
        ]

        need = ai_need(
            game,
            ai_key,
            player
        )

        weight = (
            0.5
            +
            style["aggression"]
            +
            need
            +
            random.random()
        )

        weights.append(
            weight
        )

    selected = random.choices(
        candidates,
        weights=weights,
        k=1
    )[0]

    return ai_bid(
        game,
        selected
    )


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

    if not can_add_player(
        game["roster"],
        player
    ):

        game["message"] = (
            "이 포지션은 이미 정원이 찼습니다."
        )

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

    reset_timer(game)

    add_bid_log(
        game,
        "user",
        new_price,
        amount
    )

    game["message"] = (
        f"👤 나 +{amount}P → "
        f"{new_price}P"
    )

    return True


# ============================================================
# 낙찰
# ============================================================

def settle_current_auction(game):

    player = game.get(
        "current"
    )

    leader = game.get(
        "leader"
    )

    if not player or not leader:
        return False

    price = game.get(
        "price",
        START_PRICE
    )

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    if leader == "user":

        if price > game["budget"]:

            game["message"] = (
                "예산 부족으로 낙찰할 수 없습니다."
            )

            return False

        game["budget"] -= price

        player_copy = copy.deepcopy(
            player
        )

        player_copy["cost"] = price

        game["roster"].append(
            player_copy
        )

        winner_name = "나"

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    else:

        ai_budget = game[
            "ai_budgets"
        ][leader]

        if price > ai_budget:

            return False

        game[
            "ai_budgets"
        ][leader] -= price

        player_copy = copy.deepcopy(
            player
        )

        player_copy["cost"] = price

        game[
            "ai_rosters"
        ][leader].append(
            player_copy
        )

        winner_name = AI_NAMES[
            leader
        ]

    # 기록
    game.setdefault(
        "auction_history",
        []
    ).append({

        "player":
            player_name(player),

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

    game["message"] = (
        f"🔨 {player_name(player)} "
        f"{price}P 낙찰! "
        f"({winner_name})"
    )

    # 현재 선수 제거
    try:
        game["players"].remove(
            player
        )
    except ValueError:
        pass

    game["current"] = None

    # 팀 완성 여부
    if roster_complete(
        game["roster"]
    ):

        finish_game(game)
        return True

    next_round(game)

    return True


# ============================================================
# 패스
# ============================================================

def user_pass(game):

    if game.get("finished"):
        return False

    # 내가 최고가라면
    # 바로 낙찰하지 않고 AI에게 경쟁 기회를 준다.
    if game.get("leader") == "user":

        run_ai_battle(game)

        return True

    # AI가 최고가라면
    # 내가 PASS → AI 낙찰
    if game.get("leader") in AI_NAMES:

        settle_current_auction(game)

        return True

    # 아무도 입찰하지 않았다면
    # AI에게 첫 입찰 기회
    if run_ai_battle(game):
        return True

    return False


# ============================================================
# 게임 종료
# ============================================================

def build_result(game):

    players = []

    user_roster = game.get(
        "roster",
        []
    )

    user_spent = (
        game["start_budget"]
        -
        game["budget"]
    )

    players.append({

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

    for ai_key, ai_name in AI_NAMES.items():

        roster = game[
            "ai_rosters"
        ][ai_key]

        spent = (
            game["start_budget"]
            -
            game["ai_budgets"][ai_key]
        )

        players.append({

            "key":
                ai_key,

            "name":
                ai_name,

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

    # 점수 우선
    players.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    total = len(players)

    for index, result in enumerate(
        players,
        start=1
    ):

        result["rank"] = index

        result["grade"] = (
            grade_from_rank(
                index,
                total
            )
        )

    user_result = next(
        x
        for x in players
        if x["is_user"]
    )

    # 1위 점수
    first_score = players[0][
        "score"
    ]

    user_result[
        "win_margin"
    ] = round(
        user_result["score"]
        - first_score,
        1
    )

    # 최고의 가성비 영입
    best_bargain = None

    for player in user_roster:

        cost = safe_int(
            player.get(
                "cost",
                0
            ),
            1
        )

        ovr = player_overall(
            player
        )

        value = round(
            ovr / max(
                1,
                cost
            ),
            2
        )

        p = copy.deepcopy(
            player
        )

        p["value"] = value

        if (
            best_bargain is None
            or value
            > best_bargain["value"]
        ):
            best_bargain = p

    # 결과
    return {

        "results":
            players,

        "user":
            user_result,

        "history":
            game.get(
                "auction_history",
                []
            ),

        "best_bargain":
            best_bargain,

        "roster_limits":
            ROSTER_LIMITS.copy(),

    }


def finish_game(game):

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
        return game

    # --------------------------------------------------------
    # 입찰
    # --------------------------------------------------------

    if action in (
        "1",
        "3",
        "5",
    ):

        user_bid(
            game,
            int(action)
        )

        return game

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if action == "pass":

        user_pass(
            game
        )

        return game

    # --------------------------------------------------------
    # SOLD
    # --------------------------------------------------------

    if action == "sold":

        if game.get(
            "leader"
        ) != "user":

            game["message"] = (
                "현재 최고 입찰자가 아닙니다."
            )

            return game

        settle_current_auction(
            game
        )

        return game

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    if action == "timeout":

        if not is_bid_expired(
            game
        ):
            return game

        leader = game.get(
            "leader"
        )

        # 최고 입찰자가 있다면 낙찰
        if leader:

            settle_current_auction(
                game
            )

            return game

        # 아무도 입찰하지 않았다면
        # AI에게 마지막 기회
        if run_ai_battle(game):

            return game

        # 아무도 관심 없으면 다음 선수
        current = game.get(
            "current"
        )

        if current:

            game.setdefault(
                "passed_players",
                []
            ).append(
                current
            )

        next_round(game)

        return game

    return game
