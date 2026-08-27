import json
import random
import time
from pathlib import Path


# =========================================================
# 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PLAYER_POOL_PATH = BASE_DIR / "player_pool.json"

INITIAL_BUDGET = 1000

# 선수 등장 직후 제한시간
INITIAL_AUCTION_TIME = 10

# 누군가 입찰하면 남은 시간이 5초로 리셋
BID_RESET_TIME = 5

# 최종 로스터
ROSTER_LIMITS = {
    "포수": 1,
    "내야": 4,
    "외야": 3,

    "선발": 5,
    "불펜": 3,
    "마무리": 1,
}

TOTAL_ROSTER_SIZE = sum(
    ROSTER_LIMITS.values()
)

# 최대 라운드
MAX_ROUNDS = TOTAL_ROSTER_SIZE * 2

VALID_POSITIONS = {
    "선발",
    "불펜",
    "마무리",
    "포수",
    "내야",
    "외야",
}


# =========================================================
# 선수 풀
# =========================================================

def load_player_pool():

    if not PLAYER_POOL_PATH.exists():
        raise FileNotFoundError(
            f"player_pool.json을 찾을 수 없습니다.\n"
            f"경로: {PLAYER_POOL_PATH}"
        )

    with open(
        PLAYER_POOL_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "player_pool.json 최상위 구조는 배열([])이어야 합니다."
        )

    players = []

    for index, raw in enumerate(data):

        if not isinstance(raw, dict):
            continue

        name = str(
            raw.get("name", "")
        ).strip()

        team = str(
            raw.get("team", "")
        ).strip()

        position = str(
            raw.get("position", "")
        ).strip()

        try:
            overall = float(
                raw.get("overall", 0)
            )
        except (
            TypeError,
            ValueError
        ):
            overall = 0.0

        try:
            rank = int(
                raw.get("rank", 9999)
            )
        except (
            TypeError,
            ValueError
        ):
            rank = 9999

        if not name:
            continue

        if position not in VALID_POSITIONS:
            print(
                "[AUCTION] 알 수 없는 포지션 제외:",
                name,
                position
            )
            continue

        players.append({
            "id": index,
            "name": name,
            "team": team,
            "position": position,
            "overall": overall,
            "rank": rank,
        })

    if not players:
        raise ValueError(
            "사용 가능한 선수가 없습니다."
        )

    print(
        f"[AUCTION] 선수 풀 로딩 완료: "
        f"{len(players)}명"
    )

    return players


# =========================================================
# 가격
# =========================================================

def starting_price(player):

    overall = float(
        player.get("overall", 70)
    )

    if overall >= 95:
        return 80

    if overall >= 92:
        return 65

    if overall >= 89:
        return 50

    if overall >= 86:
        return 35

    if overall >= 82:
        return 25

    if overall >= 78:
        return 15

    return 10


def bid_increment(current_price):

    if current_price < 50:
        return 10

    if current_price < 100:
        return 10

    if current_price < 200:
        return 20

    return 30


# =========================================================
# 로스터
# =========================================================

def roster_count(
    roster,
    position
):
    return sum(
        1
        for player in roster
        if player.get("position") == position
    )


def can_add_player(
    roster,
    player
):

    position = player.get(
        "position"
    )

    limit = ROSTER_LIMITS.get(
        position,
        0
    )

    return (
        roster_count(
            roster,
            position
        )
        < limit
    )


def roster_full(roster):

    return len(roster) >= TOTAL_ROSTER_SIZE


def roster_complete(roster):

    if len(roster) != TOTAL_ROSTER_SIZE:
        return False

    for position, limit in ROSTER_LIMITS.items():

        if roster_count(
            roster,
            position
        ) != limit:
            return False

    return True


# =========================================================
# AI
# =========================================================

AI_NAMES = [
    "승부사",
    "스카우터",
    "단장님",
    "야구광",
]


def create_ai(index):

    return {
        "id": f"ai_{index}",
        "name": AI_NAMES[index],
        "budget": INITIAL_BUDGET,
        "roster": [],
        "spent": 0,
        "bids": 0,
        "wins": 0,
    }


def ai_can_bid(
    ai,
    player
):

    if ai["budget"] <= 0:
        return False

    return can_add_player(
        ai["roster"],
        player
    )


def ai_max_price(
    ai,
    player
):

    overall = float(
        player.get(
            "overall",
            70
        )
    )

    value = overall * 2.0

    personality_bonus = {
        "승부사": 1.15,
        "스카우터": 0.95,
        "단장님": 1.05,
        "야구광": 1.10,
    }.get(
        ai["name"],
        1.0
    )

    value *= personality_bonus

    # AI가 예산을 한 선수에게 전부 쓰지 않도록
    budget_limit = ai["budget"] * 0.65

    return min(
        value,
        budget_limit
    )


def ai_should_bid(
    ai,
    player,
    current_price,
    amount
):

    if not ai_can_bid(
        ai,
        player
    ):
        return False

    next_price = (
        current_price
        + amount
    )

    max_price = ai_max_price(
        ai,
        player
    )

    if next_price > max_price:
        return False

    if next_price > ai["budget"]:
        return False

    overall = float(
        player.get(
            "overall",
            70
        )
    )

    if overall >= 93:
        probability = 0.85

    elif overall >= 90:
        probability = 0.72

    elif overall >= 85:
        probability = 0.55

    elif overall >= 80:
        probability = 0.38

    else:
        probability = 0.25

    # 비싸질수록 신중
    if current_price > max_price * 0.65:
        probability *= 0.65

    # +50은 AI도 자주 못 누르게
    if amount == 50:
        probability *= 0.65

    return random.random() < probability


def choose_ai_bid(
    game
):

    player = game.get(
        "current_player"
    )

    if not player:
        return None

    current_price = game[
        "current_price"
    ]

    candidates = []

    for ai in game["ais"]:

        if not ai_can_bid(
            ai,
            player
        ):
            continue

        # AI도 10/30/50 중 선택
        possible_amounts = [
            amount
            for amount in (
                10,
                30,
                50
            )
            if (
                current_price + amount
                <= ai["budget"]
            )
        ]

        if not possible_amounts:
            continue

        # 보통 10억, 좋은 선수면 30억,
        # 아주 좋은 상황에서 50억
        if player["overall"] >= 93:
            weights = [0.25, 0.50, 0.25]

        elif player["overall"] >= 88:
            weights = [0.50, 0.40, 0.10]

        else:
            weights = [0.75, 0.22, 0.03]

        # 실제 가능한 금액만 추림
        filtered = []

        for amount, weight in zip(
            (10, 30, 50),
            weights
        ):
            if amount in possible_amounts:
                filtered.append(
                    (amount, weight)
                )

        if not filtered:
            continue

        total = sum(
            weight
            for _, weight in filtered
        )

        r = random.random() * total

        selected_amount = None

        for amount, weight in filtered:

            r -= weight

            if r <= 0:
                selected_amount = amount
                break

        if selected_amount is None:
            selected_amount = filtered[-1][0]

        if ai_should_bid(
            ai,
            player,
            current_price,
            selected_amount
        ):
            candidates.append(
                (
                    ai,
                    selected_amount
                )
            )

    if not candidates:
        return None

    # 높은 지불 의향 우선
    candidates.sort(
        key=lambda item:
            ai_max_price(
                item[0],
                player
            ),
        reverse=True
    )

    # 가끔 2위 AI도 낙찰 경쟁
    if (
        len(candidates) >= 2
        and random.random() < 0.30
    ):
        return random.choice(
            candidates[:2]
        )

    return candidates[0]


def run_ai_turn(game):

    if game["finished"]:
        return

    player = game.get(
        "current_player"
    )

    if not player:
        return

    # 한 번의 요청에서 AI가 너무 많이
    # 입찰하지 않도록 최대 2번
    for _ in range(2):

        result = choose_ai_bid(
            game
        )

        if result is None:
            break

        ai, amount = result

        next_price = (
            game["current_price"]
            + amount
        )

        if next_price > ai["budget"]:
            continue

        if not can_add_player(
            ai["roster"],
            player
        ):
            continue

        game["current_price"] = (
            next_price
        )

        game["highest_bidder"] = (
            ai["id"]
        )

        game["last_bid_at"] = (
            time.time()
        )

        # ⭐ AI 입찰도 5초 리셋
        game["auction_deadline"] = (
            time.time()
            + BID_RESET_TIME
        )

        ai["bids"] += 1

        game["bid_history"].append({
            "bidder": ai["name"],
            "price": next_price,
            "amount": amount,
            "time": time.strftime(
                "%H:%M:%S"
            ),
        })

        add_log(
            game,
            f"🤖 {ai['name']} → "
            f"{player['name']} "
            f"+{amount}억 "
            f"({next_price}억)"
        )

        # AI가 입찰하면 다음 요청까지 기다림
        break


# =========================================================
# 게임 생성
# =========================================================

def create_game(game_id):

    players = load_player_pool()

    random.shuffle(players)

    game = {
        "id": str(game_id),

        "budget": INITIAL_BUDGET,

        "roster": [],

        "ais": [
            create_ai(i)
            for i in range(4)
        ],

        "players": players,

        "used_player_ids": [],

        "round": 0,

        "total_rounds": MAX_ROUNDS,

        "current_player": None,

        "current_price": 0,

        "highest_bidder": None,

        "started_at": None,

        "last_bid_at": None,

        "auction_deadline": None,

        "finished": False,

        "result": None,

        "bid_history": [],

        "logs": [],
    }

    return game


# =========================================================
# 선수 선택
# =========================================================

def available_players(game):

    used = set(
        game.get(
            "used_player_ids",
            []
        )
    )

    return [
        player
        for player in game["players"]
        if player["id"] not in used
    ]


def choose_next_player(game):

    available = available_players(
        game
    )

    if not available:
        return None

    # 내 로스터에 필요한 포지션
    needed_positions = []

    for position, limit in (
        ROSTER_LIMITS.items()
    ):

        current = roster_count(
            game["roster"],
            position
        )

        if current < limit:
            needed_positions.append(
                position
            )

    candidates = [
        player
        for player in available
        if player["position"]
        in needed_positions
    ]

    if not candidates:
        candidates = available

    # 어느 정도 좋은 선수들 위주로
    # 등장시키되 매번 최고 선수는 아님
    candidates.sort(
        key=lambda p:
            p["overall"],
        reverse=True
    )

    top_count = min(
        len(candidates),
        50
    )

    return random.choice(
        candidates[:top_count]
    )


# =========================================================
# 라운드 시작
# =========================================================

def start_round(game):

    if game["finished"]:
        return False

    if roster_full(
        game["roster"]
    ):
        finish_game(game)
        return False

    player = choose_next_player(
        game
    )

    if player is None:
        finish_game(game)
        return False

    game["round"] += 1

    game["current_player"] = player

    game["used_player_ids"].append(
        player["id"]
    )

    game["current_price"] = (
        starting_price(player)
    )

    game["highest_bidder"] = None

    now = time.time()

    game["started_at"] = now

    game["last_bid_at"] = None

    # ⭐ 첫 등장만 10초
    game["auction_deadline"] = (
        now + INITIAL_AUCTION_TIME
    )

    game["bid_history"] = []

    add_log(
        game,
        f"🔔 {player['name']} "
        f"({player['team']}) "
        f"경매 시작! "
        f"시작가 "
        f"{game['current_price']}억"
    )

    return True


# =========================================================
# 로그
# =========================================================

def add_log(
    game,
    message
):

    game.setdefault(
        "logs",
        []
    )

    game["logs"].append({
        "time": time.strftime(
            "%H:%M:%S"
        ),
        "message": message,
    })

    if len(
        game["logs"]
    ) > 100:

        game["logs"] = (
            game["logs"][-100:]
        )


# =========================================================
# 사용자 입찰
# =========================================================

def user_bid(
    game,
    amount
):

    if game["finished"]:
        return (
            False,
            "게임이 종료되었습니다."
        )

    player = game.get(
        "current_player"
    )

    if not player:
        return (
            False,
            "현재 경매 선수가 없습니다."
        )

    # 시간 종료
    if auction_expired(game):

        settle_auction(game)

        return (
            False,
            "입찰 시간이 종료되었습니다."
        )

    if amount not in (
        10,
        30,
        50
    ):
        return (
            False,
            "잘못된 입찰 금액입니다."
        )

    if not can_add_player(
        game["roster"],
        player
    ):
        return (
            False,
            f"{player['position']} "
            f"포지션은 이미 정원을 "
            f"채웠습니다."
        )

    next_price = (
        game["current_price"]
        + amount
    )

    if next_price > game["budget"]:
        return (
            False,
            "예산이 부족합니다."
        )

    # =====================================
    # 입찰
    # =====================================

    game["current_price"] = (
        next_price
    )

    game["highest_bidder"] = "user"

    game["last_bid_at"] = (
        time.time()
    )

    # ⭐ 사용자 입찰마다 5초 리셋
    game["auction_deadline"] = (
        time.time()
        + BID_RESET_TIME
    )

    game["bid_history"].append({
        "bidder": "나",
        "price": next_price,
        "amount": amount,
        "time": time.strftime(
            "%H:%M:%S"
        ),
    })

    add_log(
        game,
        f"🧑 나 → "
        f"{player['name']} "
        f"+{amount}억 "
        f"({next_price}억)"
    )

    return (
        True,
        f"+{amount}억 입찰 성공"
    )


# =========================================================
# 시간
# =========================================================

def auction_expired(game):

    deadline = game.get(
        "auction_deadline"
    )

    if deadline is None:
        return False

    return time.time() >= deadline


def remaining_time(game):

    deadline = game.get(
        "auction_deadline"
    )

    if deadline is None:
        return INITIAL_AUCTION_TIME

    remain = (
        deadline
        - time.time()
    )

    return max(
        0,
        int(remain + 0.999)
    )


# =========================================================
# 낙찰
# =========================================================

def settle_auction(game):

    if game["finished"]:
        return

    player = game.get(
        "current_player"
    )

    if not player:
        return

    winner = game.get(
        "highest_bidder"
    )

    price = game.get(
        "current_price",
        0
    )

    # =====================================
    # 아무도 입찰하지 않음
    # =====================================

    if not winner:

        add_log(
            game,
            f"⚪ {player['name']} "
            f"무입찰 유찰"
        )

        game["current_player"] = None

        if (
            game["round"]
            >= game["total_rounds"]
        ):
            finish_game(game)

        else:
            start_round(game)

        return

    # =====================================
    # 사용자 낙찰
    # =====================================

    if winner == "user":

        if price > game["budget"]:

            add_log(
                game,
                "❌ 예산 부족으로 "
                "낙찰 취소"
            )

        else:

            game["budget"] -= price

            game["roster"].append(
                dict(player)
            )

            add_log(
                game,
                f"🏆 나 → "
                f"{player['name']} "
                f"{price}억 낙찰!"
            )

    # =====================================
    # AI 낙찰
    # =====================================

    else:

        ai = next(
            (
                a
                for a in game["ais"]
                if a["id"] == winner
            ),
            None
        )

        if ai:

            if price <= ai["budget"]:

                ai["budget"] -= price

                ai["spent"] += price

                ai["roster"].append(
                    dict(player)
                )

                ai["wins"] += 1

                add_log(
                    game,
                    f"🏆 {ai['name']} → "
                    f"{player['name']} "
                    f"{price}억 낙찰!"
                )

    # =====================================
    # 다음
    # =====================================

    game["current_player"] = None

    game["highest_bidder"] = None

    game["current_price"] = 0

    game["auction_deadline"] = None

    game["bid_history"] = []

    if roster_complete(
        game["roster"]
    ):
        finish_game(game)
        return

    if (
        game["round"]
        >= game["total_rounds"]
    ):
        finish_game(game)
        return

    start_round(game)


# =========================================================
# 점수
# =========================================================

def calculate_team_score(
    roster
):

    if not roster:
        return 0

    overall_total = sum(
        float(
            player.get(
                "overall",
                0
            )
        )
        for player in roster
    )

    average = (
        overall_total
        / len(roster)
    )

    position_bonus = 0

    for position, limit in (
        ROSTER_LIMITS.items()
    ):

        if (
            roster_count(
                roster,
                position
            )
            >= limit
        ):
            position_bonus += 3

    return round(
        average
        + position_bonus,
        2
    )


# =========================================================
# 등급
# =========================================================

def calculate_grade(
    score,
    rank
):

    if rank == 1:
        return "S"

    if rank == 2:
        return "A+"

    if rank == 3:
        return "A"

    if rank <= 5:
        return "B+"

    if rank <= 8:
        return "B"

    if rank <= 12:
        return "C"

    return "D"


# =========================================================
# 종료
# =========================================================

def finish_game(game):

    if game["finished"]:
        return

    game["finished"] = True

    user_score = calculate_team_score(
        game["roster"]
    )

    competitors = []

    competitors.append({
        "id": "user",
        "name": "나",
        "score": user_score,
        "roster": list(
            game["roster"]
        ),
    })

    for ai in game["ais"]:

        score = calculate_team_score(
            ai["roster"]
        )

        competitors.append({
            "id": ai["id"],
            "name": ai["name"],
            "score": score,
            "roster": list(
                ai["roster"]
            ),
        })

    competitors.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    for index, competitor in enumerate(
        competitors,
        start=1
    ):

        competitor["rank"] = index

        competitor["grade"] = (
            calculate_grade(
                competitor["score"],
                index
            )
        )

    user_result = next(
        x
        for x in competitors
        if x["id"] == "user"
    )

    game["result"] = {
        "score": user_result["score"],
        "rank": user_result["rank"],
        "grade": user_result["grade"],
        "competitors": competitors,
    }

    add_log(
        game,
        f"🏁 경기 종료 "
        f"{user_result['rank']}위 / "
        f"{user_result['grade']}등급"
    )


# =========================================================
# 게임 처리
# =========================================================

def process_game(game):

    if game["finished"]:
        return

    if not game.get(
        "current_player"
    ):
        start_round(game)
        return

    # AI 입찰
    run_ai_turn(game)

    # 시간 종료
    if auction_expired(game):
        settle_auction(game)


# =========================================================
# 직렬화
# =========================================================

def serialize_game(game):

    player = game.get(
        "current_player"
    )

    return {
        "id": game["id"],
        "budget": game["budget"],
        "roster": game["roster"],
        "ais": game["ais"],
        "round": game["round"],
        "total_rounds": game["total_rounds"],
        "current_player": player,
        "current_price": game[
            "current_price"
        ],
        "highest_bidder": game[
            "highest_bidder"
        ],
        "remaining_time": remaining_time(
            game
        ),
        "initial_time": INITIAL_AUCTION_TIME,
        "reset_time": BID_RESET_TIME,
        "finished": game["finished"],
        "result": game["result"],
        "bid_history": game[
            "bid_history"
        ],
        "logs": game["logs"],
    }
