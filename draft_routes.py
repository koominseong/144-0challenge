# ============================================================
# Draft Mode
# draft_routes.py
#
# Player_pool.json은 절대 수정하지 않는다.
#
# 선수 포지션:
#   선발 / 불펜 / 마무리 -> 투수
#   투수 -> 투수
#   내야 / 내야수 -> 내야수
#   외야 / 외야수 -> 외야수
#   포수 -> 포수
#
# 게임 방식:
#   1vs1 경매
#   선수풀은 설정한 인원 × 2
#   경매 선수 순서는 랜덤
#   다음 선수는 공개하지 않음
#
#   첫 행동:
#       Player 1 / Player 2 누구든 먼저 가능
#
#   첫 행동 이후:
#       서로 번갈아 행동
#
#   금액:
#       +1 고정이 아니라 원하는 금액 직접 입력
#
#   ALL-IN:
#       보유 자금 전액
#       같은 금액이라도 ALL-IN이 우선
#
#   PASS:
#       첫 입찰 전 둘 다 PASS -> 선수풀 맨 뒤
#       경매 중 PASS -> 상대방 낙찰
#
# ============================================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)

import os
import json
import uuid
import random


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

        if os.path.exists(path):

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
            "Player_pool.json의 최상위 구조가 list가 아닙니다."
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

        if not group:
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

        except Exception:

            overall = 0

        player = {

            "pool_id": index,

            "name": name,

            "position": source_position,

            "group": group,

            "rank": raw.get(
                "rank",
                999
            ),

            "team": raw.get(
                "team",
                ""
            ),

            "overall": overall,

        }

        players.append(
            player
        )

    return players


# ============================================================
# 선수풀 개수
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

def make_player_pool(
    limits
):

    players = load_players()

    counts = available_counts(
        players
    )

    required = {

        key:
            int(limits[key]) * 2

        for key in POSITION_KEYS

    }

    # --------------------------------------------------------
    # 선수풀 충분한지 검사
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 포지션별 정확히 2배 추출
    # --------------------------------------------------------

    selected = []

    for key in POSITION_KEYS:

        need = required[key]

        if need <= 0:
            continue

        candidates = [

            p.copy()

            for p in players

            if p["group"] == key

        ]

        chosen = random.sample(
            candidates,
            need
        )

        selected.extend(
            chosen
        )

    # --------------------------------------------------------
    # 전체 경매 순서 랜덤
    # --------------------------------------------------------

    random.shuffle(
        selected
    )

    return selected


# ============================================================
# 새로운 State
# ============================================================

def new_state(
    player_pool,
    initial_money,
    limits
):

    return {

        "players": {

            "a": "PLAYER 1",

            "b": "PLAYER 2",

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

        "roster_size":
            sum(
                int(limits[key])
                for key in POSITION_KEYS
            ),

        "limits": {

            key: int(
                limits[key]
            )

            for key in POSITION_KEYS

        },

        "pool": player_pool,

        "current": None,

        "current_bid": 0,

        # 현재 최고 입찰자
        "leader": None,

        # 첫 입찰 전에는 None
        # 첫 입찰 후에는 반드시 한 명
        "turn": None,

        "auction_started": False,

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
# Session
# ============================================================

def save_state(
    game_id,
    state
):

    session[
        f"draft_game_{game_id}"
    ] = state

    session.modified = True


def get_state(
    game_id
):

    return session.get(
        f"draft_game_{game_id}"
    )


def delete_state(
    game_id
):

    session.pop(
        f"draft_game_{game_id}",
        None
    )

    session.modified = True


# ============================================================
# 로스터 검사
# ============================================================

def roster_count(
    state,
    side,
    group
):

    return sum(

        1

        for player
        in state["rosters"][side]

        if player.get(
            "group"
        ) == group

    )


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


def group_full(
    state,
    side,
    group
):

    return (

        roster_count(
            state,
            side,
            group
        )

        >=

        state["limits"].get(
            group,
            0
        )

    )


# ============================================================
# 포지션 자동 배정
# ============================================================

def assign_if_position_forced(
    state
):

    """
    한쪽이 특정 포지션 정원을 모두 채우면
    남아 있는 해당 포지션 선수는 상대에게 배정한다.

    현재 경매 중인 선수는 pool에 없으므로
    건드리지 않는다.
    """

    changed = True

    while changed:

        changed = False

        for player in list(
            state["pool"]
        ):

            group = player.get(
                "group"
            )

            if group not in POSITION_KEYS:
                continue

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

            # ------------------------------------------------
            # A가 다 채움 -> B
            # ------------------------------------------------

            if a_full and not b_full:

                state["pool"].remove(
                    player
                )

                state["rosters"]["b"].append(
                    player
                )

                state["log"].append(

                    f"자동 배정: "
                    f"{player['name']} → "
                    f"{state['players']['b']}"

                )

                changed = True

                break

            # ------------------------------------------------
            # B가 다 채움 -> A
            # ------------------------------------------------

            if b_full and not a_full:

                state["pool"].remove(
                    player
                )

                state["rosters"]["a"].append(
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
# 다음 선수
# ============================================================

def next_player(
    state
):

    assign_if_position_forced(
        state
    )

    # --------------------------------------------------------
    # 선수풀이 비었으면 종료
    # --------------------------------------------------------

    if not state["pool"]:

        finish_game(
            state
        )

        return

    # --------------------------------------------------------
    # 맨 앞 선수 하나만 공개
    # --------------------------------------------------------

    player = state["pool"].pop(
        0
    )

    state["current"] = player

    state["current_bid"] = 0

    state["leader"] = None

    # 중요:
    # 첫 입찰 전에는 turn이 없다.
    # 누구든 먼저 버튼을 누를 수 있다.
    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,

    }


# ============================================================
# 게임 종료
# ============================================================

def finish_game(
    state
):

    # --------------------------------------------------------
    # 혹시 남은 선수풀 처리
    # --------------------------------------------------------

    while state["pool"]:

        player = state["pool"].pop(
            0
        )

        a_full = roster_full(
            state,
            "a"
        )

        b_full = roster_full(
            state,
            "b"
        )

        if not a_full:

            state["rosters"]["a"].append(
                player
            )

        elif not b_full:

            state["rosters"]["b"].append(
                player
            )

    # --------------------------------------------------------
    # OVR 총합
    # --------------------------------------------------------

    score_a = sum(

        float(
            p.get(
                "overall",
                0
            )
        )

        for p
        in state["rosters"]["a"]

    )

    score_b = sum(

        float(
            p.get(
                "overall",
                0
            )
        )

        for p
        in state["rosters"]["b"]

    )

    # --------------------------------------------------------
    # 승자
    # --------------------------------------------------------

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

    state["current"] = None

    state["current_bid"] = 0

    state["leader"] = None

    state["turn"] = None


# ============================================================
# 선수 획득
# ============================================================

def award_player(
    state,
    side,
    price
):

    player = state.get(
        "current"
    )

    if player is None:

        return

    price = int(price)

    if price < 0:

        raise ValueError(
            "잘못된 낙찰 금액입니다."
        )

    if price > state["money"][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    # --------------------------------------------------------
    # 돈 처리
    # --------------------------------------------------------

    state["money"][side] -= price

    state["spent"][side] += price

    # --------------------------------------------------------
    # 선수 지급
    # --------------------------------------------------------

    state["rosters"][side].append(
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
    # 자동 배정
    # --------------------------------------------------------

    assign_if_position_forced(
        state
    )

    # --------------------------------------------------------
    # 양쪽 로스터 완성
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
# 첫 입찰
# ============================================================

def start_bid(
    state,
    side,
    amount
):

    amount = int(amount)

    if amount <= 0:

        raise ValueError(
            "입찰 금액은 1달러 이상이어야 합니다."
        )

    if amount > state["money"][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = state["current"].get(
        "group"
    )

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # --------------------------------------------------------
    # 첫 입찰자 = 선두
    # --------------------------------------------------------

    state["current_bid"] = amount

    state["leader"] = side

    # 이후 상대방의 차례
    state["turn"] = (
        "b"
        if side == "a"
        else "a"
    )

    state["auction_started"] = True

    state["passed"] = {

        "a": False,

        "b": False,

    }

    state["log"].append(

        f"{state['players'][side]} "
        f"선제 입찰 ${amount}"

    )


# ============================================================
# 일반 입찰
# ============================================================

def normal_bid(
    state,
    side,
    amount
):

    amount = int(amount)

    # --------------------------------------------------------
    # 현재가보다 높아야 함
    # --------------------------------------------------------

    if amount <= state["current_bid"]:

        raise ValueError(

            f"현재가 "
            f"${state['current_bid']}보다 "
            f"높은 금액을 입력하세요."

        )

    # --------------------------------------------------------
    # 자금
    # --------------------------------------------------------

    if amount > state["money"][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    # --------------------------------------------------------
    # 포지션
    # --------------------------------------------------------

    group = state["current"].get(
        "group"
    )

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # --------------------------------------------------------
    # 선두 변경
    # --------------------------------------------------------

    state["current_bid"] = amount

    state["leader"] = side

    # 다음은 상대방
    state["turn"] = (
        "b"
        if side == "a"
        else "a"
    )

    state["passed"][side] = False

    state["log"].append(

        f"{state['players'][side]} "
        f"→ ${amount}"

    )


# ============================================================
# PASS
# ============================================================

def pass_action(
    state,
    side
):

    other = (
        "b"
        if side == "a"
        else "a"
    )

    # ========================================================
    # 아직 아무도 입찰하지 않음
    # ========================================================

    if not state["auction_started"]:

        state["passed"][side] = True

        state["log"].append(

            f"{state['players'][side]} PASS"

        )

        # ----------------------------------------------------
        # 둘 다 PASS
        # ----------------------------------------------------

        if state["passed"][other]:

            player = state["current"]

            state["pool"].append(
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

            return

        # ----------------------------------------------------
        # 한쪽만 PASS
        # ----------------------------------------------------

        state["turn"] = other

        return

    # ========================================================
    # 이미 경매가 시작된 상태
    # ========================================================

    # --------------------------------------------------------
    # 현재 선두가 PASS
    # -> 상대방이 현재가로 획득
    # --------------------------------------------------------

    if state["leader"] == side:

        state["log"].append(

            f"{state['players'][side]} "
            f"선두 포기"

        )

        award_player(

            state,

            other,

            state["current_bid"]

        )

        return

    # --------------------------------------------------------
    # 선두가 아닌 사람이 PASS
    # -> 현재 선두 낙찰
    # --------------------------------------------------------

    state["log"].append(

        f"{state['players'][side]} PASS"

    )

    award_player(

        state,

        state["leader"],

        state["current_bid"]

    )


# ============================================================
# ALL-IN
# ============================================================

def all_in(
    state,
    side
):

    money = int(
        state["money"][side]
    )

    if money <= 0:

        raise ValueError(
            "사용 가능한 자금이 없습니다."
        )

    group = state["current"].get(
        "group"
    )

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # ========================================================
    # 첫 행동 ALL-IN
    # ========================================================

    if not state["auction_started"]:

        amount = money

        state["current_bid"] = amount

        state["leader"] = side

        state["auction_started"] = True

        state["turn"] = (
            "b"
            if side == "a"
            else "a"
        )

        state["log"].append(

            f"{state['players'][side]} "
            f"ALL-IN ${amount}"

        )

        # ----------------------------------------------------
        # ALL-IN은 즉시 낙찰
        # ----------------------------------------------------

        award_player(

            state,

            side,

            amount

        )

        return

    # ========================================================
    # 이미 경매 중
    # ========================================================

    amount = money

    # --------------------------------------------------------
    # 일반 입찰보다 높아야 하지만
    # 같은 금액이라도 ALL-IN이면 허용
    # --------------------------------------------------------

    if amount < state["current_bid"]:

        raise ValueError(

            f"ALL-IN 금액 "
            f"${amount}이 현재가 "
            f"${state['current_bid']}보다 낮습니다."

        )

    # --------------------------------------------------------
    # ALL-IN 우선 낙찰
    #
    # 같은 금액이면 ALL-IN한 쪽이 가져간다.
    # --------------------------------------------------------

    state["current_bid"] = amount

    state["leader"] = side

    state["log"].append(

        f"{state['players'][side]} "
        f"ALL-IN ${amount}"

    )

    award_player(

        state,

        side,

        amount

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
                20
            )

        )

        if initial_money <= 0:

            raise ValueError(
                "초기 자본은 1달러 이상이어야 합니다."
            )

        # ----------------------------------------------------
        # 포지션
        # ----------------------------------------------------

        limits = {

            "투수": int(
                request.form.get(
                    "pitchers",
                    2
                )
            ),

            "내야수": int(
                request.form.get(
                    "infielders",
                    2
                )
            ),

            "외야수": int(
                request.form.get(
                    "outfielders",
                    2
                )
            ),

            "포수": int(
                request.form.get(
                    "catchers",
                    1
                )
            ),

        }

        for key in POSITION_KEYS:

            if limits[key] < 0:

                raise ValueError(
                    "선수 수는 0 이상이어야 합니다."
                )

        total_players = sum(
            limits.values()
        )

        if total_players <= 0:

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
        # State
        # ----------------------------------------------------

        state = new_state(

            player_pool,

            initial_money,

            limits

        )

        # ----------------------------------------------------
        # 플레이어 이름
        # ----------------------------------------------------

        player_a = request.form.get(
            "player_a",
            "PLAYER 1"
        ).strip()

        player_b = request.form.get(
            "player_b",
            "PLAYER 2"
        ).strip()

        state["players"]["a"] = (
            player_a
            or "PLAYER 1"
        )

        state["players"]["b"] = (
            player_b
            or "PLAYER 2"
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

        save_state(
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

    state = get_state(
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

        error=None

    )


# ============================================================
# 액션
# ============================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(
    game_id
):

    state = get_state(
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
            "side"
        )

        action_type = request.form.get(
            "action"
        )

        # ----------------------------------------------------
        # 플레이어 검사
        # ----------------------------------------------------

        if side not in (
            "a",
            "b"
        ):

            raise ValueError(
                "잘못된 플레이어입니다."
            )

        # ----------------------------------------------------
        # 첫 입찰 전:
        #
        # turn == None
        #
        # -> 누구든 행동 가능
        #
        # 첫 행동 이후:
        #
        # turn에 지정된 사람만 행동 가능
        # ----------------------------------------------------

        if state["turn"] is not None:

            if state["turn"] != side:

                raise ValueError(
                    "현재는 상대방의 차례입니다."
                )

        # ----------------------------------------------------
        # 현재 선수 검사
        # ----------------------------------------------------

        if state.get(
            "current"
        ) is None:

            raise ValueError(
                "현재 경매 중인 선수가 없습니다."
            )

        # ====================================================
        # BID
        # ====================================================

        if action_type == "bid":

            # ------------------------------------------------
            # HTML에서 amount / bid_amount 둘 다 지원
            # ------------------------------------------------

            amount_raw = request.form.get(
                "amount"
            )

            if amount_raw is None:

                amount_raw = request.form.get(
                    "bid_amount"
                )

            if amount_raw is None:

                amount_raw = ""

            amount_raw = str(
                amount_raw
            ).strip()

            if not amount_raw:

                raise ValueError(
                    "입찰 금액을 입력하세요."
                )

            try:

                amount = int(
                    amount_raw
                )

            except ValueError:

                raise ValueError(
                    "입찰 금액은 숫자로 입력하세요."
                )

            # ------------------------------------------------
            # 첫 입찰
            # ------------------------------------------------

            if not state[
                "auction_started"
            ]:

                start_bid(

                    state,

                    side,

                    amount

                )

            # ------------------------------------------------
            # 일반 입찰
            # ------------------------------------------------

            else:

                normal_bid(

                    state,

                    side,

                    amount

                )

        # ====================================================
        # ALL-IN
        # ====================================================

        elif action_type in (
            "allin",
            "all_in"
        ):

            all_in(

                state,

                side

            )

        # ====================================================
        # PASS
        # ====================================================

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

        save_state(

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

        save_state(

            game_id,

            state

        )

        return render_template(

            "draft_game.html",

            state=state,

            game_id=game_id,

            error=error

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

    state = get_state(
        game_id
    )

    if state is None:

        return redirect(

            url_for(
                "draft.draft_home"
            )

        )

    # --------------------------------------------------------
    # 기존 state 호환
    # --------------------------------------------------------

    if "score" not in state:

        score_a = sum(

            float(
                p.get(
                    "overall",
                    0
                )
            )

            for p
            in state["rosters"]["a"]

        )

        score_b = sum(

            float(
                p.get(
                    "overall",
                    0
                )
            )

            for p
            in state["rosters"]["b"]

        )

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

    # --------------------------------------------------------
    # winner가 없으면 계산
    # --------------------------------------------------------

    if not state.get(
        "winner"
    ):

        score_a = state["score"]["a"]

        score_b = state["score"]["b"]

        if score_a > score_b:

            state["winner"] = "a"

        elif score_b > score_a:

            state["winner"] = "b"

        else:

            state["winner"] = "draw"

    save_state(
        game_id,
        state
    )

    return render_template(

        "draft_result.html",

        state=state,

        game_id=game_id

    )


# ============================================================
# 리셋
# ============================================================

@draft_bp.route(
    "/reset/<game_id>",
    methods=["GET"]
)
def reset(
    game_id
):

    delete_state(
        game_id
    )

    return redirect(

        url_for(
            "draft.draft_home"
        )

    )
