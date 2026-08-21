# ============================================================
# draft_routes.py
# ============================================================
#
# 144-0 Challenge
# Draft Mode
#
# 1 vs 1 선수 경매
#
# 실제 player_pool.json 구조:
#
# 투수:
#   선발
#   불펜
#   마무리
#
# 야수:
#   포수
#   내야
#   외야
#
# Draft 내부 그룹:
#   투수
#   포수
#   내야수
#   외야수
#
# ============================================================


import os
import json
import random
import uuid
import copy

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)


# ============================================================
# Blueprint
# ============================================================

draft = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 파일 위치
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


PLAYER_POOL_PATH = os.path.join(
    BASE_DIR,
    "player_pool.json"
)


# 혹시 서버에 txt로 들어가 있는 경우
PLAYER_POOL_TXT_PATH = os.path.join(
    BASE_DIR,
    "player_pool.json.txt"
)


# ============================================================
# 기본값
# ============================================================

DEFAULT_START_MONEY = 20

DEFAULT_PITCHERS = 2
DEFAULT_INFIELDERS = 2
DEFAULT_OUTFIELDERS = 2
DEFAULT_CATCHERS = 1


# ============================================================
# 선수풀 로드
# ============================================================

def load_player_pool():

    path = PLAYER_POOL_PATH

    if not os.path.exists(path):

        if os.path.exists(
            PLAYER_POOL_TXT_PATH
        ):
            path = PLAYER_POOL_TXT_PATH

        else:

            raise FileNotFoundError(
                "player_pool.json 파일을 찾을 수 없습니다."
            )


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        players = json.load(f)


    result = []


    for player in players:

        position = str(
            player.get(
                "position",
                ""
            )
        ).strip()


        # ----------------------------------------------------
        # 실제 JSON 포지션 → Draft 그룹
        # ----------------------------------------------------

        # 선발 / 불펜 / 마무리 = 투수
        if position in (
            "선발",
            "불펜",
            "마무리"
        ):

            group = "투수"


        elif position == "포수":

            group = "포수"


        elif position == "내야":

            group = "내야수"


        elif position == "외야":

            group = "외야수"


        else:

            # 알 수 없는 포지션은 Draft에서 제외
            continue


        result.append({

            "name": player.get(
                "name",
                "이름 없음"
            ),

            "team": player.get(
                "team",
                ""
            ),

            "overall": float(
                player.get(
                    "overall",
                    0
                )
            ),

            # 실제 원본 포지션
            "position": position,

            # Draft용 그룹
            "group": group,

            "rank": player.get(
                "rank",
                0
            )

        })


    return result


# ============================================================
# 그룹별 선수
# ============================================================

def players_by_group():

    players = load_player_pool()

    result = {

        "투수": [],
        "내야수": [],
        "외야수": [],
        "포수": []

    }


    for player in players:

        group = player["group"]

        if group in result:

            result[group].append(
                player
            )


    return result


# ============================================================
# 선수풀 생성
# ============================================================

def make_player_pool(
    pitchers,
    infielders,
    outfielders,
    catchers
):

    required = {

        "투수":
            int(pitchers) * 2,

        "내야수":
            int(infielders) * 2,

        "외야수":
            int(outfielders) * 2,

        "포수":
            int(catchers) * 2

    }


    grouped = players_by_group()


    pool = []


    for group, count in required.items():

        candidates = list(
            grouped.get(
                group,
                []
            )
        )


        if len(candidates) < count:

            raise ValueError(
                f"{group} 선수 풀이 부족합니다. "
                f"필요 {count}명 / "
                f"보유 {len(candidates)}명"
            )


        random.shuffle(
            candidates
        )


        selected = candidates[
            :count
        ]


        pool.extend(
            copy.deepcopy(
                selected
            )
        )


    # 최종 경매 순서는 랜덤
    random.shuffle(pool)


    return pool


# ============================================================
# 입력값 안전하게 가져오기
# ============================================================

def get_int(
    names,
    default
):

    if isinstance(
        names,
        str
    ):

        names = [names]


    for name in names:

        value = request.form.get(
            name
        )


        if value is None:
            continue


        try:

            return int(value)

        except (
            TypeError,
            ValueError
        ):

            continue


    return default


# ============================================================
# 게임 상태 생성
# ============================================================

def create_game(
    player_a,
    player_b,
    start_money,
    pitchers,
    infielders,
    outfielders,
    catchers
):

    pool = make_player_pool(
        pitchers,
        infielders,
        outfielders,
        catchers
    )


    game_id = uuid.uuid4().hex


    state = {

        # ----------------------------------------------------
        # 플레이어
        # ----------------------------------------------------

        "players": {

            "a": player_a,

            "b": player_b

        },


        # ----------------------------------------------------
        # 돈
        # ----------------------------------------------------

        "money": {

            "a": int(start_money),

            "b": int(start_money)

        },


        "spent": {

            "a": 0,

            "b": 0

        },


        # ----------------------------------------------------
        # 로스터
        # ----------------------------------------------------

        "rosters": {

            "a": [],

            "b": []

        },


        # ----------------------------------------------------
        # 포지션 제한
        # ----------------------------------------------------

        "limits": {

            "투수":
                int(pitchers),

            "내야수":
                int(infielders),

            "외야수":
                int(outfielders),

            "포수":
                int(catchers)

        },


        "roster_size": (

            int(pitchers)
            + int(infielders)
            + int(outfielders)
            + int(catchers)

        ),


        # ----------------------------------------------------
        # 선수풀
        # ----------------------------------------------------

        "pool": pool,


        # 현재 선수
        #
        # 현재 선수만 공개.
        # 다음 선수는 HTML에 전달하지 않음.
        # ----------------------------------------------------

        "current": None,


        # ----------------------------------------------------
        # 경매
        # ----------------------------------------------------

        "bid": 0,

        "leader": None,

        "turn": random.choice(
            ["a", "b"]
        ),

        "passed": {

            "a": False,

            "b": False

        },


        # ----------------------------------------------------
        # 로그
        # ----------------------------------------------------

        "log": [],


        # ----------------------------------------------------
        # 종료
        # ----------------------------------------------------

        "finished": False,

        "winner": None

    }


    # 첫 선수
    advance_player(
        state
    )


    state["log"].append(
        "Draft가 시작되었습니다."
    )


    return game_id, state


# ============================================================
# 다음 선수 등장
# ============================================================

def advance_player(state):

    # 더 이상 선수 없음
    if not state["pool"]:

        state["current"] = None

        state["finished"] = True

        determine_winner(
            state
        )

        return


    state["current"] = (
        state["pool"].pop(0)
    )


    state["bid"] = 0

    state["leader"] = None

    state["passed"] = {

        "a": False,

        "b": False

    }


    # 다음 선수는 랜덤으로 시작
    state["turn"] = random.choice(
        ["a", "b"]
    )


# ============================================================
# 포지션 제한 확인
# ============================================================

def roster_can_add(
    state,
    side,
    player
):

    group = player["group"]


    limit = state[
        "limits"
    ].get(
        group,
        0
    )


    current = 0


    for p in state[
        "rosters"
    ][side]:

        if p.get(
            "group"
        ) == group:

            current += 1


    return current < limit


# ============================================================
# 로스터가 꽉 찼는지
# ============================================================

def roster_full(
    state,
    side
):

    return len(
        state["rosters"][side]
    ) >= state["roster_size"]


# ============================================================
# 두 선수 모두 로스터 완성?
# ============================================================

def both_full(state):

    return (
        roster_full(
            state,
            "a"
        )
        and
        roster_full(
            state,
            "b"
        )
    )


# ============================================================
# 특정 플레이어가 남은 선수를 전부 받을 수 있는 경우
# ============================================================

def remaining_slots(
    state,
    side
):

    return (
        state["roster_size"]
        -
        len(
            state["rosters"][side]
        )
    )


# ============================================================
# 승자 결정
# ============================================================

def determine_winner(state):

    a = len(
        state["rosters"]["a"]
    )

    b = len(
        state["rosters"]["b"]
    )


    if a >= state["roster_size"]:

        state["winner"] = "a"

        return


    if b >= state["roster_size"]:

        state["winner"] = "b"

        return


    # 둘 다 동일하게 못 채운 경우
    # 남은 선수 수와 지출을 비교하지 않고
    # 우선 돈이 많은 쪽을 우위로 둔다.

    if state["money"]["a"] > state["money"]["b"]:

        state["winner"] = "a"

    elif state["money"]["b"] > state["money"]["a"]:

        state["winner"] = "b"

    else:

        state["winner"] = None


# ============================================================
# PASS 처리
# ============================================================

def handle_pass(
    state,
    side
):

    player = state[
        "players"
    ][side]


    state["log"].append(
        f"{player} → PASS"
    )


    state["passed"][side] = True


    other = (
        "b"
        if side == "a"
        else "a"
    )


    # 상대가 이미 PASS했다면
    # 둘 다 원하지 않는 선수
    if state[
        "passed"
    ][other]:

        current = state["current"]


        if current:

            state["log"].append(
                f"{current['name']} → "
                "양쪽 모두 PASS"
            )


            # 선수풀 맨 뒤로
            state["pool"].append(
                current
            )


        # 새로운 선수
        advance_player(
            state
        )

        return


    # 상대방 차례
    state["turn"] = other


# ============================================================
# BID 처리
# ============================================================

def handle_bid(
    state,
    side
):

    player = state[
        "players"
    ][side]


    current = state[
        "current"
    ]


    if not current:

        return


    # 로스터 제한
    if not roster_can_add(
        state,
        side,
        current
    ):

        raise ValueError(
            "해당 포지션의 "
            "로스터 자리가 없습니다."
        )


    # 입찰가는 1달러씩
    new_bid = (
        state["bid"] + 1
    )


    # 돈 부족
    if state[
        "money"
    ][side] < new_bid:

        raise ValueError(
            "보유 금액이 부족합니다."
        )


    state["bid"] = new_bid

    state["leader"] = side

    state["passed"] = {

        "a": False,

        "b": False

    }


    state["log"].append(
        f"{player} → "
        f"${new_bid} 입찰"
    )


    # 상대방에게 차례
    state["turn"] = (
        "b"
        if side == "a"
        else "a"
    )


# ============================================================
# ALL-IN 처리
# ============================================================

def handle_all_in(
    state,
    side
):

    player = state[
        "players"
    ][side]


    current = state[
        "current"
    ]


    if not current:

        return


    # 포지션 자리 확인
    if not roster_can_add(
        state,
        side,
        current
    ):

        raise ValueError(
            "해당 포지션의 "
            "로스터 자리가 없습니다."
        )


    money = state[
        "money"
    ][side]


    if money <= state["bid"]:

        raise ValueError(
            "올인할 금액이 없습니다."
        )


    # 현재 가진 돈 전부
    new_bid = money


    # --------------------------------------------------------
    # 동액 ALL-IN
    #
    # 사용자가 원한 규칙:
    #
    # 동일 금액에서 올인하면
    # 올인한 사람이 선수 획득
    # --------------------------------------------------------

    state["bid"] = new_bid

    state["leader"] = side


    state["log"].append(
        f"{player} → "
        f"${new_bid} ALL-IN"
    )


    # 바로 낙찰
    award_current_player(
        state,
        side,
        all_in=True
    )


# ============================================================
# 선수 낙찰
# ============================================================

def award_current_player(
    state,
    side,
    all_in=False
):

    current = state[
        "current"
    ]


    if not current:

        return


    bid = state[
        "bid"
    ]


    if bid <= 0:

        raise ValueError(
            "낙찰 금액이 올바르지 않습니다."
        )


    # 돈 확인
    if state[
        "money"
    ][side] < bid:

        raise ValueError(
            "보유 금액이 부족합니다."
        )


    # 포지션 확인
    if not roster_can_add(
        state,
        side,
        current
    ):

        raise ValueError(
            "해당 포지션의 "
            "로스터 자리가 없습니다."
        )


    player_name = current[
        "name"
    ]


    # 돈 차감
    state[
        "money"
    ][side] -= bid


    state[
        "spent"
    ][side] += bid


    # 선수 지급
    state[
        "rosters"
    ][side].append(
        current
    )


    owner = state[
        "players"
    ][side]


    if all_in:

        state["log"].append(
            f"{player_name} → "
            f"{owner} 낙찰 "
            f"(${bid}, ALL-IN)"
        )

    else:

        state["log"].append(
            f"{player_name} → "
            f"{owner} 낙찰 "
            f"(${bid})"
        )


    # 현재 선수 제거
    state["current"] = None


    # 두 팀 모두 완성
    if both_full():

        state["finished"] = True

        determine_winner(
            state
        )

        return


    # 한쪽만 완성
    if roster_full(
        state,
        side
    ):

        other = (
            "b"
            if side == "a"
            else "a"
        )


        # 이후 선수는 상대에게 자동 지급
        # 단, 상대의 포지션 제한을 확인
        if not roster_full(
            state,
            other
        ):

            state["turn"] = other


    else:

        # 다음 선수
        state["turn"] = random.choice(
            ["a", "b"]
        )


    advance_player(
        state
    )


# ============================================================
# 일반 입찰 종료
#
# 상대가 PASS하면 현재 선두가 낙찰
# ============================================================

def resolve_pass(
    state,
    side
):

    other = (
        "b"
        if side == "a"
        else "a"
    )


    # 상대가 PASS
    if state[
        "passed"
    ][side] and state[
        "leader"
    ] == other:

        award_current_player(
            state,
            other
        )

        return True


    return False


# ============================================================
# 한쪽이 로스터를 다 채웠을 경우
# ============================================================

def auto_fill_for_remaining_player(
    state
):

    # 한쪽이 완성되면
    # 남은 선수는 다른 쪽으로 자동 배정
    while True:

        if not state["current"]:

            if state["finished"]:

                return

            if not state["pool"]:

                state["finished"] = True

                determine_winner(
                    state
                )

                return

            advance_player(
                state
            )


        if not state["current"]:

            return


        current = state[
            "current"
        ]


        # 아직 자리가 있는 쪽 찾기
        available = []


        for side in (
            "a",
            "b"
        ):

            if not roster_full(
                state,
                side
            ) and roster_can_add(
                state,
                side,
                current
            ):

                available.append(
                    side
                )


        # 둘 다 가능 → 경매 진행
        if len(available) == 2:

            return


        # 한쪽만 가능 → 자동 지급
        if len(available) == 1:

            side = available[0]


            # 자동 지급은 무료가 아니라
            # 현재 bid가 있다면 정상 낙찰.
            #
            # 보통 이 상황에서는 bid=0이므로
            # 무료 지급.
            #
            # 상대가 이미 로스터를 채웠기 때문에
            # 남은 선수는 자동으로 상대에게 감.

            state[
                "rosters"
            ][side].append(
                current
            )


            state["log"].append(
                f"{current['name']} → "
                f"{state['players'][side]} "
                "자동 배정"
            )


            state["current"] = None


            continue


        # 아무도 받을 수 없음
        state["current"] = None

        continue


# ============================================================
# 게임 상태 저장
# ============================================================

def save_game(
    game_id,
    state
):

    games = session.get(
        "draft_games",
        {}
    )


    games[game_id] = state


    session[
        "draft_games"
    ] = games


    session.modified = True


# ============================================================
# 게임 상태 가져오기
# ============================================================

def get_game(
    game_id
):

    games = session.get(
        "draft_games",
        {}
    )


    return games.get(
        game_id
    )


# ============================================================
# 게임 상태 삭제
# ============================================================

def delete_game(
    game_id
):

    games = session.get(
        "draft_games",
        {}
    )


    if game_id in games:

        del games[
            game_id
        ]


    session[
        "draft_games"
    ] = games

    session.modified = True


# ============================================================
# Draft 메인
#
# /draft
# ============================================================

@draft.route(
    "/",
    methods=["GET"]
)
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# ============================================================
# /draft도 허용
# ============================================================

@draft.route(
    "",
    methods=["GET"]
)
def draft_home_no_slash():

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )


# ============================================================
# 게임 생성
#
# POST /draft/start
# ============================================================

@draft.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    player_a = (
        request.form.get(
            "player_a"
        )
        or
        request.form.get(
            "name_a"
        )
        or
        "PLAYER A"
    )


    player_b = (
        request.form.get(
            "player_b"
        )
        or
        request.form.get(
            "name_b"
        )
        or
        "PLAYER B"
    )


    start_money = get_int(
        [
            "start_money",
            "money",
            "initial_money"
        ],
        DEFAULT_START_MONEY
    )


    pitchers = get_int(
        [
            "pitchers",
            "pitcher",
            "투수"
        ],
        DEFAULT_PITCHERS
    )


    infielders = get_int(
        [
            "infielders",
            "inf",
            "내야수",
            "내야"
        ],
        DEFAULT_INFIELDERS
    )


    outfielders = get_int(
        [
            "outfielders",
            "of",
            "외야수",
            "외야"
        ],
        DEFAULT_OUTFIELDERS
    )


    catchers = get_int(
        [
            "catchers",
            "catcher",
            "포수"
        ],
        DEFAULT_CATCHERS
    )


    # --------------------------------------------------------
    # 기본 검증
    # --------------------------------------------------------

    if start_money <= 0:

        return render_template(
            "draft_setup.html",
            error="초기 자본은 1달러 이상이어야 합니다."
        )


    if pitchers < 0:
        pitchers = 0

    if infielders < 0:
        infielders = 0

    if outfielders < 0:
        outfielders = 0

    if catchers < 0:
        catchers = 0


    roster_size = (
        pitchers
        + infielders
        + outfielders
        + catchers
    )


    if roster_size <= 0:

        return render_template(
            "draft_setup.html",
            error="최소 1명의 선수를 설정해야 합니다."
        )


    # --------------------------------------------------------
    # 선수풀 생성
    # --------------------------------------------------------

    try:

        game_id, state = create_game(

            player_a,
            player_b,

            start_money,

            pitchers,
            infielders,
            outfielders,
            catchers

        )

    except Exception as e:

        return render_template(
            "draft_setup.html",
            error=str(e)
        )


    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

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


# ============================================================
# 게임 화면
#
# /draft/game/<game_id>
# ============================================================

@draft.route(
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

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    # --------------------------------------------------------
    # 한쪽이 모두 채웠으면 자동 배정 처리
    # --------------------------------------------------------

    if not state.get(
        "finished",
        False
    ):

        auto_fill_for_remaining_player(
            state
        )


        save_game(
            game_id,
            state
        )


    # --------------------------------------------------------
    # 종료
    # --------------------------------------------------------

    if state.get(
        "finished"
    ):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    # --------------------------------------------------------
    # 템플릿에는 현재 선수만 전달
    #
    # pool 전체는 전달하지 않음.
    # 다음 선수 순서를 숨기는 것이 목적.
    # --------------------------------------------------------

    visible_state = {

        "players":
            state["players"],

        "money":
            state["money"],

        "spent":
            state["spent"],

        "rosters":
            state["rosters"],

        "limits":
            state["limits"],

        "roster_size":
            state["roster_size"],

        "current":
            state["current"],

        "bid":
            state["bid"],

        "leader":
            state["leader"],

        "turn":
            state["turn"],

        "log":
            state["log"],

        "finished":
            state["finished"],

        "winner":
            state["winner"]

    }


    return render_template(
        "draft_game.html",
        state=visible_state,
        game_id=game_id,
        save_id=game_id,
        error=None
    )


# ============================================================
# 기존 템플릿 호환용
#
# /draft/game/<save_id>/<game_id>
#
# ============================================================

@draft.route(
    "/game/<save_id>/<game_id>",
    methods=["GET"]
)
def game_legacy(
    save_id,
    game_id
):

    state = get_game(
        game_id
    )


    if state is None:

        state = get_game(
            save_id
        )

        if state is not None:

            game_id = save_id


    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# ============================================================
# 경매 액션
#
# POST /draft/game/<game_id>/action
# ============================================================

@draft.route(
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

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    if state.get(
        "finished",
        False
    ):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    side = (
        request.form.get(
            "side"
        )
        or
        state["turn"]
    )


    if side not in (
        "a",
        "b"
    ):

        side = state["turn"]


    # --------------------------------------------------------
    # 실제 현재 차례가 아닌 경우
    # --------------------------------------------------------

    if side != state["turn"]:

        return render_game_error(
            game_id,
            state,
            "현재 차례가 아닙니다."
        )


    action_type = (
        request.form.get(
            "action"
        )
        or
        ""
    ).lower()


    try:

        # ----------------------------------------------------
        # BID
        # ----------------------------------------------------

        if action_type in (
            "bid",
            "raise"
        ):

            handle_bid(
                state,
                side
            )


        # ----------------------------------------------------
        # ALL-IN
        # ----------------------------------------------------

        elif action_type in (
            "allin",
            "all_in"
        ):

            handle_all_in(
                state,
                side
            )


        # ----------------------------------------------------
        # PASS
        # ----------------------------------------------------

        elif action_type == "pass":

            # 이미 선두가 있는 경우
            # PASS = 선두에게 낙찰
            if (
                state["leader"]
                and
                state["leader"] != side
            ):

                state["passed"][side] = True


                state["log"].append(
                    f"{state['players'][side]} "
                    "→ PASS"
                )


                leader = state[
                    "leader"
                ]


                award_current_player(
                    state,
                    leader
                )


            else:

                handle_pass(
                    state,
                    side
                )


        else:

            raise ValueError(
                "잘못된 경매 액션입니다."
            )


        # ----------------------------------------------------
        # 자동 배정
        # ----------------------------------------------------

        if not state.get(
            "finished",
            False
        ):

            auto_fill_for_remaining_player(
                state
            )


        save_game(
            game_id,
            state
        )


    except Exception as e:

        return render_game_error(
            game_id,
            state,
            str(e)
        )


    if state.get(
        "finished",
        False
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


# ============================================================
# 기존 템플릿 호환용 액션
#
# POST /draft/game/<save_id>/<game_id>/action
# ============================================================

@draft.route(
    "/game/<save_id>/<game_id>/action",
    methods=["POST"]
)
def action_legacy(
    save_id,
    game_id
):

    state = get_game(
        game_id
    )


    if state is None:

        state = get_game(
            save_id
        )

        if state is not None:

            game_id = save_id


    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    return action(
        game_id
    )


# ============================================================
# 오류 화면
# ============================================================

def render_game_error(
    game_id,
    state,
    error
):

    visible_state = {

        "players":
            state["players"],

        "money":
            state["money"],

        "spent":
            state["spent"],

        "rosters":
            state["rosters"],

        "limits":
            state["limits"],

        "roster_size":
            state["roster_size"],

        "current":
            state["current"],

        "bid":
            state["bid"],

        "leader":
            state["leader"],

        "turn":
            state["turn"],

        "log":
            state["log"],

        "finished":
            state["finished"],

        "winner":
            state["winner"]

    }


    return render_template(
        "draft_game.html",
        state=visible_state,
        game_id=game_id,
        save_id=game_id,
        error=error
    )


# ============================================================
# 결과 화면
#
# /draft/result/<game_id>
# ============================================================

@draft.route(
    "/result/<game_id>",
    methods=["GET"]
)
def result(
    game_id
):

    state = get_game(
        game_id
    )


    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    # 아직 끝나지 않았으면 게임으로
    if not state.get(
        "finished",
        False
    ):

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    winner = state.get(
        "winner"
    )


    return render_template(
        "draft_result.html",
        state=state,
        game_id=game_id,
        winner=winner
    )


# ============================================================
# 새 Draft
# ============================================================

@draft.route(
    "/new",
    methods=["GET"]
)
def new_game():

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )


# ============================================================
# 게임 삭제
# ============================================================

@draft.route(
    "/delete/<game_id>",
    methods=["POST"]
)
def delete(
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
