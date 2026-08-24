# ============================================================
# Draft Mode
# draft_routes.py
#
# 세션 저장 완전 제거 버전
#
# Player_pool.json
#   - 읽기 전용
#   - 절대로 수정하지 않음
#
# 게임 상태
#   - 서버 메모리 GAMES에 저장
#
# 게임 방식
#   - 1 vs 1
#   - 선수풀 = 설정 인원 x 2
#   - 경매 순서 랜덤
#   - 다음 선수는 공개하지 않음
#   - 첫 행동은 Player 1 / Player 2 중 먼저 누른 사람
#   - 이후 서로 번갈아 행동
#   - 원하는 금액 직접 입력
#   - ALL-IN도 즉시 낙찰되지 않음
#   - ALL-IN 상대가 더 높은 금액을 제시할 수 있음
#   - PASS / PASS -> 선수풀 맨 뒤
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


# ============================================================
# Blueprint
# ============================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 서버 메모리 게임 저장소
# ============================================================

# 중요:
# Flask session을 전혀 사용하지 않는다.
#
# 게임 상태는:
#
# GAMES[game_id] = state
#
# 형태로 저장된다.
#
# 단, Render에서 여러 Gunicorn worker를 사용하면
# worker별 메모리가 다를 수 있다.
#
# 테스트 / 단일 worker에서는 정상적으로 작동한다.
# ============================================================

GAMES = {}


# ============================================================
# 포지션
# ============================================================

POSITION_KEYS = [
    "투수",
    "내야수",
    "외야수",
    "포수",
]


# Player_pool.json의 position을
# Draft에서 사용할 그룹으로 변환
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

        if os.path.isfile(path):

            return path

    raise FileNotFoundError(
        "Player_pool.json 파일을 찾을 수 없습니다."
    )


# ============================================================
# Player_pool.json 로드
# ============================================================

def load_players():

    path = _find_player_pool()

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    # --------------------------------------------------------
    # 혹시 JSON이 {"players":[...]} 형태여도 처리
    # --------------------------------------------------------

    if isinstance(data, dict):

        if isinstance(
            data.get("players"),
            list
        ):

            data = data["players"]

        elif isinstance(
            data.get("data"),
            list
        ):

            data = data["data"]

        else:

            raise ValueError(
                "Player_pool.json의 선수 목록을 찾을 수 없습니다."
            )

    if not isinstance(data, list):

        raise ValueError(
            "Player_pool.json의 최상위 구조가 올바르지 않습니다."
        )

    players = []

    for index, raw in enumerate(data):

        if not isinstance(raw, dict):

            continue

        name = str(
            raw.get("name", "")
        ).strip()

        if not name:

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

        # ----------------------------------------------------
        # 혹시 group / position_group이 있는 데이터도 처리
        # ----------------------------------------------------

        if not group:

            raw_group = str(
                raw.get(
                    "group",
                    ""
                )
            ).strip()

            if raw_group in POSITION_KEYS:

                group = raw_group

        if not group:

            raw_group = str(
                raw.get(
                    "position_group",
                    ""
                )
            ).strip()

            if raw_group in POSITION_KEYS:

                group = raw_group

        if not group:

            continue

        # ----------------------------------------------------
        # overall 안전 처리
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # 선수 객체
        # ----------------------------------------------------

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

        players.append(
            player
        )

    if not players:

        raise ValueError(
            "Player_pool.json에서 사용할 수 있는 선수가 없습니다."
        )

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
# 실제 게임 선수풀 생성
# ============================================================

def make_player_pool(limits):

    players = load_players()

    counts = available_counts(
        players
    )

    required = {}

    for key in POSITION_KEYS:

        amount = int(
            limits.get(
                key,
                0
            )
        )

        required[key] = amount * 2

    # --------------------------------------------------------
    # 선수풀 충분한지 검사
    # --------------------------------------------------------

    shortage = []

    for key in POSITION_KEYS:

        need = required[key]

        have = counts[key]

        if have < need:

            shortage.append(
                f"{key}: 필요 {need}명 / 보유 {have}명"
            )

    if shortage:

        raise ValueError(
            "선수 풀이 부족합니다.\n"
            + "\n".join(shortage)
        )

    selected = []

    # --------------------------------------------------------
    # 포지션별 정확히 2배 추출
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 전체 경매 순서 랜덤
    # --------------------------------------------------------

    random.shuffle(
        selected
    )

    return selected


# ============================================================
# 새 게임 상태
# ============================================================

def new_state(
    player_pool,
    initial_money,
    limits,
):

    roster_size = sum(
        int(
            limits[key]
        )
        for key in POSITION_KEYS
    )

    return {

        # ----------------------------------------------------
        # 플레이어
        # ----------------------------------------------------

        "players": {

            "a": "PLAYER 1",

            "b": "PLAYER 2",

        },

        # ----------------------------------------------------
        # 자금
        # ----------------------------------------------------

        "money": {

            "a": int(
                initial_money
            ),

            "b": int(
                initial_money
            ),

        },

        # ----------------------------------------------------
        # 총 지출
        # ----------------------------------------------------

        "spent": {

            "a": 0,

            "b": 0,

        },

        # ----------------------------------------------------
        # 로스터
        # ----------------------------------------------------

        "rosters": {

            "a": [],

            "b": [],

        },

        # ----------------------------------------------------
        # 포지션 제한
        # ----------------------------------------------------

        "limits": {

            key: int(
                limits[key]
            )

            for key in POSITION_KEYS

        },

        # ----------------------------------------------------
        # 전체 로스터 크기
        # ----------------------------------------------------

        "roster_size": roster_size,

        # ----------------------------------------------------
        # 선수풀
        # ----------------------------------------------------

        "pool": player_pool,

        # ----------------------------------------------------
        # 현재 선수
        # ----------------------------------------------------

        "current": None,

        # ----------------------------------------------------
        # 현재 경매가
        # ----------------------------------------------------

        "current_bid": 0,

        # ----------------------------------------------------
        # 현재 선두
        # ----------------------------------------------------

        "leader": None,

        # ----------------------------------------------------
        # 현재 차례
        # ----------------------------------------------------

        "turn": None,

        # ----------------------------------------------------
        # 경매 시작 여부
        # ----------------------------------------------------

        "auction_started": False,

        # ----------------------------------------------------
        # 첫 행동 PASS 기록
        # ----------------------------------------------------

        "passed": {

            "a": False,

            "b": False,

        },

        # ----------------------------------------------------
        # ALL-IN 여부
        # ----------------------------------------------------

        "all_in": {

            "a": False,

            "b": False,

        },

        # ----------------------------------------------------
        # 로그
        # ----------------------------------------------------

        "log": [],

        # ----------------------------------------------------
        # 종료
        # ----------------------------------------------------

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

def save_state(
    game_id,
    state
):

    GAMES[game_id] = state


# ============================================================
# 게임 조회
# ============================================================

def get_state(
    game_id
):

    return GAMES.get(
        game_id
    )


# ============================================================
# 게임 삭제
# ============================================================

def delete_state(
    game_id
):

    GAMES.pop(
        game_id,
        None
    )


# ============================================================
# 로스터 포지션 수
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

        if player.get("group") == group

    )


# ============================================================
# 로스터 전체 완성 여부
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
# 특정 포지션 완성 여부
# ============================================================

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
# 특정 포지션이 양쪽 모두 완성되었는지
# ============================================================

def group_both_full(
    state,
    group
):

    return (

        group_full(
            state,
            "a",
            group
        )

        and

        group_full(
            state,
            "b",
            group
        )

    )


# ============================================================
# 자동 배정
# ============================================================

def assign_forced_players(
    state
):

    """
    현재 경매 중인 선수는 제외하고
    선수풀에 남은 선수 중 한쪽이 해당 포지션을
    다 채운 경우 반대쪽으로 자동 배정한다.

    예:

        투수 제한 2명

        A 투수 2명 완료
        B 투수 1명

    이후 선수풀의 투수는 B에게 자동 배정.
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

            if not group:
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
            # 양쪽 모두 꽉 찼다면
            # ------------------------------------------------

            if a_full and b_full:

                # 이론적으로 없어야 하지만
                # 안전하게 선수풀에서 제거
                state["pool"].remove(
                    player
                )

                state["log"].append(
                    f"{player['name']} "
                    f"({group}) → 양쪽 정원 초과 방지로 제외"
                )

                changed = True

                break

            # ------------------------------------------------
            # A가 꽉 찼으면 B
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
            # B가 꽉 찼으면 A
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

    # 먼저 자동 배정
    assign_forced_players(
        state
    )

    # 양쪽 로스터 완성
    if (
        roster_full(state, "a")
        and
        roster_full(state, "b")
    ):

        finish_game(
            state
        )

        return

    # 선수풀 소진
    if not state["pool"]:

        finish_game(
            state
        )

        return

    # --------------------------------------------------------
    # 선수풀 앞에서 꺼냄
    # --------------------------------------------------------

    player = state["pool"].pop(
        0
    )

    state["current"] = player

    state["current_bid"] = 0

    state["leader"] = None

    # 핵심:
    # 처음에는 turn이 None.
    #
    # Player 1 / Player 2 중
    # 먼저 요청한 사람이 선공자가 된다.
    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,

    }

    state["all_in"] = {

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
    # 남은 선수는 로스터가 빈 쪽에 배정
    # --------------------------------------------------------

    assign_forced_players(
        state
    )

    # --------------------------------------------------------
    # 그래도 남은 선수가 있으면
    # 로스터 여유가 있는 쪽에 배정
    # --------------------------------------------------------

    while state["pool"]:

        player = state["pool"].pop(
            0
        )

        group = player.get(
            "group"
        )

        # A가 해당 포지션에 자리 있으면 A
        if not group_full(
            state,
            "a",
            group
        ):

            state["rosters"]["a"].append(
                player
            )

            continue

        # B
        if not group_full(
            state,
            "b",
            group
        ):

            state["rosters"]["b"].append(
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
        in state["rosters"]["a"]

    )

    score_b = sum(

        float(
            player.get(
                "overall",
                0
            )
        )

        for player
        in state["rosters"]["b"]

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

    state["auction_started"] = False


# ============================================================
# 선수 낙찰
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

        raise ValueError(
            "현재 경매 선수가 없습니다."
        )

    price = int(
        price
    )

    if price < 0:

        raise ValueError(
            "금액이 올바르지 않습니다."
        )

    if price > state["money"][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = player.get(
        "group"
    )

    # --------------------------------------------------------
    # 포지션 제한 최종 검사
    # --------------------------------------------------------

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    # --------------------------------------------------------
    # 금액 차감
    # --------------------------------------------------------

    state["money"][side] -= price

    state["spent"][side] += price

    # --------------------------------------------------------
    # 선수 등록
    # --------------------------------------------------------

    state["rosters"][side].append(
        player
    )

    # --------------------------------------------------------
    # 로그
    # --------------------------------------------------------

    state["log"].append(

        f"{state['players'][side]} → "
        f"{player['name']} "
        f"${price}"

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

    state["all_in"] = {

        "a": False,

        "b": False,

    }

    # --------------------------------------------------------
    # 자동 배정
    # --------------------------------------------------------

    assign_forced_players(
        state
    )

    # --------------------------------------------------------
    # 게임 종료
    # --------------------------------------------------------

    if (
        roster_full(state, "a")
        and
        roster_full(state, "b")
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

    player = state.get(
        "current"
    )

    if player is None:

        raise ValueError(
            "현재 선수가 없습니다."
        )

    amount = int(
        amount
    )

    if amount <= 0:

        raise ValueError(
            "입찰 금액은 1달러 이상이어야 합니다."
        )

    if amount > state["money"][side]:

        raise ValueError(
            "보유 자금보다 큰 금액을 제시할 수 없습니다."
        )

    group = player.get(
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
    # 첫 제시자가 선공
    # --------------------------------------------------------

    state["current_bid"] = amount

    state["leader"] = side

    state["auction_started"] = True

    state["passed"] = {

        "a": False,

        "b": False,

    }

    # 첫 제시자의 상대가 다음 차례
    other = (
        "b"
        if side == "a"
        else "a"
    )

    state["turn"] = other

    state["log"].append(

        f"{state['players'][side]} "
        f"선제 제시 ${amount}"

    )


# ============================================================
# 일반 입찰
# ============================================================

def normal_bid(
    state,
    side,
    amount
):

    player = state.get(
        "current"
    )

    if player is None:

        raise ValueError(
            "현재 선수가 없습니다."
        )

    amount = int(
        amount
    )

    current_bid = int(
        state["current_bid"]
    )

    # --------------------------------------------------------
    # 반드시 현재가보다 높아야 함
    # --------------------------------------------------------

    if amount <= current_bid:

        raise ValueError(

            f"현재가 ${current_bid}보다 "
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

    group = player.get(
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
    # ALL-IN 상태에서 상대가 더 높게 부른 경우
    #
    # 상대방이 더 높은 금액을 제시하면
    # ALL-IN 플레이어는 더 이상 올릴 수 없다.
    #
    # 따라서 새 제시자가 자동 선두가 되고
    # ALL-IN 플레이어는 사실상 PASS 상태.
    # --------------------------------------------------------

    previous_leader = state.get(
        "leader"
    )

    state["current_bid"] = amount

    state["leader"] = side

    state["passed"][side] = False

    # --------------------------------------------------------
    # 현재 입찰자가 자기 돈 전부를 쓴 경우
    # --------------------------------------------------------

    if amount == state["money"][side]:

        state["all_in"][side] = True

    else:

        state["all_in"][side] = False

    # --------------------------------------------------------
    # 상대 확인
    # --------------------------------------------------------

    other = (
        "b"
        if side == "a"
        else "a"
    )

    # --------------------------------------------------------
    # 상대가 ALL-IN 상태라면
    #
    # 현재 side가 더 높은 금액을 제시한 것이므로
    # 상대는 더 이상 대응할 수 없다.
    #
    # 즉 현재 side가 낙찰.
    # --------------------------------------------------------

    if state["all_in"].get(
        other,
        False
    ):

        state["log"].append(

            f"{state['players'][side]} "
            f"→ ${amount} "
            f"(상대 ALL-IN 초과)"

        )

        award_player(
            state,
            side,
            amount
        )

        return

    # --------------------------------------------------------
    # 정상적으로 상대에게 차례
    # --------------------------------------------------------

    state["turn"] = other

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

    player = state.get(
        "current"
    )

    if player is None:

        raise ValueError(
            "현재 선수가 없습니다."
        )

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
        # 상대도 PASS
        # ----------------------------------------------------

        if state["passed"][other]:

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

            state["all_in"] = {

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
    # 이미 입찰이 존재
    # ========================================================

    leader = state.get(
        "leader"
    )

    if leader is None:

        raise ValueError(
            "경매 선두가 없습니다."
        )

    # --------------------------------------------------------
    # 선두가 PASS
    #
    # 선두가 포기하면 상대가 낙찰
    # --------------------------------------------------------

    if leader == side:

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

    # --------------------------------------------------------
    # 선두가 아닌 사람이 PASS
    #
    # 선두에게 낙찰
    # --------------------------------------------------------

    state["log"].append(

        f"{state['players'][side]} PASS"

    )

    award_player(

        state,

        leader,

        state["current_bid"]

    )


# ============================================================
# ALL-IN
# ============================================================

def all_in(
    state,
    side
):

    player = state.get(
        "current"
    )

    if player is None:

        raise ValueError(
            "현재 선수가 없습니다."
        )

    money = int(
        state["money"][side]
    )

    if money <= 0:

        raise ValueError(
            "사용 가능한 자금이 없습니다."
        )

    group = player.get(
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
    # 첫 ALL-IN
    # ========================================================

    if not state["auction_started"]:

        state["current_bid"] = money

        state["leader"] = side

        state["auction_started"] = True

        state["all_in"][side] = True

        state["passed"] = {

            "a": False,

            "b": False,

        }

        other = (
            "b"
            if side == "a"
            else "a"
        )

        # 상대에게 선택권
        state["turn"] = other

        state["log"].append(

            f"{state['players'][side]} "
            f"ALL-IN ${money}"

        )

        return

    # ========================================================
    # 이미 경매가 진행 중
    # ========================================================

    current_bid = int(
        state["current_bid"]
    )

    # --------------------------------------------------------
    # 현재 금액보다 높게 낼 수 없는 경우
    # --------------------------------------------------------

    if money <= current_bid:

        raise ValueError(

            f"현재가 ${current_bid}보다 "
            f"높게 제시할 수 없습니다."

        )

    # --------------------------------------------------------
    # ALL-IN 금액으로 새 선두
    # --------------------------------------------------------

    state["current_bid"] = money

    state["leader"] = side

    state["all_in"][side] = True

    state["log"].append(

        f"{state['players'][side]} "
        f"ALL-IN ${money}"

    )

    other = (
        "b"
        if side == "a"
        else "a"
    )

    # --------------------------------------------------------
    # 상대에게 한 번 더 선택권
    # --------------------------------------------------------

    if state["money"][other] > money:

        state["turn"] = other

        return

    # --------------------------------------------------------
    # 상대가 더 높게 제시할 수 없음
    #
    # 상대가 돈이 같거나 적으면
    # ALL-IN 선두가 낙찰.
    # --------------------------------------------------------

    award_player(
        state,
        side,
        money
    )


# ============================================================
# 홈
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

        raw_money = request.form.get(
            "initial_money",
            "20"
        ).strip()

        if not raw_money:

            raw_money = "20"

        initial_money = int(
            raw_money
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
                    f"{key} 인원은 0 이상이어야 합니다."
                )

        roster_size = sum(
            limits.values()
        )

        if roster_size <= 0:

            raise ValueError(
                "최소 1명 이상의 선수를 설정하세요."
            )

        # ----------------------------------------------------
        # 선수풀
        # ----------------------------------------------------

        player_pool = make_player_pool(
            limits
        )

        # ----------------------------------------------------
        # 상태 생성
        # ----------------------------------------------------

        state = new_state(

            player_pool=player_pool,

            initial_money=initial_money,

            limits=limits

        )

        # ----------------------------------------------------
        # 이름
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
            or
            "PLAYER 1"
        )

        state["players"]["b"] = (
            player_b
            or
            "PLAYER 2"
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

        # ----------------------------------------------------
        # 메모리 저장
        # ----------------------------------------------------

        save_state(
            game_id,
            state
        )

        # ----------------------------------------------------
        # 게임 화면
        # ----------------------------------------------------

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
        "done",
        False
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
        "done",
        False
    ):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )

    error = None

    try:

        # ----------------------------------------------------
        # 어느 플레이어가 행동했는가
        # ----------------------------------------------------

        side = request.form.get(
            "side",
            ""
        ).strip()

        if side not in (
            "a",
            "b"
        ):

            raise ValueError(
                "잘못된 플레이어입니다."
            )

        # ----------------------------------------------------
        # 첫 행동
        #
        # turn == None이면
        # 먼저 요청한 사람이 선공.
        # ----------------------------------------------------

        if state["turn"] is not None:

            if state["turn"] != side:

                raise ValueError(
                    f"{state['players'][state['turn']]}의 차례입니다."
                )

        # ----------------------------------------------------
        # 액션
        # ----------------------------------------------------

        action_type = request.form.get(
            "action",
            ""
        ).strip()

        # ====================================================
        # BID
        # ====================================================

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
                    "금액은 숫자로 입력하세요."
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
        # ALL-IN
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
            "done",
            False
        ):

            return redirect(

                url_for(

                    "draft.result",

                    game_id=game_id

                )

            )

        # ----------------------------------------------------
        # 다시 게임 화면
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # 이전 버전 state 호환
    # --------------------------------------------------------

    if "players" not in state:

        state["players"] = {

            "a": "PLAYER 1",

            "b": "PLAYER 2",

        }

    if "rosters" not in state:

        state["rosters"] = {

            "a": [],

            "b": [],

        }

    # --------------------------------------------------------
    # 결과가 아직 없으면 계산
    # --------------------------------------------------------

    if not state.get(
        "done",
        False
    ):

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

        save_state(
            game_id,
            state
        )

    # --------------------------------------------------------
    # 결과 안전값
    # --------------------------------------------------------

    if "winner" not in state:

        state["winner"] = "draw"

    if "score" not in state:

        state["score"] = {

            "a": 0,

            "b": 0,

        }

    return render_template(

        "draft_result.html",

        state=state,

        game_id=game_id

    )


# ============================================================
# 게임 초기화
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


# ============================================================
# 디버그용 게임 상태 확인
# ============================================================

@draft_bp.route(
    "/debug/<game_id>",
    methods=["GET"]
)
def debug_game(
    game_id
):

    state = get_state(
        game_id
    )

    if state is None:

        return {
            "error": "game not found"
        }, 404

    return {

        "game_id": game_id,

        "players": state["players"],

        "money": state["money"],

        "spent": state["spent"],

        "rosters": state["rosters"],

        "limits": state["limits"],

        "current": state["current"],

        "current_bid": state["current_bid"],

        "leader": state["leader"],

        "turn": state["turn"],

        "auction_started": state[
            "auction_started"
        ],

        "pool_remaining": len(
            state["pool"]
        ),

        "done": state["done"],

        "winner": state["winner"],

        "score": state["score"],

    }
