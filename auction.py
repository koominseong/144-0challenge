import json
import random
import time
from pathlib import Path


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PLAYER_POOL_PATH = BASE_DIR / "player_pool.json"

INITIAL_BUDGET = 1000

# 한 팀이 최종적으로 가져갈 선수 수
ROSTER_LIMITS = {
    "포수": 1,
    "내야": 4,
    "외야": 3,

    "선발": 5,
    "불펜": 3,
    "마무리": 1,
}

TOTAL_ROSTER_SIZE = sum(ROSTER_LIMITS.values())

# 경매 한 선수의 제한 시간
AUCTION_TIME = 10

# 최대 경매 라운드
MAX_ROUNDS = TOTAL_ROSTER_SIZE * 2


# =========================================================
# 선수 풀
# =========================================================

VALID_POSITIONS = {
    "선발",
    "불펜",
    "마무리",
    "포수",
    "내야",
    "외야",
}


def load_player_pool():
    """
    실제 player_pool.json 구조:

    [
        {
            "position": "선발",
            "name": "류현진",
            "team": "한화",
            "overall": 95.5,
            "rank": 2
        }
    ]
    """

    if not PLAYER_POOL_PATH.exists():
        raise FileNotFoundError(
            f"player_pool.json을 찾을 수 없습니다.\n"
            f"경로: {PLAYER_POOL_PATH}"
        )

    with open(
        PLAYER_POOL_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "player_pool.json 최상위 구조는 [] 배열이어야 합니다."
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
        except (TypeError, ValueError):
            overall = 0.0

        try:
            rank = int(
                raw.get("rank", 9999)
            )
        except (TypeError, ValueError):
            rank = 9999

        if not name:
            continue

        if position not in VALID_POSITIONS:
            print(
                "[AUCTION] 알 수 없는 포지션:",
                name,
                position,
            )
            continue

        players.append(
            {
                "id": index,
                "name": name,
                "team": team,
                "position": position,
                "overall": overall,
                "rank": rank,
            }
        )

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
# 가격 계산
# =========================================================

def starting_price(player):
    """
    overall에 따라 시작가를 결정한다.

    너무 높은 가격으로 시작하지 않도록 제한.
    """

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
        return 5

    if current_price < 100:
        return 10

    if current_price < 200:
        return 20

    return 30


# =========================================================
# 로스터
# =========================================================

def roster_count(roster, position):
    return sum(
        1
        for player in roster
        if player.get("position") == position
    )


def can_add_player(roster, player):
    position = player.get("position")

    limit = ROSTER_LIMITS.get(
        position,
        0,
    )

    return roster_count(
        roster,
        position,
    ) < limit


def roster_full(roster):
    return len(roster) >= TOTAL_ROSTER_SIZE


def roster_complete(roster):
    if len(roster) != TOTAL_ROSTER_SIZE:
        return False

    for position, limit in ROSTER_LIMITS.items():

        if roster_count(
            roster,
            position,
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


def ai_can_bid(ai, player):
    if ai["budget"] <= 0:
        return False

    return can_add_player(
        ai["roster"],
        player,
    )


def ai_max_price(ai, player):
    """
    AI가 이 선수에게 쓸 수 있는 최대 금액.

    좋은 선수일수록 적극적으로 입찰한다.
    """

    overall = float(
        player.get("overall", 70)
    )

    # 기본 평가
    value = overall * 2.0

    # 선수별 성향 차이
    personality_bonus = {
        "승부사": 1.15,
        "스카우터": 0.95,
        "단장님": 1.05,
        "야구광": 1.10,
    }.get(
        ai["name"],
        1.0,
    )

    value *= personality_bonus

    # 남은 예산 보호
    budget_limit = ai["budget"] * 0.65

    return min(
        value,
        budget_limit,
    )


def ai_should_bid(ai, player, current_price):
    if not ai_can_bid(
        ai,
        player,
    ):
        return False

    max_price = ai_max_price(
        ai,
        player,
    )

    next_price = (
        current_price
        + bid_increment(current_price)
    )

    if next_price > max_price:
        return False

    overall = float(
        player.get("overall", 70)
    )

    # 기본 입찰 확률
    probability = 0.25

    if overall >= 90:
        probability = 0.80
    elif overall >= 85:
        probability = 0.60
    elif overall >= 80:
        probability = 0.45

    # 현재 가격이 너무 높으면 확률 감소
    if current_price > max_price * 0.7:
        probability *= 0.55

    # 랜덤성
    return random.random() < probability


def choose_ai_bidder(game):
    """
    현재 선수에 대해 입찰할 AI를 찾는다.
    """

    player = game["current_player"]

    candidates = []

    for ai in game["ais"]:

        if not ai_can_bid(
            ai,
            player,
        ):
            continue

        if not ai_should_bid(
            ai,
            player,
            game["current_price"],
        ):
            continue

        candidates.append(ai)

    if not candidates:
        return None

    # 가장 높은 평가를 하는 AI를 우선
    candidates.sort(
        key=lambda x: ai_max_price(
            x,
            player,
        ),
        reverse=True,
    )

    # 항상 같은 AI만 이기는 것을 방지
    if len(candidates) >= 2:
        if random.random() < 0.35:
            return random.choice(
                candidates[:2]
            )

    return candidates[0]


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

        "finished": False,

        "result": None,

        "bid_history": [],

        "logs": [],
    }

    return game


# =========================================================
# 다음 선수
# =========================================================

def available_players(game):
    used = set(
        game.get(
            "used_player_ids",
            [],
        )
    )

    return [
        player
        for player in game["players"]
        if player["id"] not in used
    ]


def choose_next_player(game):
    available = available_players(game)

    if not available:
        return None

    # 현재 로스터에서 부족한 포지션을 우선
    needed_positions = []

    for position, limit in ROSTER_LIMITS.items():

        current = roster_count(
            game["roster"],
            position,
        )

        remaining = limit - current

        if remaining > 0:
            needed_positions.append(
                position
            )

    # AI 로스터도 고려할 필요가 있으므로
    # 완전히 한 포지션만 고정하지 않고 가중치 방식
    candidates = [
        player
        for player in available
        if player["position"]
        in needed_positions
    ]

    if not candidates:
        candidates = available

    # 상위 선수만 계속 나오지 않게 랜덤
    candidates.sort(
        key=lambda p: p["overall"],
        reverse=True,
    )

    top_count = min(
        len(candidates),
        40,
    )

    return random.choice(
        candidates[:top_count]
    )


def start_round(game):
    if game["finished"]:
        return False

    if roster_full(
        game["roster"]
    ):
        finish_game(game)
        return False

    player = choose_next_player(game)

    if player is None:
        finish_game(game)
        return False

    game["round"] += 1

    game["current_player"] = player

    game["used_player_ids"].append(
        player["id"]
    )

    game["current_price"] = starting_price(
        player
    )

    game["highest_bidder"] = None

    game["started_at"] = time.time()

    game["last_bid_at"] = None

    game["bid_history"] = []

    add_log(
        game,
        f"🔔 {player['name']} "
        f"({player['team']}) "
        f"경매 시작! "
        f"시작가 {game['current_price']}억",
    )

    return True


# =========================================================
# 로그
# =========================================================

def add_log(game, message):
    game.setdefault(
        "logs",
        [],
    )

    game["logs"].append(
        {
            "time": time.strftime(
                "%H:%M:%S"
            ),
            "message": message,
        }
    )

    # 너무 길어지지 않게
    if len(game["logs"]) > 100:
        game["logs"] = game["logs"][-100:]


# =========================================================
# 사용자 입찰
# =========================================================

def user_bid(game):
    if game["finished"]:
        return False, "게임이 종료되었습니다."

    player = game.get(
        "current_player"
    )

    if not player:
        return False, "현재 경매 선수가 없습니다."

    # 제한시간 확인
    if auction_expired(game):
        settle_auction(game)
        return False, "입찰 시간이 종료되었습니다."

    if not can_add_player(
        game["roster"],
        player,
    ):
        return (
            False,
            f"{player['position']} 포지션은 "
            f"이미 정원을 채웠습니다.",
        )

    next_price = (
        game["current_price"]
        + bid_increment(
            game["current_price"]
        )
    )

    if next_price > game["budget"]:
        return (
            False,
            "예산이 부족합니다.",
        )

    game["current_price"] = next_price

    game["highest_bidder"] = "user"

    game["last_bid_at"] = time.time()

    game["bid_history"].append(
        {
            "bidder": "나",
            "price": next_price,
            "time": time.strftime(
                "%H:%M:%S"
            ),
        }
    )

    add_log(
        game,
        f"🧑 나 → "
        f"{player['name']} "
        f"{next_price}억 입찰",
    )

    return True, "입찰 성공"


# =========================================================
# AI 턴
# =========================================================

def run_ai_turn(game):
    if game["finished"]:
        return

    player = game.get(
        "current_player"
    )

    if not player:
        return

    # 여러 AI가 연속으로 경쟁할 수 있게
    for _ in range(3):

        ai = choose_ai_bidder(game)

        if ai is None:
            break

        next_price = (
            game["current_price"]
            + bid_increment(
                game["current_price"]
            )
        )

        if next_price > ai["budget"]:
            continue

        if not can_add_player(
            ai["roster"],
            player,
        ):
            continue

        game["current_price"] = next_price

        game["highest_bidder"] = ai["id"]

        game["last_bid_at"] = time.time()

        ai["bids"] += 1

        game["bid_history"].append(
            {
                "bidder": ai["name"],
                "price": next_price,
                "time": time.strftime(
                    "%H:%M:%S"
                ),
            }
        )

        add_log(
            game,
            f"🤖 {ai['name']} → "
            f"{player['name']} "
            f"{next_price}억 입찰",
        )

        # AI끼리 계속 싸우게 약간의 확률
        if random.random() < 0.35:
            continue

        break


# =========================================================
# 제한 시간
# =========================================================

def auction_expired(game):
    started = game.get(
        "started_at"
    )

    if not started:
        return False

    return (
        time.time() - started
        >= AUCTION_TIME
    )


def remaining_time(game):
    started = game.get(
        "started_at"
    )

    if not started:
        return AUCTION_TIME

    remain = (
        AUCTION_TIME
        - (
            time.time()
            - started
        )
    )

    return max(
        0,
        int(remain + 0.999),
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
        0,
    )

    # 아무도 입찰하지 않은 경우
    if not winner:

        add_log(
            game,
            f"⚪ {player['name']} "
            f"무입찰 유찰",
        )

        game["current_player"] = None

        if game["round"] >= game["total_rounds"]:
            finish_game(game)
        else:
            start_round(game)

        return

    # 사용자 낙찰
    if winner == "user":

        if price > game["budget"]:
            add_log(
                game,
                "❌ 예산 부족으로 낙찰 취소",
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
                f"{price}억 낙찰!",
            )

    # AI 낙찰
    else:

        ai = next(
            (
                a
                for a in game["ais"]
                if a["id"] == winner
            ),
            None,
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
                    f"{price}억 낙찰!",
                )

    game["current_player"] = None

    game["highest_bidder"] = None

    game["current_price"] = 0

    # 사용자 로스터 완성
    if roster_complete(
        game["roster"]
    ):
        finish_game(game)
        return

    if game["round"] >= game["total_rounds"]:
        finish_game(game)
        return

    start_round(game)


# =========================================================
# 게임 종료
# =========================================================

def calculate_team_score(roster):
    if not roster:
        return 0

    overall_total = sum(
        float(
            player.get(
                "overall",
                0,
            )
        )
        for player in roster
    )

    average = (
        overall_total
        / len(roster)
    )

    # 포지션 충족 보너스
    position_bonus = 0

    for position, limit in ROSTER_LIMITS.items():

        count = roster_count(
            roster,
            position,
        )

        if count >= limit:
            position_bonus += 3

    return round(
        average
        + position_bonus,
        2,
    )


def calculate_grade(score, rank):
    """
    경쟁 순위 기반 등급.
    """

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


def finish_game(game):
    if game["finished"]:
        return

    game["finished"] = True

    user_score = calculate_team_score(
        game["roster"]
    )

    competitors = []

    competitors.append(
        {
            "id": "user",
            "name": "나",
            "score": user_score,
            "roster": list(
                game["roster"]
            ),
        }
    )

    for ai in game["ais"]:

        score = calculate_team_score(
            ai["roster"]
        )

        competitors.append(
            {
                "id": ai["id"],
                "name": ai["name"],
                "score": score,
                "roster": list(
                    ai["roster"]
                ),
            }
        )

    competitors.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    for index, competitor in enumerate(
        competitors,
        start=1,
    ):
        competitor["rank"] = index

        competitor["grade"] = calculate_grade(
            competitor["score"],
            index,
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
        f"내 순위 {user_result['rank']}위 / "
        f"{user_result['grade']}등급",
    )


# =========================================================
# 게임 진행
# =========================================================

def process_game(game):
    """
    GET /auction/<id>가 들어올 때마다 호출.

    자동 새로고침을 하지 않는다.
    브라우저에서 요청이 들어왔을 때만 진행된다.
    """

    if game["finished"]:
        return

    if not game.get(
        "current_player"
    ):
        start_round(game)
        return

    # AI 입찰
    run_ai_turn(game)

    # 제한시간 종료
    if auction_expired(game):
        settle_auction(game)


# =========================================================
# 상태 표시용
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
        "current_price": game["current_price"],
        "highest_bidder": game["highest_bidder"],
        "remaining_time": remaining_time(game),
        "auction_time": AUCTION_TIME,
        "finished": game["finished"],
        "result": game["result"],
        "bid_history": game["bid_history"],
        "logs": game["logs"],
    }
