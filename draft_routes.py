from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

import random
import uuid


# ==========================================================
# Blueprint
# ==========================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ==========================================================
# 기본값
# ==========================================================

DEFAULT_MONEY = 20

DEFAULT_PITCHERS = 2
DEFAULT_INFIELDERS = 2
DEFAULT_OUTFIELDERS = 2
DEFAULT_CATCHERS = 1


# ==========================================================
# Draft 메인 / 설정 화면
#
# GET /draft
# ==========================================================

@draft_bp.route("")
@draft_bp.route("/")
def draft_home():

    return render_template(
        "draft_setup.html",
        state={
            "turn": None,
            "current_player": None,
            "finished": False
        },
        game=None
    )


# ==========================================================
# 게임 시작
#
# POST /draft/start
# ==========================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    # ------------------------------------------------------
    # 플레이어 이름
    # ------------------------------------------------------

    player1 = (
        request.form.get(
            "player1"
        )
        or "PLAYER 1"
    ).strip()

    player2 = (
        request.form.get(
            "player2"
        )
        or "PLAYER 2"
    ).strip()


    # ------------------------------------------------------
    # 선수 수
    # ------------------------------------------------------

    try:

        pitchers = int(
            request.form.get(
                "pitchers",
                DEFAULT_PITCHERS
            )
        )

        infielders = int(
            request.form.get(
                "infielders",
                DEFAULT_INFIELDERS
            )
        )

        outfielders = int(
            request.form.get(
                "outfielders",
                DEFAULT_OUTFIELDERS
            )
        )

        catchers = int(
            request.form.get(
                "catchers",
                DEFAULT_CATCHERS
            )
        )

        money = int(
            request.form.get(
                "money",
                DEFAULT_MONEY
            )
        )

    except (TypeError, ValueError):

        return render_template(
            "draft_setup.html",
            error="숫자를 올바르게 입력해주세요."
        )


    # ------------------------------------------------------
    # 검증
    # ------------------------------------------------------

    pitchers = max(0, pitchers)
    infielders = max(0, infielders)
    outfielders = max(0, outfielders)
    catchers = max(0, catchers)


    if money < 1:

        return render_template(
            "draft_setup.html",
            error="초기 자본은 1달러 이상이어야 합니다."
        )


    players_per_team = (
        pitchers
        + infielders
        + outfielders
        + catchers
    )


    if players_per_team <= 0:

        return render_template(
            "draft_setup.html",
            error="선수는 최소 1명 이상 설정해야 합니다."
        )


    # ======================================================
    # 선수풀
    #
    # 실제 선수 데이터는 이후 연결 가능
    # ======================================================

    player_pool = _build_player_pool(
        pitchers,
        infielders,
        outfielders,
        catchers
    )


    # ------------------------------------------------------
    # 선수 수 확인
    # ------------------------------------------------------

    required_players = players_per_team * 2


    if len(player_pool) < required_players:

        return render_template(
            "draft_setup.html",
            error=(
                f"현재 선수 데이터가 부족합니다. "
                f"필요 선수: {required_players}명"
            )
        )


    # ======================================================
    # 경매 순서 랜덤
    # ======================================================

    random.shuffle(
        player_pool
    )


    # ======================================================
    # 게임 ID
    # ======================================================

    game_id = uuid.uuid4().hex


    # ======================================================
    # 게임 상태
    # ======================================================

    game = {

        "id": game_id,

        "player1": player1,
        "player2": player2,

        "money": {
            "1": money,
            "2": money
        },

        "initial_money": money,

        "roster_size": players_per_team,

        "requirements": {
            "P": pitchers,
            "IF": infielders,
            "OF": outfielders,
            "C": catchers
        },

        "teams": {
            "1": [],
            "2": []
        },

        "pool": player_pool,

        "deferred": [],

        "current_player": None,

        "bid": 0,

        "bidder": None,

        "passed": [],

        "all_in": [],

        "finished": False,

        "winner": None,

        "history": []

    }


    # ======================================================
    # 첫 선수
    # ======================================================

    _next_player(
        game
    )


    # ======================================================
    # 세션 저장
    # ======================================================

    session[
        f"draft_{game_id}"
    ] = game


    return redirect(
        url_for(
            "draft.draft_game",
            game_id=game_id
        )
    )


# ==========================================================
# 게임 화면
#
# GET /draft/game/<game_id>
# ==========================================================

@draft_bp.route(
    "/game/<game_id>"
)
def draft_game(game_id):

    game = _get_game(
        game_id
    )


    if game is None:

        return "Draft 게임을 찾을 수 없습니다.", 404


    if game.get("finished"):

        return redirect(
            url_for(
                "draft.draft_result",
                game_id=game_id
            )
        )


    return render_template(
        "draft_game.html",
        game=game,
        state=game
    )


# ==========================================================
# 경매 액션
#
# POST /draft/game/<game_id>/action
# ==========================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def draft_action(game_id):

    game = _get_game(
        game_id
    )


    if game is None:

        return "Draft 게임을 찾을 수 없습니다.", 404


    if game.get("finished"):

        return redirect(
            url_for(
                "draft.draft_result",
                game_id=game_id
            )
        )


    # ------------------------------------------------------
    # 현재 플레이어
    # ------------------------------------------------------

    side = request.form.get(
        "side"
    )


    if side not in ("1", "2"):

        side = "1"


    action = request.form.get(
        "action",
        "pass"
    )


    # ======================================================
    # 입찰
    # ======================================================

    if action == "bid":

        _bid(
            game,
            side
        )


    # ======================================================
    # 올인
    # ======================================================

    elif action == "all_in":

        _all_in(
            game,
            side
        )


    # ======================================================
    # 패스
    # ======================================================

    elif action == "pass":

        _pass(
            game,
            side
        )


    # ======================================================
    # 상태 저장
    # ======================================================

    session[
        f"draft_{game_id}"
    ] = game

    session.modified = True


    # ======================================================
    # 종료
    # ======================================================

    if game.get("finished"):

        return redirect(
            url_for(
                "draft.draft_result",
                game_id=game_id
            )
        )


    return redirect(
        url_for(
            "draft.draft_game",
            game_id=game_id
        )
    )


# ==========================================================
# 결과
#
# GET /draft/game/<game_id>/result
# ==========================================================

@draft_bp.route(
    "/game/<game_id>/result"
)
def draft_result(game_id):

    game = _get_game(
        game_id
    )


    if game is None:

        return "Draft 게임을 찾을 수 없습니다.", 404


    return render_template(
        "draft_result.html",
        game=game,
        state=game
    )


# ==========================================================
# 게임 불러오기
# ==========================================================

def _get_game(game_id):

    return session.get(
        f"draft_{game_id}"
    )


# ==========================================================
# 선수풀 생성
# ==========================================================

def _build_player_pool(
    pitchers,
    infielders,
    outfielders,
    catchers
):

    pool = []


    # ------------------------------------------------------
    # 현재는 테스트용 선수 생성
    #
    # 이후 네 선수파일을 연결하면
    # 이 부분만 교체하면 됨.
    # ------------------------------------------------------

    index = 1


    for _ in range(
        pitchers * 2
    ):

        pool.append({

            "id": f"P{index}",

            "name": f"투수 {index}",

            "position": "P"

        })

        index += 1


    for _ in range(
        infielders * 2
    ):

        pool.append({

            "id": f"IF{index}",

            "name": f"내야수 {index}",

            "position": "IF"

        })

        index += 1


    for _ in range(
        outfielders * 2
    ):

        pool.append({

            "id": f"OF{index}",

            "name": f"외야수 {index}",

            "position": "OF"

        })

        index += 1


    for _ in range(
        catchers * 2
    ):

        pool.append({

            "id": f"C{index}",

            "name": f"포수 {index}",

            "position": "C"

        })

        index += 1


    return pool


# ==========================================================
# 다음 선수
# ==========================================================

def _next_player(game):

    # ------------------------------------------------------
    # 유찰 선수 → 뒤로 보냄
    # ------------------------------------------------------

    if game["deferred"]:

        game["pool"].extend(
            game["deferred"]
        )

        game["deferred"] = []


    # ------------------------------------------------------
    # 선수풀이 없으면 종료
    # ------------------------------------------------------

    if not game["pool"]:

        _finish_game(
            game
        )

        return


    # ------------------------------------------------------
    # 첫 선수를 가져옴
    # ------------------------------------------------------

    player = game["pool"].pop(0)


    game["current_player"] = player

    game["bid"] = 0

    game["bidder"] = None

    game["passed"] = []

    game["all_in"] = []


# ==========================================================
# 입찰
# ==========================================================

def _bid(
    game,
    side
):

    # 이미 해당 선수가 완료한 경우
    if side in game["passed"]:

        return


    money = game["money"][side]


    # ------------------------------------------------------
    # 1달러씩 증가
    # ------------------------------------------------------

    new_bid = game["bid"] + 1


    if new_bid > money:

        return


    game["bid"] = new_bid

    game["bidder"] = side


    game["history"].append({

        "type": "bid",

        "player": game["current_player"]["name"],

        "side": side,

        "amount": new_bid

    })


# ==========================================================
# 올인
# ==========================================================

def _all_in(
    game,
    side
):

    if side in game["passed"]:

        return


    money = game["money"][side]


    if money <= 0:

        return


    # ------------------------------------------------------
    # 올인 금액 = 현재 보유 자금
    # ------------------------------------------------------

    game["bid"] = money

    game["bidder"] = side

    game["all_in"].append(
        side
    )


    game["history"].append({

        "type": "all_in",

        "player": game["current_player"]["name"],

        "side": side,

        "amount": money

    })


    # ------------------------------------------------------
    # 상대가 같은 금액으로 올인하면
    # 먼저 올인한 사람에게 선수 지급
    # ------------------------------------------------------

    if len(
        set(game["all_in"])
    ) == 2:

        winner = game["all_in"][0]

        _award_player(
            game,
            winner
        )


# ==========================================================
# 패스
# ==========================================================

def _pass(
    game,
    side
):

    if side not in game["passed"]:

        game["passed"].append(
            side
        )


    game["history"].append({

        "type": "pass",

        "player": game["current_player"]["name"],

        "side": side

    })


    # ------------------------------------------------------
    # 두 명 모두 패스
    # ------------------------------------------------------

    if len(
        game["passed"]
    ) >= 2:

        player = game[
            "current_player"
        ]

        game["deferred"].append(
            player
        )

        game["current_player"] = None

        _next_player(
            game
        )

        return


    # ------------------------------------------------------
    # 한 명만 패스하고 상대가 이미 입찰했다면
    # 입찰자에게 선수 지급
    # ------------------------------------------------------

    if (
        game["bid"] > 0
        and game["bidder"] is not None
        and len(game["passed"]) == 1
    ):

        _award_player(
            game,
            game["bidder"]
        )


# ==========================================================
# 선수 획득
# ==========================================================

def _award_player(
    game,
    winner
):

    player = game[
        "current_player"
    ]


    if player is None:

        return


    amount = game[
        "bid"
    ]


    # ------------------------------------------------------
    # 금액 차감
    # ------------------------------------------------------

    game[
        "money"
    ][winner] -= amount


    # ------------------------------------------------------
    # 선수 지급
    # ------------------------------------------------------

    game[
        "teams"
    ][winner].append(
        player
    )


    game["history"].append({

        "type": "award",

        "player": player["name"],

        "side": winner,

        "amount": amount

    })


    # ------------------------------------------------------
    # 현재 선수 초기화
    # ------------------------------------------------------

    game["current_player"] = None


    game["bid"] = 0

    game["bidder"] = None

    game["passed"] = []

    game["all_in"] = []


    # ------------------------------------------------------
    # 승리 조건 확인
    # ------------------------------------------------------

    if _team_full(
        game,
        winner
    ):

        other = (
            "2"
            if winner == "1"
            else "1"
        )


        # 한 팀이 전부 채우면
        # 남은 선수는 상대에게 자동 지급

        _fill_other_team(
            game,
            other
        )

        _finish_game(
            game
        )

        return


    # ------------------------------------------------------
    # 다음 선수
    # ------------------------------------------------------

    _next_player(
        game
    )


# ==========================================================
# 로스터 완성 여부
# ==========================================================

def _team_full(
    game,
    side
):

    return (
        len(
            game["teams"][side]
        )
        >= game["roster_size"]
    )


# ==========================================================
# 남은 선수 자동 지급
# ==========================================================

def _fill_other_team(
    game,
    side
):

    needed = (
        game["roster_size"]
        - len(
            game["teams"][side]
        )
    )


    if needed <= 0:

        return


    # 현재 경매 대상
    if game["current_player"]:

        game["teams"][side].append(
            game["current_player"]
        )

        game["current_player"] = None

        needed -= 1


    # 선수풀에서 필요한 만큼 가져감
    while (
        needed > 0
        and game["pool"]
    ):

        game["teams"][side].append(
            game["pool"].pop(0)
        )

        needed -= 1


    # 유찰 선수
    while (
        needed > 0
        and game["deferred"]
    ):

        game["teams"][side].append(
            game["deferred"].pop(0)
        )

        needed -= 1


# ==========================================================
# 게임 종료
# ==========================================================

def _finish_game(
    game
):

    game["finished"] = True


    team1 = len(
        game["teams"]["1"]
    )

    team2 = len(
        game["teams"]["2"]
    )


    if team1 > team2:

        game["winner"] = "1"

    elif team2 > team1:

        game["winner"] = "2"

    else:

        game["winner"] = "draw"
