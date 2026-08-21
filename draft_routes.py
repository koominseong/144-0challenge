# draft_routes.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

import json
import os
import random
import uuid
from copy import deepcopy


# =========================================================
# Blueprint
# =========================================================

draft_bp = Blueprint(
    "draft",
    __name__
)


# =========================================================
# 게임 저장소
# =========================================================
#
# 현재는 서버 메모리에 저장한다.
#
# game_id를 URL에 넣기 때문에
# 같은 게임 화면을 새로고침해도 유지된다.
#
# 서버 재시작 시 초기화된다.
# 나중에 Supabase를 붙일 경우 이 부분만 교체하면 된다.
#

DRAFT_GAMES = {}


# =========================================================
# 기본 설정
# =========================================================

DEFAULT_START_MONEY = 20

DEFAULT_LIMITS = {
    "투수": 2,
    "내야수": 2,
    "외야수": 2,
    "포수": 1,
}

DEFAULT_PLAYER_NAMES = {
    "a": "PLAYER A",
    "b": "PLAYER B",
}


# =========================================================
# 선수풀 경로
# =========================================================

def _find_player_pool():

    base_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    candidates = [

        os.path.join(
            base_dir,
            "player_pool.json"
        ),

        os.path.join(
            base_dir,
            "player_pool.json.txt"
        ),

        os.path.join(
            base_dir,
            "data",
            "player_pool.json"
        ),

        os.path.join(
            base_dir,
            "data",
            "player_pool.json.txt"
        ),
    ]

    for path in candidates:

        if os.path.exists(path):

            return path

    return None


# =========================================================
# 선수풀 로드
# =========================================================

def _load_player_pool():

    path = _find_player_pool()

    if not path:

        raise FileNotFoundError(
            "player_pool.json 또는 "
            "player_pool.json.txt 파일을 찾을 수 없습니다."
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if isinstance(data, dict):

        # 혹시 {"players": [...]} 형태라면
        if isinstance(data.get("players"), list):
            data = data["players"]

        # 혹시 {"pool": [...]} 형태라면
        elif isinstance(data.get("pool"), list):
            data = data["pool"]

        else:

            # dict 안에 list가 하나만 있는 경우
            lists = [
                value
                for value in data.values()
                if isinstance(value, list)
            ]

            if len(lists) == 1:
                data = lists[0]

    if not isinstance(data, list):

        raise ValueError(
            "player_pool.json의 형식이 올바르지 않습니다."
        )

    result = []

    for raw in data:

        if not isinstance(raw, dict):
            continue

        name = raw.get("name")

        if not name:
            continue

        position = str(
            raw.get("position", "")
        ).strip()

        group = _normalize_group(position)

        player = {

            "name": str(name),

            "position": position,

            "group": group,

            "rank": raw.get(
                "rank",
                9999
            ),

            "team": raw.get(
                "team",
                ""
            ),

            "overall": float(
                raw.get(
                    "overall",
                    0
                )
            ),
        }

        result.append(player)

    return result


# =========================================================
# 포지션 정규화
# =========================================================

def _normalize_group(position):

    p = str(position).strip().lower()

    # 투수
    if p in {
        "투수",
        "p",
        "pitcher",
        "sp",
        "rp",
        "cp",
        "선발",
        "선발투수",
        "불펜",
        "중간계투",
        "마무리",
        "마무리투수",
    }:
        return "투수"

    # 내야
    if p in {
        "내야",
        "내야수",
        "if",
        "infielder",
        "1b",
        "2b",
        "3b",
        "ss",
    }:
        return "내야수"

    # 외야
    if p in {
        "외야",
        "외야수",
        "of",
        "outfielder",
        "lf",
        "cf",
        "rf",
    }:
        return "외야수"

    # 포수
    if p in {
        "포수",
        "c",
        "catcher",
    }:
        return "포수"

    # 애매한 경우 원래 명칭을 사용
    return position


# =========================================================
# 숫자 변환
# =========================================================

def _to_int(value, default=0):

    try:

        return int(value)

    except (
        TypeError,
        ValueError
    ):

        return default


# =========================================================
# 설정값 정리
# =========================================================

def _get_int(form, key, default):

    value = form.get(key)

    if value is None:
        return default

    try:

        value = int(value)

    except (
        TypeError,
        ValueError
    ):

        return default

    return value


# =========================================================
# 포지션별 필요 선수 수
# =========================================================

def _get_limits(form):

    limits = {

        "투수": max(
            0,
            _get_int(
                form,
                "pitchers",
                DEFAULT_LIMITS["투수"]
            )
        ),

        "내야수": max(
            0,
            _get_int(
                form,
                "infielders",
                DEFAULT_LIMITS["내야수"]
            )
        ),

        "외야수": max(
            0,
            _get_int(
                form,
                "outfielders",
                DEFAULT_LIMITS["외야수"]
            )
        ),

        "포수": max(
            0,
            _get_int(
                form,
                "catchers",
                DEFAULT_LIMITS["포수"]
            )
        ),
    }

    return limits


# =========================================================
# 로스터 크기
# =========================================================

def _roster_size(limits):

    return sum(
        limits.values()
    )


# =========================================================
# 로스터가 포지션 제한을 만족하는지
# =========================================================

def _position_count(roster, group):

    return sum(
        1
        for player in roster
        if player.get("group") == group
    )


# =========================================================
# 선수 영입 가능 여부
# =========================================================

def _can_take_player(
    state,
    side,
    player
):

    group = player.get("group")

    if group not in state["limits"]:
        return False

    current = _position_count(
        state["rosters"][side],
        group
    )

    limit = state["limits"][group]

    return current < limit


# =========================================================
# 필요한 선수풀 수
# =========================================================

def _required_pool_count(limits):

    return sum(
        value
        for value in limits.values()
    ) * 2


# =========================================================
# 선수풀 충분한지 검사
# =========================================================

def _validate_pool(
    players,
    limits
):

    required = _required_pool_count(
        limits
    )

    usable = [
        p
        for p in players
        if p.get("group") in limits
    ]

    counts = {}

    for group in limits:

        counts[group] = sum(
            1
            for p in usable
            if p.get("group") == group
        )

    problems = []

    for group, need_per_team in limits.items():

        need = need_per_team * 2

        have = counts.get(
            group,
            0
        )

        if have < need:

            problems.append(
                f"{group} 선수 풀이 부족합니다. "
                f"필요 {need}명 / 보유 {have}명"
            )

    if problems:
        return False, problems

    if len(usable) < required:

        return (
            False,
            [
                f"전체 선수 풀이 부족합니다. "
                f"필요 {required}명 / 보유 {len(usable)}명"
            ]
        )

    return True, []


# =========================================================
# 선수풀 구성
# =========================================================

def _build_pool(
    players,
    limits
):

    usable = [
        deepcopy(p)
        for p in players
        if p.get("group") in limits
    ]

    # 같은 포지션 안에서 랭크 기준으로 정렬
    # 이후 전체 순서를 랜덤화한다.
    random.shuffle(
        usable
    )

    return usable


# =========================================================
# 게임 생성
# =========================================================

def _create_game(
    form
):

    players = _load_player_pool()

    limits = _get_limits(
        form
    )

    ok, problems = _validate_pool(
        players,
        limits
    )

    if not ok:

        return None, problems

    start_money = max(
        1,
        _get_int(
            form,
            "money",
            DEFAULT_START_MONEY
        )
    )

    player_a = (
        form.get("player_a")
        or DEFAULT_PLAYER_NAMES["a"]
    ).strip()

    player_b = (
        form.get("player_b")
        or DEFAULT_PLAYER_NAMES["b"]
    ).strip()

    if not player_a:
        player_a = "PLAYER A"

    if not player_b:
        player_b = "PLAYER B"

    game_id = uuid.uuid4().hex

    pool = _build_pool(
        players,
        limits
    )

    state = {

        # 참가자
        "players": {
            "a": player_a,
            "b": player_b,
        },

        # 돈
        "money": {
            "a": start_money,
            "b": start_money,
        },

        "start_money": start_money,

        # 사용한 돈
        "spent": {
            "a": 0,
            "b": 0,
        },

        # 로스터
        "rosters": {
            "a": [],
            "b": [],
        },

        # 제한
        "limits": limits,

        # 전체 로스터 크기
        "roster_size": _roster_size(
            limits
        ),

        # 남은 선수
        "pool": pool,

        # 현재 선수
        "current": None,

        # 현재 경매가
        "bid": 0,

        # 현재 최고 입찰자
        "leader": None,

        # 누가 다음에 행동해야 하는가
        #
        # 첫 경매:
        # None
        #
        # 첫 제시가 발생하면
        # 상대방이 turn
        "turn": None,

        # 첫 제시가 누구였는지
        "opening_bidder": None,

        # ALL-IN 선언 여부
        "all_in_side": None,

        # 두 명 모두 패스했는지
        "passes": set(),

        # 로그
        "log": [],

        # 종료 여부
        "finished": False,

        # 결과
        "winner": None,
    }

    DRAFT_GAMES[game_id] = state

    _start_next_player(
        state
    )

    return game_id, []


# =========================================================
# 다음 선수 등장
# =========================================================

def _start_next_player(
    state
):

    # 이미 종료
    if state["finished"]:
        return

    # 두 팀 모두 완성
    if (
        len(state["rosters"]["a"])
        >= state["roster_size"]
        and
        len(state["rosters"]["b"])
        >= state["roster_size"]
    ):

        _finish_game(
            state
        )

        return

    # 남은 선수가 없으면 종료
    if not state["pool"]:

        _finish_game(
            state
        )

        return

    # 자동 배정
    _auto_assign_if_possible(
        state
    )

    if state["finished"]:
        return

    if not state["pool"]:
        _finish_game(state)
        return

    # 현재 선수
    state["current"] = state["pool"].pop(
        0
    )

    state["bid"] = 0

    state["leader"] = None

    state["turn"] = None

    state["opening_bidder"] = None

    state["all_in_side"] = None

    state["passes"] = set()

    state["log"].append(
        "새로운 선수가 경매에 등장했습니다."
    )


# =========================================================
# 자동 배정
# =========================================================

def _auto_assign_if_possible(
    state
):

    changed = True

    while changed:

        changed = False

        if not state["pool"]:
            return

        # 남은 선수 중 특정 포지션만 필요한 경우
        #
        # 한쪽이 해당 포지션을 전부 채웠으면
        # 그 포지션 선수는 상대에게 갈 수 있다.
        #
        # 단, 양쪽 모두 꽉 찼으면
        # 해당 선수는 풀 뒤로 보낸다.

        for index, player in enumerate(
            list(state["pool"])
        ):

            group = player.get(
                "group"
            )

            if group not in state["limits"]:
                continue

            a_full = (
                _position_count(
                    state["rosters"]["a"],
                    group
                )
                >= state["limits"][group]
            )

            b_full = (
                _position_count(
                    state["rosters"]["b"],
                    group
                )
                >= state["limits"][group]
            )

            if a_full and not b_full:

                state["pool"].pop(index)

                _give_player(
                    state,
                    "b",
                    player,
                    0
                )

                state["log"].append(
                    f"{player['name']} → "
                    f"{state['players']['b']} "
                    f"(포지션 제한으로 자동 배정)"
                )

                changed = True
                break

            if b_full and not a_full:

                state["pool"].pop(index)

                _give_player(
                    state,
                    "a",
                    player,
                    0
                )

                state["log"].append(
                    f"{player['name']} → "
                    f"{state['players']['a']} "
                    f"(포지션 제한으로 자동 배정)"
                )

                changed = True
                break


# =========================================================
# 선수 지급
# =========================================================

def _give_player(
    state,
    side,
    player,
    price
):

    player = deepcopy(
        player
    )

    state["rosters"][side].append(
        player
    )

    price = max(
        0,
        int(price)
    )

    state["spent"][side] += price

    state["money"][side] -= price


# =========================================================
# 경매 종료
# =========================================================

def _finish_auction(
    state
):

    player = state.get(
        "current"
    )

    if not player:
        return

    leader = state.get(
        "leader"
    )

    # 아무도 입찰하지 않음
    if leader is None:

        state["log"].append(
            f"{player['name']} "
            f"→ 아무도 원하지 않아 "
            f"선수풀 맨 뒤로 이동"
        )

        state["pool"].append(
            player
        )

        state["current"] = None

        _start_next_player(
            state
        )

        return

    price = state["bid"]

    _give_player(
        state,
        leader,
        player,
        price
    )

    state["log"].append(
        f"{player['name']} → "
        f"{state['players'][leader]} "
        f"${price}"
    )

    state["current"] = None

    _start_next_player(
        state
    )


# =========================================================
# 게임 종료
# =========================================================

def _finish_game(
    state
):

    if state["finished"]:
        return

    state["finished"] = True

    a_count = len(
        state["rosters"]["a"]
    )

    b_count = len(
        state["rosters"]["b"]
    )

    if (
        a_count >= state["roster_size"]
        and
        b_count >= state["roster_size"]
    ):

        a_ovr = sum(
            p.get("overall", 0)
            for p in state["rosters"]["a"]
        )

        b_ovr = sum(
            p.get("overall", 0)
            for p in state["rosters"]["b"]
        )

        if a_ovr > b_ovr:
            state["winner"] = "a"

        elif b_ovr > a_ovr:
            state["winner"] = "b"

        else:
            # OVR까지 같으면
            # 남은 돈이 많은 쪽
            if (
                state["money"]["a"]
                >
                state["money"]["b"]
            ):
                state["winner"] = "a"

            elif (
                state["money"]["b"]
                >
                state["money"]["a"]
            ):
                state["winner"] = "b"

            else:
                state["winner"] = "draw"


# =========================================================
# 현재 선수 자동 종료 체크
# =========================================================

def _check_current_player_valid(
    state
):

    player = state.get(
        "current"
    )

    if not player:
        return True, ""

    # 양쪽 모두 해당 포지션을 다 채운 경우
    # 이 선수는 다시 풀 뒤로 보낼 수 있다.
    group = player.get(
        "group"
    )

    if group not in state["limits"]:
        return (
            False,
            "알 수 없는 포지션의 선수입니다."
        )

    a_full = (
        _position_count(
            state["rosters"]["a"],
            group
        )
        >= state["limits"][group]
    )

    b_full = (
        _position_count(
            state["rosters"]["b"],
            group
        )
        >= state["limits"][group]
    )

    if a_full and b_full:

        player = state["current"]

        state["current"] = None

        state["pool"].append(
            player
        )

        state["log"].append(
            f"{player['name']} → "
            f"양 팀의 {group} 자리가 모두 차서 "
            f"선수풀 뒤로 이동"
        )

        _start_next_player(
            state
        )

        return (
            False,
            ""
        )

    return True, ""


# =========================================================
# /draft
# =========================================================

@draft_bp.route(
    "/draft",
    methods=["GET"]
)
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# =========================================================
# 게임 생성
# =========================================================

@draft_bp.route(
    "/draft/start",
    methods=["POST"]
)
def draft_start():

    try:

        game_id, errors = _create_game(
            request.form
        )

    except Exception as e:

        return render_template(
            "draft_setup.html",
            error=str(e)
        )

    if errors:

        return render_template(
            "draft_setup.html",
            error="<br>".join(
                errors
            )
        )

    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# =========================================================
# 게임 화면
# =========================================================

@draft_bp.route(
    "/draft/game/<game_id>",
    methods=["GET"]
)
def game(game_id):

    state = DRAFT_GAMES.get(
        game_id
    )

    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )

    return render_template(
        "draft_game.html",
        state=state,
        game_id=game_id,
        save_id=game_id,
        error=None
    )


# =========================================================
# 액션
# =========================================================

@draft_bp.route(
    "/draft/game/<game_id>/action",
    methods=["POST"]
)
def action(game_id):

    state = DRAFT_GAMES.get(
        game_id
    )

    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )

    if state["finished"]:

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    side = request.form.get(
        "side"
    )

    action_type = request.form.get(
        "action"
    )

    if side not in {
        "a",
        "b"
    }:

        return render_template(
            "draft_game.html",
            state=state,
            game_id=game_id,
            save_id=game_id,
            error="잘못된 플레이어입니다."
        )

    # 현재 선수 확인
    valid, message = (
        _check_current_player_valid(
            state
        )
    )

    if not valid:

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    current = state.get(
        "current"
    )

    if current is None:

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    # =====================================================
    # PASS
    # =====================================================

    if action_type == "pass":

        # 아직 아무도 입찰하지 않은 상태
        if state["leader"] is None:

            state["passes"].add(
                side
            )

            state["log"].append(
                f"{state['players'][side]} "
                f"PASS"
            )

            # 둘 다 PASS
            if len(
                state["passes"]
            ) >= 2:

                _finish_auction(
                    state
                )

            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )

        # 이미 누군가 입찰했다면
        # 현재 리더가 아닌 사람이 PASS
        #
        # → 경매 종료
        if side != state["leader"]:

            state["log"].append(
                f"{state['players'][side]} "
                f"PASS → "
                f"{state['players'][state['leader']]} "
                f"낙찰"
            )

            _finish_auction(
                state
            )

            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )

        return render_template(
            "draft_game.html",
            state=state,
            game_id=game_id,
            save_id=game_id,
            error="현재 선두 입찰자는 PASS할 수 없습니다."
        )

    # =====================================================
    # 입찰 금액
    # =====================================================

    if action_type in {
        "bid",
        "allin"
    }:

        money = state["money"][side]

        # 이미 선두인 사람이 다시 입찰하는 것 방지
        if (
            state["leader"] == side
        ):

            return render_template(
                "draft_game.html",
                state=state,
                game_id=game_id,
                save_id=game_id,
                error="현재 최고 입찰자입니다. 상대방의 제시를 기다리세요."
            )

        # 첫 제시
        if state["leader"] is None:

            if action_type == "allin":

                amount = money

                if amount <= 0:

                    return render_template(
                        "draft_game.html",
                        state=state,
                        game_id=game_id,
                        save_id=game_id,
                        error="사용할 수 있는 금액이 없습니다."
                    )

            else:

                amount = _to_int(
                    request.form.get(
                        "amount"
                    ),
                    0
                )

                if amount <= 0:

                    return render_template(
                        "draft_game.html",
                        state=state,
                        game_id=game_id,
                        save_id=game_id,
                        error="제시 금액을 입력하세요."
                    )

            if amount > money:

                return render_template(
                    "draft_game.html",
                    state=state,
                    game_id=game_id,
                    save_id=game_id,
                    error=f"보유 금액은 ${money}입니다."
                )

            # 첫 제시는 최소 $1
            if amount < 1:

                return render_template(
                    "draft_game.html",
                    state=state,
                    game_id=game_id,
                    save_id=game_id,
                    error="최소 제시 금액은 $1입니다."
                )

            state["bid"] = amount

            state["leader"] = side

            state["opening_bidder"] = side

            state["turn"] = (
                "b"
                if side == "a"
                else "a"
            )

            if action_type == "allin":

                state["all_in_side"] = side

                state["log"].append(
                    f"{state['players'][side]} "
                    f"ALL-IN ${amount}"
                )

            else:

                state["log"].append(
                    f"{state['players'][side]} "
                    f"${amount} 제시"
                )

            # 상대가 더 이상 돈이 없으면
            # 현재 입찰자가 자동 낙찰
            opponent = (
                "b"
                if side == "a"
                else "a"
            )

            if state["money"][opponent] < amount:

                _finish_auction(
                    state
                )

            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )

        # =================================================
        # 두 번째 이후 입찰
        # =================================================

        current_bid = state["bid"]

        if action_type == "allin":

            amount = money

        else:

            amount = _to_int(
                request.form.get(
                    "amount"
                ),
                0
            )

        if amount <= current_bid:

            return render_template(
                "draft_game.html",
                state=state,
                game_id=game_id,
                save_id=game_id,
                error=f"현재가 ${current_bid}보다 높은 금액을 제시해야 합니다."
            )

        if amount > money:

            return render_template(
                "draft_game.html",
                state=state,
                game_id=game_id,
                save_id=game_id,
                error=f"보유 금액은 ${money}입니다."
            )

        # 새 선두
        state["bid"] = amount

        state["leader"] = side

        state["turn"] = (
            "b"
            if side == "a"
            else "a"
        )

        if action_type == "allin":

            state["all_in_side"] = side

            state["log"].append(
                f"{state['players'][side]} "
                f"ALL-IN ${amount}"
            )

            # =================================================
            # 동일 금액 ALL-IN
            # =================================================
            #
            # 상대도 같은 금액으로 ALL-IN 가능.
            #
            # 이 경우 먼저 ALL-IN을 선언한 쪽이 승리.
            #

        else:

            state["all_in_side"] = None

            state["log"].append(
                f"{state['players'][side]} "
                f"${amount} 제시"
            )

        opponent = (
            "b"
            if side == "a"
            else "a"
        )

        # 상대가 현재가보다 높은 금액을 낼 수 없으면
        # 자동 낙찰
        if state["money"][opponent] <= amount:

            _finish_auction(
                state
            )

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    # =====================================================
    # 잘못된 액션
    # =====================================================

    return render_template(
        "draft_game.html",
        state=state,
        game_id=game_id,
        save_id=game_id,
        error="알 수 없는 경매 액션입니다."
    )


# =========================================================
# 결과
# =========================================================

@draft_bp.route(
    "/draft/game/<game_id>/result",
    methods=["GET"]
)
def result(game_id):

    state = DRAFT_GAMES.get(
        game_id
    )

    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )

    return render_template(
        "draft_result.html",
        state=state,
        game_id=game_id
    )
