# ============================================================
# Draft Mode
# draft_routes.py
#
# Player_pool.json은 절대 수정하지 않는다.
#
# 선수 포지션:
#   선발 / 불펜 / 마무리 -> 투수
#   내야 -> 내야수
#   외야 -> 외야수
#   포수 -> 포수
#
# 게임 방식:
#   1vs1 경매
#   선수풀은 설정한 인원 × 2
#   경매 선수 순서는 랜덤
#   다음 선수는 공개하지 않음
#   첫 행동은 두 플레이어 중 먼저 버튼을 누른 쪽
#   이후에는 서로 번갈아 행동
#   금액은 +1 고정이 아니라 직접 입력
#   ALL-IN은 즉시 해당 선수 획득
#   둘 다 PASS하면 선수는 풀의 맨 뒤로 이동
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


draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 설정
# ============================================================

POSITION_KEYS = [
    "투수",
    "내야수",
    "외야수",
    "포수",
]


SOURCE_POSITION = {
    "선발": "투수",
    "불펜": "투수",
    "마무리": "투수",

    "투수": "투수",

    "내야": "내야수",
    "내야수": "내야수",

    "외야": "외야수",
    "외야수": "외야수",

    "포수": "포수",
}


# ============================================================
# 선수풀 로드
# ============================================================

def _find_player_pool():
    """
    프로젝트 루트에서 Player_pool.json을 찾는다.

    절대로 파일을 쓰지 않는다.
    """

    base = os.path.dirname(
        os.path.abspath(__file__)
    )

    candidates = [
        os.path.join(base, "Player_pool.json"),
        os.path.join(base, "player_pool.json"),
        os.path.join(base, "player_pool.json.txt"),
        os.path.join(base, "Player_pool.json.txt"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        "Player_pool.json 파일을 찾을 수 없습니다."
    )


def load_players():
    """
    Player_pool.json을 읽어서 내부 공통 구조로 변환한다.

    원본 파일은 절대 수정하지 않는다.
    """

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
            raw.get("position", "")
        ).strip()

        group = SOURCE_POSITION.get(
            source_position
        )

        if not group:
            continue

        name = str(
            raw.get("name", "")
        ).strip()

        if not name:
            continue

        player = {
            "pool_id": index,
            "name": name,
            "position": source_position,
            "group": group,
            "rank": raw.get("rank", 999),
            "team": raw.get("team", ""),
            "overall": float(
                raw.get("overall", 0)
            ),
        }

        players.append(player)

    return players


# ============================================================
# 선수풀 검증
# ============================================================

def available_counts(players):
    counts = {
        "투수": 0,
        "내야수": 0,
        "외야수": 0,
        "포수": 0,
    }

    for player in players:

        group = player.get("group")

        if group in counts:
            counts[group] += 1

    return counts


def make_player_pool(
    limits
):
    """
    설정한 인원의 정확히 2배를 뽑는다.

    예:
        투수 2
        내야수 2
        외야수 2
        포수 1

    -> 총 14명
    """

    players = load_players()

    counts = available_counts(players)

    required = {
        key: int(limits[key]) * 2
        for key in POSITION_KEYS
    }

    for key in POSITION_KEYS:

        if required[key] <= 0:
            continue

        if counts[key] < required[key]:
            raise ValueError(
                f"{key} 선수 풀이 부족합니다. "
                f"필요 {required[key]}명 / "
                f"보유 {counts[key]}명"
            )

    selected = []

    for key in POSITION_KEYS:

        candidates = [
            p.copy()
            for p in players
            if p["group"] == key
        ]

        chosen = random.sample(
            candidates,
            required[key]
        )

        selected.extend(chosen)

    random.shuffle(selected)

    return selected


# ============================================================
# 기본 State
# ============================================================

def new_state(
    player_pool,
    initial_money,
    limits,
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

        "roster_size": sum(
            int(limits[key])
            for key in POSITION_KEYS
        ),

        "limits": {
            key: int(limits[key])
            for key in POSITION_KEYS
        },

        "pool": player_pool,

        "current": None,

        "current_bid": 0,

        "leader": None,

        "turn": None,

        "auction_started": False,

        "passed": {
            "a": False,
            "b": False,
        },

        "log": [],

        "done": False,

        "winner": None,
    }


# ============================================================
# Session 저장
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
# 선수 슬롯
# ============================================================

def roster_count(
    state,
    side,
    group
):
    return sum(
        1
        for player in state["rosters"][side]
        if player["group"] == group
    )


def roster_full(
    state,
    side
):
    return (
        len(state["rosters"][side])
        >= state["roster_size"]
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
        >= state["limits"][group]
    )


# ============================================================
# 자동 배정
# ============================================================

def assign_if_position_forced(
    state
):
    """
    어떤 포지션에서 한쪽이 이미 정원을 채웠다면
    해당 포지션의 남은 선수는 다른 쪽으로 자동 배정한다.

    단, 현재 경매 중인 선수는 건드리지 않는다.
    """

    changed = True

    while changed:

        changed = False

        for player in list(
            state["pool"]
        ):

            group = player["group"]

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
# 현재 선수 꺼내기
# ============================================================

def next_player(
    state
):
    """
    풀의 앞에서 하나 꺼낸다.

    다음 선수는 화면에 공개하지 않는다.
    """

    assign_if_position_forced(
        state
    )

    if not state["pool"]:
        finish_game(
            state
        )
        return

    player = state["pool"].pop(0)

    state["current"] = player

    state["current_bid"] = 0

    state["leader"] = None

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
    # 혹시 남은 선수가 있다면 가능한 쪽에 배정
    while state["pool"]:

        player = state["pool"].pop(0)

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

    score_a = sum(
        p["overall"]
        for p in state["rosters"]["a"]
    )

    score_b = sum(
        p["overall"]
        for p in state["rosters"]["b"]
    )

    if score_a > score_b:
        winner = "a"

    elif score_b > score_a:
        winner = "b"

    else:
        winner = "draw"

    state["winner"] = winner

    state["score"] = {
        "a": round(score_a, 1),
        "b": round(score_b, 1),
    }

    state["done"] = True

    state["current"] = None

    state["turn"] = None


# ============================================================
# 선수 획득
# ============================================================

def award_player(
    state,
    side,
    price
):
    player = state["current"]

    if player is None:
        return

    state["money"][side] -= price

    state["spent"][side] += price

    state["rosters"][side].append(
        player
    )

    state["log"].append(
        f"{state['players'][side]} → "
        f"{player['name']} "
        f"(${price})"
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

    assign_if_position_forced(
        state
    )

    if (
        roster_full(state, "a")
        and roster_full(state, "b")
    ):
        finish_game(
            state
        )
        return

    next_player(
        state
    )


# ============================================================
# 경매 시작
# ============================================================

def start_bid(
    state,
    side,
    amount
):
    """
    아무도 먼저 행동하지 않은 상태.

    먼저 누른 사람이 선공자가 된다.
    """

    if amount <= 0:
        raise ValueError(
            "입찰 금액은 1달러 이상이어야 합니다."
        )

    if amount > state["money"][side]:
        raise ValueError(
            "보유 자금보다 큰 금액을 "
            "입찰할 수 없습니다."
        )

    if roster_full(
        state,
        side
    ):
        raise ValueError(
            "이미 로스터가 완성되었습니다."
        )

    group = state["current"]["group"]

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
    if amount <= state["current_bid"]:
        raise ValueError(
            "현재가보다 높은 금액을 입력하세요."
        )

    if amount > state["money"][side]:
        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = state["current"]["group"]

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
    """
    첫 경매:
        A PASS
        B PASS
        -> 선수 풀 맨 뒤

    이미 누군가 입찰:
        현재 선두가 아닌 사람이 PASS
        -> 선두가 획득

    선두가 PASS:
        -> 경매 포기
        -> 상대가 현재가로 획득
    """

    other = (
        "b"
        if side == "a"
        else "a"
    )

    # 아직 아무도 입찰하지 않은 경우
    if not state["auction_started"]:

        state["passed"][side] = True

        state["log"].append(
            f"{state['players'][side]} PASS"
        )

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

            state["turn"] = None

            state["passed"] = {
                "a": False,
                "b": False,
            }

            next_player(
                state
            )

        else:

            state["turn"] = other

        return

    # 선두가 포기
    if state["leader"] == side:

        state["log"].append(
            f"{state['players'][side]} "
            f"경매 포기"
        )

        award_player(
            state,
            other,
            state["current_bid"]
        )

        return

    # 현재 선두가 아닌 사람이 PASS
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
    money = state["money"][side]

    if money <= 0:
        raise ValueError(
            "사용 가능한 자금이 없습니다."
        )

    group = state["current"]["group"]

    if group_full(
        state,
        side,
        group
    ):
        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    amount = money

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
# 게임 생성
# ============================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    try:

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

        if sum(
            limits.values()
        ) <= 0:
            raise ValueError(
                "최소 1명 이상의 선수를 설정하세요."
            )

        player_pool = make_player_pool(
            limits
        )

        state = new_state(
            player_pool,
            initial_money,
            limits
        )

        state["players"]["a"] = (
            request.form.get(
                "player_a",
                "PLAYER 1"
            ).strip()
            or "PLAYER 1"
        )

        state["players"]["b"] = (
            request.form.get(
                "player_b",
                "PLAYER 2"
            ).strip()
            or "PLAYER 2"
        )

        # 첫 선수
        next_player(
            state
        )

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

    if state.get("done"):

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

    if state.get("done"):

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

        if side not in ("a", "b"):
            raise ValueError(
                "잘못된 플레이어입니다."
            )

        # 현재 차례 검사
        if state["turn"] is not None:

            if state["turn"] != side:
                raise ValueError(
                    "상대방의 차례입니다."
                )

        # ====================================================
        # BID
        # ====================================================

        if action_type == "bid":

            amount_raw = request.form.get(
                "amount",
                ""
            ).strip()

            if not amount_raw:
                raise ValueError(
                    "입찰 금액을 입력하세요."
                )

            amount = int(
                amount_raw
            )

            if not state["auction_started"]:

                start_bid(
                    state,
                    side,
                    amount
                )

            else:

                normal_bid(
                    state,
                    side,
                    amount
                )

        # ====================================================
        # ALL IN
        # ====================================================

        elif action_type == "allin":

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

        save_state(
            game_id,
            state
        )

        if state.get("done"):

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

    state = get_state(
        game_id
    )

    if state is None:
        return redirect(
            url_for(
                "draft.draft_home"
            )
        )

    # 혹시 이전 버전 state라 winner가 없다면
    # 여기서 직접 계산한다.
    if not state.get("done"):

        score_a = sum(
            p.get("overall", 0)
            for p in state["rosters"]["a"]
        )

        score_b = sum(
            p.get("overall", 0)
            for p in state["rosters"]["b"]
        )

        if score_a > score_b:
            winner = "a"
        elif score_b > score_a:
            winner = "b"
        else:
            winner = "draw"

        state["score"] = {
            "a": round(score_a, 1),
            "b": round(score_b, 1),
        }

        state["winner"] = winner

    return render_template(
        "draft_result.html",
        state=state,
        game_id=game_id,
    )


# ============================================================
# 다시 시작
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
