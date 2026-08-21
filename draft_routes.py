# ============================================================
# Draft Mode
# draft_routes.py
#
# 경매 방식
#
# 1. 현재 선수만 공개
# 2. A/B 누구든 먼저 BID 또는 ALL-IN을 누를 수 있음
# 3. 첫 번째로 누른 사람이 선공자가 됨
# 4. 이후에는 양쪽이 번갈아 행동
# 5. PASS
# 6. 둘 다 PASS -> 선수풀 맨 뒤로 이동
# 7. ALL-IN
# 8. 같은 금액 ALL-IN -> 먼저 ALL-IN한 쪽 승리
# 9. 다음 선수는 공개하지 않음
#
# ============================================================

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
import uuid
import random
import copy


# ============================================================
# BLUEPRINT
# ============================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# PLAYER POOL
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYER_POOL_PATH = os.path.join(
    BASE_DIR,
    "player_pool.json"
)


# ============================================================
# 기본값
# ============================================================

DEFAULT_POSITION_LIMITS = {
    "선발": 2,
    "불펜": 2,
    "마무리": 1,
    "포수": 1,
    "내야수": 2,
    "외야수": 2
}


DEFAULT_GROUP_ALIASES = {
    "선발": "선발",
    "SP": "선발",
    "starter": "선발",
    "STARTER": "선발",

    "불펜": "불펜",
    "RP": "불펜",
    "reliever": "불펜",
    "RELIEVER": "불펜",

    "마무리": "마무리",
    "CP": "마무리",
    "closer": "마무리",
    "CLOSER": "마무리",

    "포수": "포수",
    "C": "포수",
    "catcher": "포수",
    "CATCHER": "포수",

    "내야수": "내야수",
    "내야": "내야수",
    "IF": "내야수",
    "INF": "내야수",
    "infielder": "내야수",
    "INFIELDER": "내야수",

    "외야수": "외야수",
    "외야": "외야수",
    "OF": "외야수",
    "outfielder": "외야수",
    "OUTFIELDER": "외야수",

    "투수": "선발",
    "P": "선발"
}


# ============================================================
# 메모리 저장소
#
# Render에서 여러 worker를 사용할 경우 DB 저장이 필요하지만,
# 현재 Draft 테스트/구조용으로는 이 방식으로 동작한다.
# ============================================================

GAMES = {}


# ============================================================
# PLAYER POOL LOAD
# ============================================================

def load_player_pool():

    if not os.path.exists(PLAYER_POOL_PATH):

        raise FileNotFoundError(
            f"player_pool.json을 찾을 수 없습니다: "
            f"{PLAYER_POOL_PATH}"
        )

    with open(
        PLAYER_POOL_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)


    # --------------------------------------------------------
    # JSON 구조 대응
    # --------------------------------------------------------

    if isinstance(data, dict):

        if "players" in data:
            data = data["players"]

        elif "player_pool" in data:
            data = data["player_pool"]

        elif "data" in data:
            data = data["data"]

        else:

            # dict 안에 선수들이 직접 들어있는 경우
            values = list(data.values())

            if values and all(
                isinstance(x, dict)
                for x in values
            ):
                data = values


    if not isinstance(data, list):

        raise ValueError(
            "player_pool.json의 선수 데이터 형식을 "
            "확인해주세요."
        )


    result = []


    for index, raw in enumerate(data):

        if not isinstance(raw, dict):
            continue


        player = normalize_player(
            raw,
            index
        )


        if player:
            result.append(player)


    return result


# ============================================================
# PLAYER NORMALIZE
# ============================================================

def normalize_player(raw, index):

    raw = dict(raw)


    # --------------------------------------------------------
    # 이름
    # --------------------------------------------------------

    name = (
        raw.get("name")
        or raw.get("player_name")
        or raw.get("선수명")
        or raw.get("선수")
        or raw.get("이름")
    )


    if not name:
        return None


    # --------------------------------------------------------
    # 팀
    # --------------------------------------------------------

    team = (
        raw.get("team")
        or raw.get("팀")
        or raw.get("club")
        or ""
    )


    # --------------------------------------------------------
    # 포지션
    # --------------------------------------------------------

    position = (
        raw.get("position")
        or raw.get("pos")
        or raw.get("포지션")
        or raw.get("position_name")
        or ""
    )


    # --------------------------------------------------------
    # 역할
    # --------------------------------------------------------

    role = (
        raw.get("group")
        or raw.get("role")
        or raw.get("pitcher_type")
        or raw.get("투수유형")
        or raw.get("투수 유형")
        or raw.get("구분")
        or ""
    )


    position_text = str(position).strip()
    role_text = str(role).strip()


    # --------------------------------------------------------
    # 그룹 결정
    # --------------------------------------------------------

    group = None


    if role_text in DEFAULT_GROUP_ALIASES:
        group = DEFAULT_GROUP_ALIASES[role_text]


    if position_text in DEFAULT_GROUP_ALIASES:
        group = DEFAULT_GROUP_ALIASES[position_text]


    combined = (
        f"{position_text} "
        f"{role_text}"
    ).lower()


    if group is None:

        if "마무리" in combined or "closer" in combined:
            group = "마무리"

        elif "불펜" in combined or "reliever" in combined:
            group = "불펜"

        elif "선발" in combined or "starter" in combined:
            group = "선발"

        elif (
            "포수" in combined
            or position_text.upper() == "C"
        ):
            group = "포수"

        elif (
            "내야" in combined
            or position_text.upper() in ("IF", "INF")
        ):
            group = "내야수"

        elif (
            "외야" in combined
            or position_text.upper() == "OF"
        ):
            group = "외야수"


    # --------------------------------------------------------
    # 투수라고만 되어 있는 경우
    # 기본적으로 선발로 처리
    # --------------------------------------------------------

    if group == "투수":
        group = "선발"


    if group is None:

        # 포지션 자체가 P인 경우
        if position_text.upper() == "P":
            group = "선발"


    # --------------------------------------------------------
    # OVR
    # --------------------------------------------------------

    overall_raw = (
        raw.get("overall")
        or raw.get("ovr")
        or raw.get("OVR")
        or raw.get("능력치")
        or raw.get("종합")
        or 0
    )


    try:
        overall = int(float(overall_raw))
    except Exception:
        overall = 0


    # --------------------------------------------------------
    # pitcher_type
    # --------------------------------------------------------

    pitcher_type = None

    if group in (
        "선발",
        "불펜",
        "마무리"
    ):
        pitcher_type = group


    # --------------------------------------------------------
    # 실제 포지션 표시
    # --------------------------------------------------------

    display_position = position_text

    if not display_position:

        display_position = group or "미정"


    # --------------------------------------------------------
    # 내부 ID
    # --------------------------------------------------------

    player_id = (
        raw.get("id")
        or raw.get("player_id")
        or f"draft_player_{index}"
    )


    return {
        "id": str(player_id),
        "name": str(name),
        "team": str(team),
        "position": str(display_position),
        "group": group or "기타",
        "pitcher_type": pitcher_type,
        "overall": overall
    }


# ============================================================
# 포지션별 선수 확인
# ============================================================

def count_available_players(
    players,
    group
):

    return sum(
        1
        for p in players
        if p.get("group") == group
    )


# ============================================================
# 선수풀 검증
# ============================================================

def validate_pool(
    players,
    limits
):

    errors = []


    for group, need in limits.items():

        available = count_available_players(
            players,
            group
        )


        if available < need:

            errors.append(
                f"{group} 선수 풀이 부족합니다. "
                f"필요 {need}명 / 보유 {available}명"
            )


    return errors


# ============================================================
# 로스터에 들어갈 수 있는지
# ============================================================

def can_add_player(
    state,
    side,
    player
):

    group = player.get("group")


    if group not in state["limits"]:

        return False, "등록할 수 없는 포지션입니다."


    roster = state["rosters"][side]


    current = sum(
        1
        for p in roster
        if p.get("group") == group
    )


    limit = state["limits"][group]


    if current >= limit:

        return False, (
            f"{group} 포지션이 이미 "
            f"{limit}명으로 가득 찼습니다."
        )


    if len(roster) >= state["roster_size"]:

        return False, "로스터가 가득 찼습니다."


    return True, None


# ============================================================
# 게임 생성
# ============================================================

def create_game(
    player_a="PLAYER A",
    player_b="PLAYER B",
    initial_money=10,
    limits=None
):

    players = load_player_pool()


    if limits is None:

        limits = dict(
            DEFAULT_POSITION_LIMITS
        )


    # --------------------------------------------------------
    # 필요한 총 선수 수
    # --------------------------------------------------------

    required_per_player = sum(
        int(x)
        for x in limits.values()
    )


    required_total = (
        required_per_player * 2
    )


    # --------------------------------------------------------
    # 선수풀 전체에서 필요한 만큼 랜덤 추출
    #
    # 단, 포지션별 조건을 만족하도록 추출
    # --------------------------------------------------------

    selected = []


    for group, count in limits.items():

        candidates = [
            p
            for p in players
            if p.get("group") == group
        ]


        if len(candidates) < count * 2:

            raise ValueError(
                f"{group} 선수 풀이 부족합니다. "
                f"필요 {count * 2}명 / "
                f"보유 {len(candidates)}명"
            )


        random.shuffle(candidates)


        selected.extend(
            candidates[:count * 2]
        )


    random.shuffle(selected)


    # --------------------------------------------------------
    # 게임 ID
    # --------------------------------------------------------

    game_id = uuid.uuid4().hex


    # --------------------------------------------------------
    # 현재 선수
    # --------------------------------------------------------

    current = selected.pop(0)


    # --------------------------------------------------------
    # 상태
    # --------------------------------------------------------

    state = {

        "players": {
            "a": player_a,
            "b": player_b
        },


        "money": {
            "a": int(initial_money),
            "b": int(initial_money)
        },


        "spent": {
            "a": 0,
            "b": 0
        },


        "rosters": {
            "a": [],
            "b": []
        },


        "roster_size": required_per_player,


        "limits": dict(limits),


        # 남은 선수
        # 브라우저에 절대 공개하지 않는다.
        "pool": selected,


        # 현재 선수
        "current": current,


        # 현재 경매가
        "bid": 0,


        # 현재 최고 입찰자
        "leader": None,


        # 다음 행동 차례
        #
        # 중요:
        # 처음에는 None.
        # A/B 중 누가 먼저 버튼을 누르느냐에 따라 결정.
        "turn": None,


        # 이번 경매에서 처음 행동한 사람
        "first_bidder": None,


        # PASS 여부
        "passed": {
            "a": False,
            "b": False
        },


        # ALL-IN 여부
        "all_in": {
            "a": False,
            "b": False
        },


        # ALL-IN 행동 순서
        "all_in_order": [],


        # 로그
        "log": [
            "새로운 Draft가 시작되었습니다."
        ],


        # 게임 종료
        "finished": False,


        # 결과
        "winner": None
    }


    GAMES[game_id] = state


    return game_id


# ============================================================
# 게임 가져오기
# ============================================================

def get_game(game_id):

    return GAMES.get(game_id)


# ============================================================
# 다음 선수
# ============================================================

def next_player(state):

    if not state["pool"]:

        state["current"] = None
        state["finished"] = True

        state["turn"] = None
        state["leader"] = None

        return


    state["current"] = state["pool"].pop(0)


    # 새 경매 시작
    state["bid"] = 0
    state["leader"] = None

    # 중요
    #
    # 이전 선수의 선공자를 기억하지 않는다.
    #
    # 다음 선수도 다시
    # "누가 먼저 누르느냐"로 결정.
    state["turn"] = None

    state["first_bidder"] = None

    state["passed"] = {
        "a": False,
        "b": False
    }

    state["all_in"] = {
        "a": False,
        "b": False
    }

    state["all_in_order"] = []


# ============================================================
# 선수 배정
# ============================================================

def award_player(
    state,
    side,
    price
):

    player = state["current"]


    if not player:
        return False


    state["rosters"][side].append(
        copy.deepcopy(player)
    )


    state["money"][side] -= price

    state["spent"][side] += price


    state["log"].append(
        f"{state['players'][side]}이(가) "
        f"{player['name']}을(를) "
        f"${price}에 영입했습니다."
    )


    next_player(state)


    return True


# ============================================================
# 상대쪽
# ============================================================

def other_side(side):

    return "b" if side == "a" else "a"


# ============================================================
# 현재 상태에서 상대가 행동할 수 있는지
# ============================================================

def player_can_act(
    state,
    side
):

    if state["finished"]:
        return False


    if not state["current"]:
        return False


    # --------------------------------------------------------
    # 첫 행동
    #
    # A/B 모두 가능
    # --------------------------------------------------------

    if state["turn"] is None:
        return True


    return state["turn"] == side


# ============================================================
# BID
# ============================================================

def process_bid(
    state,
    side
):

    if not player_can_act(
        state,
        side
    ):

        return (
            False,
            "현재는 이 플레이어의 차례가 아닙니다."
        )


    money = state["money"][side]


    next_bid = state["bid"] + 1


    if money < next_bid:

        return (
            False,
            "입찰할 자금이 부족합니다."
        )


    # --------------------------------------------------------
    # 첫 번째 입찰자
    # --------------------------------------------------------

    if state["first_bidder"] is None:

        state["first_bidder"] = side

        state["leader"] = side

        state["turn"] = other_side(side)

        state["bid"] = next_bid

        state["passed"][side] = False


        state["log"].append(
            f"{state['players'][side]}이(가) "
            f"{state['current']['name']}에게 "
            f"처음 ${next_bid}을 제시했습니다."
        )

        return True, None


    # --------------------------------------------------------
    # 정상적인 추가 입찰
    # --------------------------------------------------------

    state["bid"] = next_bid

    state["leader"] = side

    state["passed"][side] = False

    state["turn"] = other_side(side)


    state["log"].append(
        f"{state['players'][side]}이(가) "
        f"${next_bid}을 제시했습니다."
    )


    return True, None


# ============================================================
# ALL-IN
# ============================================================

def process_allin(
    state,
    side
):

    if not player_can_act(
        state,
        side
    ):

        return (
            False,
            "현재는 이 플레이어의 차례가 아닙니다."
        )


    money = state["money"][side]


    if money <= state["bid"]:

        return (
            False,
            "현재가보다 높은 금액을 ALL-IN해야 합니다."
        )


    all_in_price = money


    # --------------------------------------------------------
    # 처음 ALL-IN
    # --------------------------------------------------------

    if state["first_bidder"] is None:

        state["first_bidder"] = side


    state["bid"] = all_in_price

    state["leader"] = side

    state["all_in"][side] = True


    if side not in state["all_in_order"]:

        state["all_in_order"].append(side)


    state["log"].append(
        f"{state['players'][side]}이(가) "
        f"${all_in_price} ALL-IN!"
    )


    opponent = other_side(side)


    # --------------------------------------------------------
    # 상대가 이미 ALL-IN
    #
    # 둘 다 ALL-IN이면
    #
    # 먼저 ALL-IN한 사람이 승리
    # --------------------------------------------------------

    if state["all_in"].get(opponent):

        winner = state["all_in_order"][0]


        price = state["bid"]


        award_player(
            state,
            winner,
            price
        )


        state["log"].append(
            f"동일 ALL-IN 상황에서 "
            f"{state['players'][winner]}이(가) "
            f"먼저 ALL-IN하여 승리했습니다."
        )


        return True, None


    # --------------------------------------------------------
    # 상대가 아직 ALL-IN하지 않은 경우
    # 상대가 대응해야 함
    # --------------------------------------------------------

    state["turn"] = opponent


    return True, None


# ============================================================
# PASS
# ============================================================

def process_pass(
    state,
    side
):

    if not player_can_act(
        state,
        side
    ):

        return (
            False,
            "현재는 이 플레이어의 차례가 아닙니다."
        )


    opponent = other_side(side)


    # --------------------------------------------------------
    # 아무도 입찰하지 않은 상태
    # --------------------------------------------------------

    if state["bid"] == 0:

        state["passed"][side] = True


        state["log"].append(
            f"{state['players'][side]}이(가) PASS했습니다."
        )


        # 둘 다 PASS
        if state["passed"][opponent]:

            state["log"].append(
                f"{state['current']['name']}은(는) "
                f"두 플레이어 모두 PASS하여 "
                f"선수풀 뒤로 이동합니다."
            )


            player = state["current"]

            state["pool"].append(
                player
            )


            next_player(state)


            return True, None


        # 상대가 먼저 행동해야 함
        state["turn"] = opponent


        return True, None


    # --------------------------------------------------------
    # 이미 누군가 입찰
    #
    # PASS하면 현재 선두에게 낙찰
    # --------------------------------------------------------

    if state["leader"]:

        winner = state["leader"]

        price = state["bid"]


        award_player(
            state,
            winner,
            price
        )


        state["log"].append(
            f"{state['players'][side]}이(가) PASS하여 "
            f"{state['players'][winner]}에게 "
            f"낙찰되었습니다."
        )


        return True, None


    return False, "PASS 처리 중 오류가 발생했습니다."


# ============================================================
# ACTION
# ============================================================

def process_action(
    state,
    side,
    action
):

    if state["finished"]:

        return (
            False,
            "이미 경매가 종료되었습니다."
        )


    if side not in ("a", "b"):

        return (
            False,
            "잘못된 플레이어입니다."
        )


    if action == "bid":

        return process_bid(
            state,
            side
        )


    if action in (
        "allin",
        "all_in"
    ):

        return process_allin(
            state,
            side
        )


    if action == "pass":

        return process_pass(
            state,
            side
        )


    return (
        False,
        "알 수 없는 행동입니다."
    )


# ============================================================
# 상태 정리
#
# pool은 절대 template으로 보내지 않는다.
# ============================================================

def public_state(state):

    result = {
        "players": copy.deepcopy(
            state["players"]
        ),

        "money": copy.deepcopy(
            state["money"]
        ),

        "spent": copy.deepcopy(
            state["spent"]
        ),

        "rosters": copy.deepcopy(
            state["rosters"]
        ),

        "roster_size": state["roster_size"],

        "limits": copy.deepcopy(
            state["limits"]
        ),

        "current": copy.deepcopy(
            state["current"]
        ),

        "bid": state["bid"],

        "leader": state["leader"],

        "turn": state["turn"],

        "first_bidder": state["first_bidder"],

        "log": list(
            state["log"]
        ),

        "finished": state["finished"],

        "winner": state["winner"]
    }


    return result


# ============================================================
# /draft
#
# 시작 화면
# ============================================================

@draft_bp.route("/")
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# ============================================================
# /draft/start
#
# 게임 생성
# ============================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    try:

        player_a = (
            request.form.get(
                "player_a"
            )
            or "PLAYER A"
        )


        player_b = (
            request.form.get(
                "player_b"
            )
            or "PLAYER B"
        )


        initial_money = int(
            request.form.get(
                "initial_money",
                10
            )
        )


        # ----------------------------------------------------
        # 포지션 제한
        # ----------------------------------------------------

        limits = {

            "선발": int(
                request.form.get(
                    "starter",
                    2
                )
            ),

            "불펜": int(
                request.form.get(
                    "bullpen",
                    2
                )
            ),

            "마무리": int(
                request.form.get(
                    "closer",
                    1
                )
            ),

            "포수": int(
                request.form.get(
                    "catcher",
                    1
                )
            ),

            "내야수": int(
                request.form.get(
                    "infielder",
                    2
                )
            ),

            "외야수": int(
                request.form.get(
                    "outfielder",
                    2
                )
            )
        }


        # ----------------------------------------------------
        # 최소값 검사
        # ----------------------------------------------------

        if initial_money <= 0:

            return render_template(
                "draft_setup.html",
                error="초기 자본은 1달러 이상이어야 합니다."
            )


        for group, count in limits.items():

            if count < 0:

                return render_template(
                    "draft_setup.html",
                    error=f"{group} 인원은 0 이상이어야 합니다."
                )


        # ----------------------------------------------------
        # 선수풀 확인
        # ----------------------------------------------------

        players = load_player_pool()


        errors = validate_pool(
            players,
            limits
        )


        if errors:

            return render_template(
                "draft_setup.html",
                error=" / ".join(errors)
            )


        # ----------------------------------------------------
        # 게임 생성
        # ----------------------------------------------------

        game_id = create_game(
            player_a=player_a,
            player_b=player_b,
            initial_money=initial_money,
            limits=limits
        )


        # ----------------------------------------------------
        # 세션
        # ----------------------------------------------------

        session["draft_game_id"] = game_id


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    except ValueError:

        return render_template(
            "draft_setup.html",
            error="입력값을 확인해주세요."
        )


    except Exception as e:

        return render_template(
            "draft_setup.html",
            error=str(e)
        )


# ============================================================
# /draft/game/<game_id>
#
# 게임 화면
# ============================================================

@draft_bp.route(
    "/game/<game_id>",
    methods=["GET"]
)
def game(game_id):

    state = get_game(
        game_id
    )


    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    return render_template(
        "draft_game.html",

        state=public_state(
            state
        ),

        game_id=game_id,

        save_id=game_id,

        error=None
    )


# ============================================================
# /draft/game/<game_id>/action
#
# 경매 행동
# ============================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(game_id):

    state = get_game(
        game_id
    )


    if state is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    side = (
        request.form.get(
            "side"
        )
        or ""
    )


    action_type = (
        request.form.get(
            "action"
        )
        or ""
    )


    success, error = process_action(
        state,
        side,
        action_type
    )


    if not success:

        return render_template(
            "draft_game.html",

            state=public_state(
                state
            ),

            game_id=game_id,

            save_id=game_id,

            error=error
        )


    # --------------------------------------------------------
    # 게임 종료
    # --------------------------------------------------------

    if state["finished"]:

        state["winner"] = calculate_winner(
            state
        )


        return redirect(
            url_for(
                "draft.game",
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
# 승자 계산
# ============================================================

def calculate_winner(state):

    a_score = 0
    b_score = 0


    for p in state["rosters"]["a"]:
        a_score += int(
            p.get(
                "overall",
                0
            )
        )


    for p in state["rosters"]["b"]:
        b_score += int(
            p.get(
                "overall",
                0
            )
        )


    if a_score > b_score:
        return "a"

    if b_score > a_score:
        return "b"

    return "draw"
