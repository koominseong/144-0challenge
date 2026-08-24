# ============================================================
# Draft Mode
# draft_routes.py
#
# 중요
# ------------------------------------------------------------
# 1. Flask session을 사용하지 않는다.
# 2. Player_pool.json은 절대 수정하지 않는다.
# 3. 게임 상태는 서버 메모리에서 관리한다.
#
# 선수 포지션
# ------------------------------------------------------------
# 선발 / 불펜 / 마무리 -> 투수
# 투수                 -> 투수
# 내야 / 내야수        -> 내야수
# 외야 / 외야수        -> 외야수
# 포수                 -> 포수
#
# 경매
# ------------------------------------------------------------
# - 1 vs 1
# - 설정 인원 x 2명 선수풀
# - 선수 순서는 랜덤
# - 다음 선수는 공개하지 않음
# - 처음에는 누구든 먼저 행동 가능
# - 먼저 제시한 사람이 선공
# - 이후에는 서로 번갈아 행동
# - 원하는 금액 직접 입력
# - ALL-IN = 즉시 낙찰이 아니라 전액 제시
# - 상대방이 다시 입찰 가능
# - PASS로 경매 종료
# - 처음부터 둘 다 PASS하면 선수풀 맨 뒤
# - 실제 낙찰 시에만 돈 차감
# ============================================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
)

import os
import json
import uuid
import random
import threading


# ============================================================
# Blueprint
# ============================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 포지션
# ============================================================

POSITION_KEYS = [
    "투수",
    "내야수",
    "외야수",
    "포수",
]


SOURCE_POSITION = {

    # 투수
    "선발": "투수",
    "불펜": "투수",
    "마무리": "투수",
    "투수": "투수",

    # 내야
    "내야": "내야수",
    "내야수": "내야수",

    # 외야
    "외야": "외야수",
    "외야수": "외야수",

    # 포수
    "포수": "포수",
}


# ============================================================
# 서버 메모리
#
# Render에서 gunicorn worker가 여러 개라면
# worker마다 별도 메모리를 사용한다.
#
# 따라서 가능하면 Render에서
# worker 1개로 실행하는 것을 권장한다.
# ============================================================

GAMES = {}

GAMES_LOCK = threading.RLock()


# ============================================================
# Player_pool.json 찾기
# ============================================================

def _find_player_pool():

    base = os.path.dirname(
        os.path.abspath(__file__)
    )

    candidates = [

        os.path.join(
            base,
            "Player_pool.json"
        ),

        os.path.join(
            base,
            "player_pool.json"
        ),

        os.path.join(
            base,
            "Player_pool.json.txt"
        ),

        os.path.join(
            base,
            "player_pool.json.txt"
        ),

    ]

    for path in candidates:

        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Player_pool.json 파일을 찾을 수 없습니다."
    )


# ============================================================
# 선수풀 로드
# ============================================================

def load_players():

    path = _find_player_pool()

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if not isinstance(data, list):

        raise ValueError(
            "Player_pool.json의 최상위 구조는 list여야 합니다."
        )

    players = []

    for index, raw in enumerate(data):

        if not isinstance(raw, dict):
            continue

        source_position = str(
            raw.get(
                "position",
                ""
            )
        ).strip()

        group = SOURCE_POSITION.get(
            source_position
        )

        if group is None:
            continue

        name = str(
            raw.get(
                "name",
                ""
            )
        ).strip()

        if not name:
            continue

        try:

            overall = float(
                raw.get(
                    "overall",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            overall = 0

        player = {

            "pool_id": index,

            "name": name,

            "position": source_position,

            "group": group,

            "team": str(
                raw.get(
                    "team",
                    ""
                )
            ).strip(),

            "overall": overall,

            "rank": raw.get(
                "rank",
                999
            ),

        }

        players.append(player)

    return players


# ============================================================
# 선수풀 포지션별 숫자
# ============================================================

def available_counts(players):

    counts = {

        "투수": 0,

        "내야수": 0,

        "외야수": 0,

        "포수": 0,

    }

    for player in players:

        group = player.get(
            "group"
        )

        if group in counts:

            counts[group] += 1

    return counts


# ============================================================
# 선수풀 생성
# ============================================================

def make_player_pool(limits):

    players = load_players()

    counts = available_counts(
        players
    )

    required = {

        key: int(limits[key]) * 2

        for key in POSITION_KEYS

    }

    for key in POSITION_KEYS:

        need = required[key]

        if need <= 0:
            continue

        have = counts.get(
            key,
            0
        )

        if have < need:

            raise ValueError(

                f"{key} 선수 풀이 부족합니다. "

                f"필요 {need}명 / "

                f"보유 {have}명"

            )

    selected = []

    for key in POSITION_KEYS:

        need = required[key]

        if need <= 0:
            continue

        candidates = [

            player.copy()

            for player in players

            if player["group"] == key

        ]

        chosen = random.sample(
            candidates,
            need
        )

        selected.extend(
            chosen
        )

    random.shuffle(
        selected
    )

    return selected


# ============================================================
# State 생성
# ============================================================

def new_state(
    player_pool,
    initial_money,
    limits,
    player_a,
    player_b,
):

    limits = {

        key: int(
            limits.get(
                key,
                0
            )
        )

        for key in POSITION_KEYS

    }

    return {

        "players": {

            "a": player_a,

            "b": player_b,

        },

        "money": {

            "a": int(initial_money),

            "b": int(initial_money),

        },

        "spent": {

            "a": 0,

            "b": 0,

        },

        "rosters": {

            "a": [],

            "b": [],

        },

        "roster_size": sum(
            limits.values()
        ),

        "limits": limits,

        # 아직 화면에 공개되지 않은 선수
        "pool": player_pool,

        # 현재 경매 선수
        "current": None,

        # 현재 최고 제시 금액
        "current_bid": 0,

        # 현재 선두
        "leader": None,

        # 현재 차례
        #
        # None:
        #   첫 행동 전
        #
        # "a" / "b":
        #   해당 플레이어 차례
        #
        "turn": None,

        # 경매가 시작됐는가
        "auction_started": False,

        # 첫 경매에서 PASS 기록
        "passed": {

            "a": False,

            "b": False,

        },

        "log": [],

        "done": False,

        "winner": None,

        "score": {

            "a": 0,

            "b": 0,

        },

    }


# ============================================================
# 게임 저장
# ============================================================

def save_game(
    game_id,
    state
):

    with GAMES_LOCK:

        GAMES[game_id] = state


# ============================================================
# 게임 가져오기
# ============================================================

def get_game(
    game_id
):

    with GAMES_LOCK:

        return GAMES.get(
            game_id
        )


# ============================================================
# 게임 삭제
# ============================================================

def delete_game(
    game_id
):

    with GAMES_LOCK:

        GAMES.pop(
            game_id,
            None
        )


# ============================================================
# 포지션별 로스터 숫자
# ============================================================

def roster_count(
    state,
    side,
    group
):

    return sum(

        1

        for player in state[
            "rosters"
        ][side]

        if player.get(
            "group"
        ) == group

    )


# ============================================================
# 전체 로스터 완성
# ============================================================

def roster_full(
    state,
    side
):

    return (

        len(
            state["rosters"][side]
        )

        >=

        state["roster_size"]

    )


# ============================================================
# 포지션 정원
# ============================================================

def group_full(
    state,
    side,
    group
):

    limit = state[
        "limits"
    ].get(
        group,
        0
    )

    return (

        roster_count(
            state,
            side,
            group
        )

        >= limit

    )


# ============================================================
# 상대방
# ============================================================

def other_side(
    side
):

    return (
        "b"
        if side == "a"
        else "a"
    )


# ============================================================
# 현재 선수 선택
# ============================================================

def next_player(
    state
):

    # 자동 배정을 먼저 수행
    assign_forced_players(
        state
    )

    # 이미 양쪽이 완성됐으면 종료
    if (

        roster_full(
            state,
            "a"
        )

        and

        roster_full(
            state,
            "b"
        )

    ):

        finish_game(
            state
        )

        return

    # 선수풀이 없으면 종료
    if not state["pool"]:

        finish_game(
            state
        )

        return

    # ========================================================
    # 다음 선수
    # ========================================================

    player = state[
        "pool"
    ].pop(0)

    state["current"] = player

    state["current_bid"] = 0

    state["leader"] = None

    # 첫 행동은 누구든 가능
    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,

    }


# ============================================================
# 강제 자동 배정
# ============================================================

def assign_forced_players(
    state
):

    changed = True

    while changed:

        changed = False

        for player in list(
            state["pool"]
        ):

            group = player[
                "group"
            ]

            a_full = group_full(
                state,
                "a",
                group
            )

            b_full = group_full(
                state,
                "b",
                group
            )

            # A가 해당 포지션 완성
            # -> 남은 선수는 B
            if (

                a_full

                and

                not b_full

            ):

                state["pool"].remove(
                    player
                )

                state[
                    "rosters"
                ]["b"].append(
                    player
                )

                state["log"].append(

                    f"자동 배정: "

                    f"{player['name']} → "

                    f"{state['players']['b']}"

                )

                changed = True

                break

            # B가 해당 포지션 완성
            # -> 남은 선수는 A
            if (

                b_full

                and

                not a_full

            ):

                state["pool"].remove(
                    player
                )

                state[
                    "rosters"
                ]["a"].append(
                    player
                )

                state["log"].append(

                    f"자동 배정: "

                    f"{player['name']} → "

                    f"{state['players']['a']}"

                )

                changed = True

                break


# ============================================================
# 게임 종료
# ============================================================

def finish_game(
    state
):

    # --------------------------------------------------------
    # 남은 선수가 있다면 필요한 쪽으로 배정
    # --------------------------------------------------------

    while state["pool"]:

        player = state[
            "pool"
        ].pop(0)

        group = player[
            "group"
        ]

        if (

            not group_full(
                state,
                "a",
                group
            )

            and

            not roster_full(
                state,
                "a"
            )

        ):

            state[
                "rosters"
            ]["a"].append(
                player
            )

            continue

        if (

            not group_full(
                state,
                "b",
                group
            )

            and

            not roster_full(
                state,
                "b"
            )

        ):

            state[
                "rosters"
            ]["b"].append(
                player
            )

            continue

    # --------------------------------------------------------
    # 점수
    # --------------------------------------------------------

    score_a = sum(

        float(
            player.get(
                "overall",
                0
            )
        )

        for player
        in state[
            "rosters"
        ]["a"]

    )

    score_b = sum(

        float(
            player.get(
                "overall",
                0
            )
        )

        for player
        in state[
            "rosters"
        ]["b"]

    )

    score_a = round(
        score_a,
        1
    )

    score_b = round(
        score_b,
        1
    )

    if score_a > score_b:

        winner = "a"

    elif score_b > score_a:

        winner = "b"

    else:

        winner = "draw"

    state["score"] = {

        "a": score_a,

        "b": score_b,

    }

    state["winner"] = winner

    state["done"] = True

    state["current"] = None

    state["current_bid"] = 0

    state["leader"] = None

    state["turn"] = None


# ============================================================
# 선수 낙찰
# ============================================================

def award_player(
    state,
    side,
    price
):

    player = state[
        "current"
    ]

    if player is None:

        raise ValueError(
            "현재 경매 선수가 없습니다."
        )

    price = int(price)

    if price < 0:

        raise ValueError(
            "잘못된 금액입니다."
        )

    if price > state[
        "money"
    ][side]:

        raise ValueError(
            "낙찰 금액이 보유 자금보다 많습니다."
        )

    group = player[
        "group"
    ]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # --------------------------------------------------------
    # 실제 낙찰 시에만 돈 차감
    # --------------------------------------------------------

    state[
        "money"
    ][side] -= price

    state[
        "spent"
    ][side] += price

    state[
        "rosters"
    ][side].append(
        player
    )

    state["log"].append(

        f"{state['players'][side]} → "

        f"{player['name']} "

        f"(${price})"

    )

    # --------------------------------------------------------
    # 현재 경매 초기화
    # --------------------------------------------------------

    state["current"] = None

    state["current_bid"] = 0

    state["leader"] = None

    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,

    }

    # --------------------------------------------------------
    # 포지션 강제 배정
    # --------------------------------------------------------

    assign_forced_players(
        state
    )

    # --------------------------------------------------------
    # 게임 종료 여부
    # --------------------------------------------------------

    if (

        roster_full(
            state,
            "a"
        )

        and

        roster_full(
            state,
            "b"
        )

    ):

        finish_game(
            state
        )

        return

    # --------------------------------------------------------
    # 다음 선수
    # --------------------------------------------------------

    next_player(
        state
    )


# ============================================================
# 첫 제시
# ============================================================

def start_bid(
    state,
    side,
    amount
):

    if state["current"] is None:

        raise ValueError(
            "현재 경매 선수가 없습니다."
        )

    amount = int(amount)

    if amount <= 0:

        raise ValueError(
            "입찰 금액은 1달러 이상이어야 합니다."
        )

    if amount > state[
        "money"
    ][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # --------------------------------------------------------
    # 첫 제시
    # --------------------------------------------------------

    state["current_bid"] = amount

    state["leader"] = side

    state["turn"] = other_side(
        side
    )

    state["auction_started"] = True

    state["passed"] = {

        "a": False,

        "b": False,

    }

    state["log"].append(

        f"{state['players'][side]} "

        f"선공 입찰 ${amount}"

    )


# ============================================================
# 일반 입찰
# ============================================================

def normal_bid(
    state,
    side,
    amount
):

    if state["current"] is None:

        raise ValueError(
            "현재 경매 선수가 없습니다."
        )

    amount = int(amount)

    if amount <= state[
        "current_bid"
    ]:

        raise ValueError(

            "현재가보다 높은 금액을 입력하세요."

        )

    if amount > state[
        "money"
    ][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    state["current_bid"] = amount

    state["leader"] = side

    state["turn"] = other_side(
        side
    )

    state["auction_started"] = True

    state["passed"][side] = False

    state["log"].append(

        f"{state['players'][side]} "

        f"→ ${amount}"

    )


# ============================================================
# ALL-IN
# ============================================================

def all_in(
    state,
    side
):

    if state["current"] is None:

        raise ValueError(
            "현재 경매 선수가 없습니다."
        )

    money = int(
        state["money"][side]
    )

    if money <= 0:

        raise ValueError(
            "사용 가능한 자금이 없습니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    amount = money

    # --------------------------------------------------------
    # 첫 ALL-IN
    # --------------------------------------------------------

    if not state[
        "auction_started"
    ]:

        state["current_bid"] = amount

        state["leader"] = side

        state["auction_started"] = True

        state["turn"] = other_side(
            side
        )

        state["passed"] = {

            "a": False,

            "b": False,

        }

        state["log"].append(

            f"{state['players'][side]} "

            f"ALL-IN ${amount}"

        )

        return

    # --------------------------------------------------------
    # 기존 현재가보다 높아야 함
    # --------------------------------------------------------

    if amount <= state[
        "current_bid"
    ]:

        raise ValueError(

            "현재가보다 높은 금액을 "
            "제시할 수 있어야 ALL-IN할 수 있습니다."

        )

    state["current_bid"] = amount

    state["leader"] = side

    state["turn"] = other_side(
        side
    )

    state["passed"][side] = False

    state["log"].append(

        f"{state['players'][side]} "

        f"ALL-IN ${amount}"

    )


# ============================================================
# PASS
# ============================================================

def pass_action(
    state,
    side
):

    if state["current"] is None:

        return

    other = other_side(
        side
    )

    # ========================================================
    # 아무도 입찰하지 않은 상태
    # ========================================================

    if not state[
        "auction_started"
    ]:

        state[
            "passed"
        ][side] = True

        state["log"].append(

            f"{state['players'][side]} PASS"

        )

        # ----------------------------------------------------
        # 둘 다 PASS
        # ----------------------------------------------------

        if state[
            "passed"
        ][other]:

            player = state[
                "current"
            ]

            state[
                "pool"
            ].append(
                player
            )

            state["log"].append(

                f"{player['name']} "

                f"→ 선수풀 맨 뒤"

            )

            state["current"] = None

            state["current_bid"] = 0

            state["leader"] = None

            state["turn"] = None

            state["auction_started"] = False

            state["passed"] = {

                "a": False,

                "b": False,

            }

            next_player(
                state
            )

        else:

            # 상대에게 기회
            state["turn"] = other

        return

    # ========================================================
    # 경매가 시작된 상태
    # ========================================================

    # 선두가 PASS
    if state[
        "leader"
    ] == side:

        state["log"].append(

            f"{state['players'][side]} PASS"

        )

        # 상대방이 현재 금액으로 낙찰
        award_player(

            state,

            other,

            state["current_bid"]

        )

        return

    # ========================================================
    # 선두가 아닌 사람이 PASS
    # ========================================================

    state["log"].append(

        f"{state['players'][side]} PASS"

    )

    award_player(

        state,

        state["leader"],

        state["current_bid"]

    )


# ============================================================
# 시작 화면
# ============================================================

@draft_bp.route(
    "",
    methods=["GET"]
)
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# ============================================================
# 게임 시작
# ============================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    try:

        # ----------------------------------------------------
        # 초기 자본
        # ----------------------------------------------------

        initial_money = int(

            request.form.get(
                "initial_money",
                "20"
            )

        )

        if initial_money <= 0:

            raise ValueError(
                "초기 자본은 1달러 이상이어야 합니다."
            )

        # ----------------------------------------------------
        # 포지션별 인원
        # ----------------------------------------------------

        limits = {

            "투수": int(

                request.form.get(
                    "pitchers",
                    "2"
                )

            ),

            "내야수": int(

                request.form.get(
                    "infielders",
                    "2"
                )

            ),

            "외야수": int(

                request.form.get(
                    "outfielders",
                    "2"
                )

            ),

            "포수": int(

                request.form.get(
                    "catchers",
                    "1"
                )

            ),

        }

        for key in POSITION_KEYS:

            if limits[key] < 0:

                raise ValueError(

                    f"{key} 인원은 "
                    f"0 이상이어야 합니다."

                )

        roster_size = sum(
            limits.values()
        )

        if roster_size <= 0:

            raise ValueError(
                "최소 1명 이상의 선수를 설정하세요."
            )

        # ----------------------------------------------------
        # 선수풀 생성
        # ----------------------------------------------------

        player_pool = make_player_pool(
            limits
        )

        # ----------------------------------------------------
        # 플레이어 이름
        # ----------------------------------------------------

        player_a = (

            request.form.get(
                "player_a",
                "PLAYER 1"
            ).strip()

            or

            "PLAYER 1"

        )

        player_b = (

            request.form.get(
                "player_b",
                "PLAYER 2"
            ).strip()

            or

            "PLAYER 2"

        )

        # ----------------------------------------------------
        # State
        # ----------------------------------------------------

        state = new_state(

            player_pool,

            initial_money,

            limits,

            player_a,

            player_b,

        )

        # ----------------------------------------------------
        # 첫 선수
        # ----------------------------------------------------

        next_player(
            state
        )

        # ----------------------------------------------------
        # 게임 ID
        # ----------------------------------------------------

        game_id = uuid.uuid4().hex

        save_game(
            game_id,
            state
        )

        return redirect(

            url_for(

                "draft.game",

                game_id=game_id

            )

        )

    except Exception as e:

        return render_template(

            "draft_setup.html",

            error=str(e)

        )


# ============================================================
# 게임 화면
# ============================================================

@draft_bp.route(
    "/game/<game_id>",
    methods=["GET"]
)
def game(
    game_id
):

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(

            url_for(
                "draft.draft_home"
            )

        )

    if state.get(
        "done"
    ):

        return redirect(

            url_for(

                "draft.result",

                game_id=game_id

            )

        )

    return render_template(

        "draft_game.html",

        state=state,

        game_id=game_id,

        error=None,

    )


# ============================================================
# 경매 액션
# ============================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(
    game_id
):

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(

            url_for(
                "draft.draft_home"
            )

        )

    if state.get(
        "done"
    ):

        return redirect(

            url_for(

                "draft.result",

                game_id=game_id

            )

        )

    error = None

    try:

        side = request.form.get(
            "side",
            ""
        ).strip()

        action_type = request.form.get(
            "action",
            ""
        ).strip()

        # ----------------------------------------------------
        # 플레이어 확인
        # ----------------------------------------------------

        if side not in (
            "a",
            "b"
        ):

            raise ValueError(
                "잘못된 플레이어입니다."
            )

        # ----------------------------------------------------
        # 현재 차례 확인
        #
        # turn == None:
        #   첫 행동
        #
        # turn != None:
        #   해당 플레이어만 행동 가능
        # ----------------------------------------------------

        if state["turn"] is not None:

            if state["turn"] != side:

                raise ValueError(
                    "현재는 상대방의 차례입니다."
                )

        # ----------------------------------------------------
        # BID
        # ----------------------------------------------------

        if action_type == "bid":

            raw_amount = request.form.get(
                "amount",
                ""
            ).strip()

            if not raw_amount:

                raise ValueError(
                    "제시 금액을 입력하세요."
                )

            try:

                amount = int(
                    raw_amount
                )

            except ValueError:

                raise ValueError(
                    "제시 금액은 숫자로 입력하세요."
                )

            if state[
                "auction_started"
            ]:

                normal_bid(

                    state,

                    side,

                    amount

                )

            else:

                start_bid(

                    state,

                    side,

                    amount

                )

        # ----------------------------------------------------
        # ALL-IN
        # ----------------------------------------------------

        elif action_type == "allin":

            all_in(

                state,

                side

            )

        # ----------------------------------------------------
        # PASS
        # ----------------------------------------------------

        elif action_type == "pass":

            pass_action(

                state,

                side

            )

        else:

            raise ValueError(
                "알 수 없는 액션입니다."
            )

        # ----------------------------------------------------
        # 저장
        # ----------------------------------------------------

        save_game(
            game_id,
            state
        )

        # ----------------------------------------------------
        # 종료
        # ----------------------------------------------------

        if state.get(
            "done"
        ):

            return redirect(

                url_for(

                    "draft.result",

                    game_id=game_id

                )

            )

        return redirect(

            url_for(

                "draft.game",

                game_id=game_id

            )

        )

    except Exception as e:

        error = str(e)

        save_game(
            game_id,
            state
        )

        return render_template(

            "draft_game.html",

            state=state,

            game_id=game_id,

            error=error,

        )


# ============================================================
# 결과
# ============================================================

@draft_bp.route(
    "/game/<game_id>/result",
    methods=["GET"]
)
def result(
    game_id
):

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(

            url_for(
                "draft.draft_home"
            )

        )

    # --------------------------------------------------------
    # 혹시 이전 state에 결과가 없는 경우
    # --------------------------------------------------------

    if "score" not in state:

        score_a = sum(

            float(
                player.get(
                    "overall",
                    0
                )
            )

            for player
            in state[
                "rosters"
            ]["a"]

        )

        score_b = sum(

            float(
                player.get(
                    "overall",
                    0
                )
            )

            for player
            in state[
                "rosters"
            ]["b"]

        )

        if score_a > score_b:

            winner = "a"

        elif score_b > score_a:

            winner = "b"

        else:

            winner = "draw"

        state["score"] = {

            "a": round(
                score_a,
                1
            ),

            "b": round(
                score_b,
                1
            ),

        }

        state["winner"] = winner

        state["done"] = True

        save_game(
            game_id,
            state
        )

    return render_template(

        "draft_result.html",

        state=state,

        game_id=game_id,

    )


# ============================================================
# 게임 삭제 / 새 게임
# ============================================================

@draft_bp.route(
    "/reset/<game_id>",
    methods=["GET"]
)
def reset(
    game_id
):

    delete_game(
        game_id
    )

    return redirect(

        url_for(
            "draft.draft_home"
        )

    )
