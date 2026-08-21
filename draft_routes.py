# ============================================================
# draft_routes.py
# Draft Mode
#
# 포지션
#   선발 / 불펜 / 마무리 / 내야 / 외야 / 포수
#
# 게임
#   1 VS 1 비공개 경매
#   선수풀은 설정 인원의 2배
#   경매 순서는 랜덤
#   +$1 입찰
#   ALL-IN
#   PASS
#   양쪽 모두 PASS -> 선수풀 맨 뒤
#   한쪽이 로스터를 모두 채우면 남은 선수는 상대에게
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
import random
import uuid


# ============================================================
# Blueprint
# ============================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 경로
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PLAYER_POOL_FILE = os.path.join(
    BASE_DIR,
    "player_pool.json"
)


# ============================================================
# 포지션 정의
#
# player_pool.json의 실제 position 값을 그대로 사용
# ============================================================

POSITIONS = [
    "선발",
    "불펜",
    "마무리",
    "내야",
    "외야",
    "포수",
]


POSITION_SETTINGS = {
    "선발": "starter",
    "불펜": "reliever",
    "마무리": "closer",
    "내야": "infield",
    "외야": "outfield",
    "포수": "catcher",
}


DEFAULT_SETTINGS = {

    # 초기 자본
    "money": 10,

    # 한 팀이 뽑을 인원
    "starter": 2,
    "reliever": 2,
    "closer": 1,
    "infield": 2,
    "outfield": 2,
    "catcher": 1,
}


# ============================================================
# 임시 게임 저장소
#
# 서버 재시작 전까지 유지
# ============================================================

GAMES = {}


# ============================================================
# JSON 로드
# ============================================================

def load_player_pool():

    if not os.path.exists(
        PLAYER_POOL_FILE
    ):
        raise FileNotFoundError(
            "player_pool.json 파일을 찾을 수 없습니다."
        )


    with open(
        PLAYER_POOL_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)


    # ----------------------------------------
    # [
    #   {...},
    #   {...}
    # ]
    # ----------------------------------------

    if isinstance(data, list):
        return data


    # ----------------------------------------
    # {"players": [...]}
    # ----------------------------------------

    if isinstance(data, dict):

        if isinstance(
            data.get("players"),
            list
        ):
            return data["players"]


        if isinstance(
            data.get("player_pool"),
            list
        ):
            return data["player_pool"]


        if isinstance(
            data.get("pool"),
            list
        ):
            return data["pool"]


    raise ValueError(
        "player_pool.json의 선수 데이터 형식을 인식할 수 없습니다."
    )


# ============================================================
# 선수 데이터 정규화
# ============================================================

def normalize_player(player):

    p = dict(player)


    # ----------------------------------------
    # 이름
    # ----------------------------------------

    if not p.get("name"):

        p["name"] = (
            p.get("player_name")
            or p.get("선수명")
            or "이름 없음"
        )


    # ----------------------------------------
    # 팀
    # ----------------------------------------

    if not p.get("team"):

        p["team"] = (
            p.get("팀")
            or ""
        )


    # ----------------------------------------
    # 포지션
    #
    # 중요:
    # 여기서는 포지션을 절대로
    # "투수"로 합치지 않는다.
    # ----------------------------------------

    position = (
        p.get("position")
        or p.get("pos")
        or ""
    )

    p["position"] = str(
        position
    ).strip()


    # ----------------------------------------
    # OVR
    # ----------------------------------------

    overall = (
        p.get("overall")
        or p.get("ovr")
        or p.get("rating")
        or 0
    )

    try:
        p["overall"] = int(
            overall
        )

    except (
        TypeError,
        ValueError
    ):
        p["overall"] = 0


    return p


# ============================================================
# 설정값 읽기
# ============================================================

def get_int_form(
    name,
    default,
    minimum=0
):

    value = request.form.get(
        name,
        default
    )


    try:

        value = int(value)

    except (
        TypeError,
        ValueError
    ):

        value = int(default)


    if value < minimum:
        value = minimum


    return value


# ============================================================
# 필요한 선수 수
#
# 예:
# 선발 2 -> 선수풀에는 4명
# 불펜 2 -> 선수풀에는 4명
# ...
# ============================================================

def required_counts(settings):

    return {

        position:
            int(
                settings[
                    POSITION_SETTINGS[
                        position
                    ]
                ]
            ) * 2

        for position in POSITIONS

    }


# ============================================================
# 팀당 로스터 크기
# ============================================================

def roster_size(settings):

    return sum(
        int(
            settings[
                POSITION_SETTINGS[
                    position
                ]
            ]
        )
        for position in POSITIONS
    )


# ============================================================
# 선수 풀 생성
# ============================================================

def build_player_pool(settings):

    raw_players = load_player_pool()


    players = []

    for raw in raw_players:

        if not isinstance(
            raw,
            dict
        ):
            continue

        players.append(
            normalize_player(raw)
        )


    # --------------------------------------------------------
    # 포지션별 분류
    # --------------------------------------------------------

    grouped = {
        position: []
        for position in POSITIONS
    }


    for player in players:

        position = player.get(
            "position",
            ""
        )


        # JSON에 실제로 존재하는 포지션만 사용

        if position in grouped:

            grouped[position].append(
                player
            )


    # --------------------------------------------------------
    # 필요한 수 확인
    # --------------------------------------------------------

    required = required_counts(
        settings
    )


    for position in POSITIONS:

        need = required[position]

        available = len(
            grouped[position]
        )


        if available < need:

            raise ValueError(
                f"{position} 선수 풀이 부족합니다. "
                f"필요 {need}명 / 보유 {available}명"
            )


    # --------------------------------------------------------
    # 각 포지션에서 필요한 선수만 랜덤 선택
    # --------------------------------------------------------

    pool = []


    for position in POSITIONS:

        count = required[position]


        selected = random.sample(
            grouped[position],
            count
        )


        pool.extend(
            selected
        )


    # --------------------------------------------------------
    # 전체 경매 순서 랜덤
    # --------------------------------------------------------

    random.shuffle(pool)


    return pool


# ============================================================
# 포지션별 현재 로스터 수
# ============================================================

def count_position(
    roster,
    position
):

    return sum(
        1
        for player in roster
        if player.get(
            "position"
        ) == position
    )


# ============================================================
# 포지션별 제한
# ============================================================

def get_position_limit(
    settings,
    position
):

    key = POSITION_SETTINGS.get(
        position
    )


    if not key:
        return 0


    return int(
        settings.get(
            key,
            0
        )
    )


# ============================================================
# 해당 포지션을 더 뽑을 수 있는지
# ============================================================

def position_full(
    game,
    side,
    player
):

    position = player.get(
        "position"
    )


    limit = get_position_limit(
        game["settings"],
        position
    )


    current = count_position(
        game["rosters"][side],
        position
    )


    return current >= limit


# ============================================================
# 로스터 전체가 가득 찼는지
# ============================================================

def roster_full(
    game,
    side
):

    return (
        len(
            game["rosters"][side]
        )
        >=
        roster_size(
            game["settings"]
        )
    )


# ============================================================
# 게임 종료 여부
# ============================================================

def check_finished(game):

    target = roster_size(
        game["settings"]
    )


    a_full = (
        len(
            game["rosters"]["a"]
        )
        >= target
    )


    b_full = (
        len(
            game["rosters"]["b"]
        )
        >= target
    )


    # 한 명이 먼저 다 채우면
    # 나머지 선수는 상대방에게

    if a_full and not b_full:

        remaining = []

        if game.get("current"):
            remaining.append(
                game["current"]
            )

        remaining.extend(
            game.get("pool", [])
        )

        remaining.extend(
            game.get("returned", [])
        )


        game["rosters"]["b"].extend(
            remaining
        )


        game["pool"] = []

        game["returned"] = []

        game["current"] = None

        game["finished"] = True

        game["winner"] = "a"

        return True


    if b_full and not a_full:

        remaining = []

        if game.get("current"):
            remaining.append(
                game["current"]
            )

        remaining.extend(
            game.get("pool", [])
        )

        remaining.extend(
            game.get("returned", [])
        )


        game["rosters"]["a"].extend(
            remaining
        )


        game["pool"] = []

        game["returned"] = []

        game["current"] = None

        game["finished"] = True

        game["winner"] = "b"

        return True


    if a_full and b_full:

        game["current"] = None

        game["pool"] = []

        game["returned"] = []

        game["finished"] = True

        game["winner"] = None

        return True


    return False


# ============================================================
# 다음 선수 꺼내기
# ============================================================

def next_player(game):

    if game["finished"]:
        return


    # --------------------------------------------------------
    # 현재 경매가 끝났으므로 현재 선수 제거
    # --------------------------------------------------------

    game["current"] = None

    game["bid"] = 0

    game["leader"] = None


    # --------------------------------------------------------
    # 먼저 일반 선수풀
    # --------------------------------------------------------

    if game["pool"]:

        game["current"] = game[
            "pool"
        ].pop(0)

        # 경매 시작자는 랜덤
        game["turn"] = random.choice(
            ["a", "b"]
        )

        return


    # --------------------------------------------------------
    # PASS로 뒤로 밀린 선수
    #
    # 일반 풀이 모두 끝나면
    # 뒤로 보낸 선수들이 다시 나온다.
    # --------------------------------------------------------

    if game["returned"]:

        game["pool"] = list(
            game["returned"]
        )

        game["returned"] = []


        random.shuffle(
            game["pool"]
        )


        game["current"] = game[
            "pool"
        ].pop(0)


        game["turn"] = random.choice(
            ["a", "b"]
        )

        return


    # --------------------------------------------------------
    # 정말 끝
    # --------------------------------------------------------

    game["finished"] = True

    game["current"] = None

    game["winner"] = None


# ============================================================
# 게임 생성
# ============================================================

def create_game(settings):

    pool = build_player_pool(
        settings
    )


    game_id = uuid.uuid4().hex


    game = {

        "id": game_id,

        "settings": dict(
            settings
        ),


        "players": {

            "a": "PLAYER 1",

            "b": "PLAYER 2",

        },


        "money": {

            "a": int(
                settings["money"]
            ),

            "b": int(
                settings["money"]
            ),

        },


        "spent": {

            "a": 0,

            "b": 0,

        },


        "rosters": {

            "a": [],

            "b": [],

        },


        "pool": pool,

        "returned": [],


        "current": None,

        "bid": 0,

        "leader": None,


        # 경매 시작자는 랜덤
        "turn": random.choice(
            ["a", "b"]
        ),


        "log": [],


        "finished": False,

        "winner": None,

    }


    # 첫 선수

    next_player(game)


    return game


# ============================================================
# 템플릿용 상태
# ============================================================

def make_state(game):

    settings = game[
        "settings"
    ]


    limits = {

        position:
            get_position_limit(
                settings,
                position
            )

        for position in POSITIONS

    }


    state = {

        "id": game["id"],


        "players": dict(
            game["players"]
        ),


        "money": dict(
            game["money"]
        ),


        "spent": dict(
            game["spent"]
        ),


        "rosters": {

            "a": list(
                game["rosters"]["a"]
            ),

            "b": list(
                game["rosters"]["b"]
            ),

        },


        "roster_size":
            roster_size(settings),


        "limits": limits,


        "current":
            game["current"],


        "bid":
            game["bid"],


        # 기존 템플릿 호환
        "current_bid":
            game["bid"],


        "leader":
            game["leader"],


        "turn":
            game["turn"],


        "log": list(
            game["log"]
        ),


        "finished":
            game["finished"],


        "winner":
            game["winner"],

    }


    return state


# ============================================================
# /draft
#
# 시작 화면
# ============================================================

@draft_bp.route("/")
def draft_home():

    return render_template(
        "draft_setup.html",
        settings=DEFAULT_SETTINGS,
        error=None
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

        money = get_int_form(
            "money",
            10,
            1
        )


        starter = get_int_form(
            "starter",
            2,
            0
        )


        reliever = get_int_form(
            "reliever",
            2,
            0
        )


        closer = get_int_form(
            "closer",
            1,
            0
        )


        infield = get_int_form(
            "infield",
            2,
            0
        )


        outfield = get_int_form(
            "outfield",
            2,
            0
        )


        catcher = get_int_form(
            "catcher",
            1,
            0
        )


        settings = {

            "money": money,

            "starter": starter,

            "reliever": reliever,

            "closer": closer,

            "infield": infield,

            "outfield": outfield,

            "catcher": catcher,

        }


        # 최소 1명 이상

        if roster_size(
            settings
        ) <= 0:

            raise ValueError(
                "최소 1명의 선수를 설정해야 합니다."
            )


        game = create_game(
            settings
        )


        GAMES[
            game["id"]
        ] = game


        return redirect(
            url_for(
                "draft.game",
                game_id=game["id"]
            )
        )


    except Exception as e:

        return render_template(
            "draft_setup.html",
            settings=request.form,
            error=str(e)
        )


# ============================================================
# 게임 화면
# ============================================================

@draft_bp.route(
    "/game/<game_id>"
)
def game(game_id):

    game_data = GAMES.get(
        game_id
    )


    if game_data is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    state = make_state(
        game_data
    )


    # 기존 템플릿과 새 템플릿 모두 대응
    return render_template(
        "draft_game.html",

        state=state,

        game=game_data,

        game_id=game_id,

        save_id=game_id,

        error=None
    )


# ============================================================
# 경매 액션
# ============================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(game_id):

    game = GAMES.get(
        game_id
    )


    if game is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    if game["finished"]:

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    current = game.get(
        "current"
    )


    if current is None:

        next_player(game)


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


    if side not in (
        "a",
        "b"
    ):

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    # --------------------------------------------------------
    # 현재 차례 검증
    # --------------------------------------------------------

    if side != game["turn"]:

        return render_template(
            "draft_game.html",

            state=make_state(game),

            game=game,

            game_id=game_id,

            save_id=game_id,

            error="현재 차례가 아닙니다."
        )


    # ========================================================
    # BID +$1
    # ========================================================

    if action_type == "bid":

        new_bid = (
            int(game["bid"])
            + 1
        )


        # ------------------------------------
        # 자본 검사
        # ------------------------------------

        if new_bid > int(
            game["money"][side]
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error="자본이 부족합니다."
            )


        # ------------------------------------
        # 로스터 검사
        # ------------------------------------

        if roster_full(
            game,
            side
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error="이미 로스터가 가득 찼습니다."
            )


        # ------------------------------------
        # 포지션 검사
        # ------------------------------------

        if position_full(
            game,
            side,
            current
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error=(
                    f"{current.get('position')} "
                    "포지션은 더 이상 뽑을 수 없습니다."
                )
            )


        # ------------------------------------
        # 입찰
        # ------------------------------------

        game["bid"] = new_bid

        game["leader"] = side


        game["log"].append(

            f"{game['players'][side]} "
            f"→ {current.get('name')} "
            f"${new_bid} 입찰"

        )


        # 상대방 차례

        game["turn"] = (
            "b"
            if side == "a"
            else "a"
        )


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    # ========================================================
    # ALL-IN
    # ========================================================

    if action_type in (
        "allin",
        "all_in"
    ):

        amount = int(
            game["money"][side]
        )


        # ------------------------------------
        # 로스터 검사
        # ------------------------------------

        if roster_full(
            game,
            side
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error="이미 로스터가 가득 찼습니다."
            )


        # ------------------------------------
        # 포지션 검사
        # ------------------------------------

        if position_full(
            game,
            side,
            current
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error=(
                    f"{current.get('position')} "
                    "포지션은 더 이상 뽑을 수 없습니다."
                )
            )


        if amount <= int(
            game["bid"]
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error="ALL-IN 할 수 있는 금액이 없습니다."
            )


        # ------------------------------------
        # 상대도 같은 금액 ALL-IN 상태
        #
        # 사용자 요구:
        # 동일 금액이면
        # 나중에 ALL-IN을 선언한 사람이 획득
        # ------------------------------------

        if (
            game["leader"] is not None
            and game["leader"] != side
            and game["bid"] == amount
        ):

            winner = side

            price = amount


            game["money"][winner] = 0

            game["spent"][winner] += price


            game["rosters"][winner].append(
                current
            )


            game["log"].append(

                f"{game['players'][winner]} "
                f"→ {current.get('name')} "
                f"동액 ALL-IN 낙찰 "
                f"(${price})"

            )


            next_player(game)


            if check_finished(
                game
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


        # ------------------------------------
        # 일반 ALL-IN
        # ------------------------------------

        game["bid"] = amount

        game["leader"] = side


        game["log"].append(

            f"{game['players'][side]} "
            f"→ {current.get('name')} "
            f"ALL-IN ${amount}"

        )


        game["turn"] = (
            "b"
            if side == "a"
            else "a"
        )


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    # ========================================================
    # PASS
    # ========================================================

    if action_type == "pass":

        # ----------------------------------------------------
        # 아무도 입찰하지 않았으면
        # 선수풀 맨 뒤로 보냄
        # ----------------------------------------------------

        if game["leader"] is None:

            game["returned"].append(
                current
            )


            game["log"].append(

                f"{current.get('name')} "
                "→ 양쪽 모두 PASS, "
                "선수풀 맨 뒤로 이동"

            )


            next_player(game)


            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )


        # ----------------------------------------------------
        # 이미 입찰자가 있다면
        # PASS한 상대가 포기
        # 선두가 낙찰
        # ----------------------------------------------------

        winner = game["leader"]

        price = int(
            game["bid"]
        )


        # 안전 검사

        if winner not in (
            "a",
            "b"
        ):

            game["leader"] = None

            game["returned"].append(
                current
            )

            next_player(game)

            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )


        if price > int(
            game["money"][winner]
        ):

            return render_template(
                "draft_game.html",

                state=make_state(game),

                game=game,

                game_id=game_id,

                save_id=game_id,

                error="낙찰 금액이 보유 자본보다 큽니다."
            )


        # ----------------------------------------------------
        # 낙찰
        # ----------------------------------------------------

        game["money"][winner] -= price

        game["spent"][winner] += price


        game["rosters"][winner].append(
            current
        )


        game["log"].append(

            f"{game['players'][winner]} "
            f"→ {current.get('name')} "
            f"낙찰 (${price})"

        )


        next_player(game)


        # ----------------------------------------------------
        # 한 명이 로스터를 전부 채웠다면
        # 남은 선수는 상대에게
        # ----------------------------------------------------

        if check_finished(
            game
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


    # ========================================================
    # 알 수 없는 액션
    # ========================================================

    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# ============================================================
# 결과 화면
# ============================================================

@draft_bp.route(
    "/game/<game_id>/result"
)
def result(game_id):

    game = GAMES.get(
        game_id
    )


    if game is None:

        return (
            "존재하지 않는 Draft 게임입니다.",
            404
        )


    # 혹시 아직 끝나지 않았는데
    # 결과 URL로 들어온 경우

    if not game["finished"]:

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    state = make_state(
        game
    )


    return render_template(
        "draft_result.html",

        state=state,

        game=game,

        game_id=game_id
    )
