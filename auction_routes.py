import json
import os

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session,
    jsonify,
)

from auction import (
    create_game,
    user_action,
    seconds_left,
    run_ai_battle,
    next_round,
)


auction_bp = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# ============================================================
# PLAYER POOL
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PLAYER_POOL_PATH = os.path.join(
    BASE_DIR,
    "player_pool.json"
)


def load_player_pool():

    if not os.path.exists(
        PLAYER_POOL_PATH
    ):

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

    # --------------------------------------------
    # [
    #   {...},
    #   {...}
    # ]
    # --------------------------------------------

    if isinstance(
        data,
        list
    ):

        players = data

    # --------------------------------------------
    # {
    #   "players": [...]
    # }
    # --------------------------------------------

    elif isinstance(
        data,
        dict
    ):

        if isinstance(
            data.get("players"),
            list
        ):

            players = data[
                "players"
            ]

        elif isinstance(
            data.get("player_pool"),
            list
        ):

            players = data[
                "player_pool"
            ]

        else:

            # 혹시 dict 안에 선수 데이터가
            # 직접 들어있는 경우
            players = []

            for value in data.values():

                if isinstance(
                    value,
                    list
                ):

                    players.extend(
                        value
                    )

    else:

        raise ValueError(
            "player_pool.json 형식이 올바르지 않습니다."
        )

    if not players:

        raise ValueError(
            "player_pool.json에 선수가 없습니다."
        )

    return players


# ============================================================
# SESSION
# ============================================================

def get_games():

    return session.get(
        "auction_games",
        {}
    )


def save_games(
    games
):

    session[
        "auction_games"
    ] = games

    session.modified = True


def get_game(
    game_id
):

    games = get_games()

    return games.get(
        str(game_id)
    )


def save_game(
    game_id,
    game
):

    games = get_games()

    games[
        str(game_id)
    ] = game

    save_games(
        games
    )


# ============================================================
# HOME
# ============================================================

@auction_bp.route(
    "/",
    methods=["GET"]
)
def auction_home():

    games = get_games()

    history = []

    for game_id, game in games.items():

        if not game.get(
            "finished"
        ):
            continue

        result = game.get(
            "result"
        )

        if not result:
            continue

        user = result.get(
            "user",
            {}
        )

        history.append({

            "game_id":
                game_id,

            "rank":
                user.get(
                    "rank",
                    "-"
                ),

            "grade":
                user.get(
                    "grade",
                    "-"
                ),

            "score":
                user.get(
                    "score",
                    0
                ),

            "date":
                game.get(
                    "created_at",
                    ""
                ),
        })

    history.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    return render_template(
        "auction_home.html",
        history=history
    )


# ============================================================
# NEW GAME
# ============================================================

@auction_bp.route(
    "/new",
    methods=["GET"]
)
def auction_new():

    try:

        # ----------------------------------------
        # 실제 player_pool.json 로딩
        # ----------------------------------------

        players = load_player_pool()

        # ----------------------------------------
        # 게임 생성
        # ----------------------------------------

        game = create_game(
            players
        )

        # ----------------------------------------
        # ID 생성
        # ----------------------------------------

        games = get_games()

        ids = []

        for key in games.keys():

            try:

                ids.append(
                    int(key)
                )

            except (
                TypeError,
                ValueError
            ):

                pass

        game_id = str(
            max(
                ids or [0]
            ) + 1
        )

        # ----------------------------------------
        # 저장
        # ----------------------------------------

        games[
            game_id
        ] = game

        save_games(
            games
        )

        # ----------------------------------------
        # 반드시 game_id를 전달
        # ----------------------------------------

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id
            )
        )

    except Exception as e:

        print(
            "[AUCTION NEW ERROR]",
            repr(e)
        )

        return render_template(
            "auction_error.html",
            error=str(e)
        ), 500


# ============================================================
# GAME
# ============================================================

@auction_bp.route(
    "/<game_id>",
    methods=["GET"]
)
def auction_play(
    game_id
):

    game = get_game(
        game_id
    )

    if game is None:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    # ----------------------------------------
    # 종료
    # ----------------------------------------

    if game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    # ----------------------------------------
    # current가 없으면 다음 선수
    # ----------------------------------------

    if game.get(
        "current"
    ) is None:

        next_round(
            game
        )

        save_game(
            game_id,
            game
        )

    # next_round 이후 종료될 수도 있음
    if game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    # ----------------------------------------
    # 타이머
    # ----------------------------------------

    remaining = seconds_left(
        game
    )

    # GET 요청마다 강제로 timeout 처리하지 않는다.
    #
    # 프론트에서 timeout POST를 보낸다.
    # 이게 중요하다.
    #
    # 이전 버전처럼 GET → timeout → redirect
    # 를 반복하면 새로고침 루프가 생길 수 있음.
    # ----------------------------------------

    return render_template(
        "auction_game.html",

        game_id=game_id,

        state=game,

        player=game.get(
            "current"
        ),

        price=game.get(
            "price",
            0
        ),

        leader=game.get(
            "leader"
        ),

        message=game.get(
            "message",
            ""
        ),

        remaining=max(
            0,
            int(
                remaining
            )
        ),

        ai_names=game.get(
            "ai_names",
            {}
        ),

        ai_budgets=game.get(
            "ai_budgets",
            {}
        ),

        ai_rosters=game.get(
            "ai_rosters",
            {}
        ),

        roster_limits=game.get(
            "roster_limits",
            {}
        ),

        bid_log=game.get(
            "bid_log",
            []
        ),

        total_rounds=game.get(
            "total_rounds",
            0
        ),

        roster=game.get(
            "roster",
            []
        )
    )


# ============================================================
# ACTION
# ============================================================

@auction_bp.route(
    "/<game_id>/action/<action>",
    methods=["POST"]
)
def auction_action(
    game_id,
    action
):

    game = get_game(
        game_id
    )

    if game is None:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    if not game.get(
        "finished"
    ):

        user_action(
            game,
            action
        )

        save_game(
            game_id,
            game
        )

    # 종료되었으면 결과
    if game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id
        )
    )


# ============================================================
# AI
# ============================================================

@auction_bp.route(
    "/<game_id>/ai",
    methods=["POST"]
)
def auction_ai(
    game_id
):

    game = get_game(
        game_id
    )

    if game is None:

        return jsonify({
            "error":
                "game not found"
        }), 404

    if game.get(
        "finished"
    ):

        return jsonify({
            "finished":
                True
        })

    changed = run_ai_battle(
        game
    )

    save_game(
        game_id,
        game
    )

    return jsonify({

        "changed":
            changed,

        "finished":
            game.get(
                "finished",
                False
            ),

        "leader":
            game.get(
                "leader"
            ),

        "price":
            game.get(
                "price",
                0
            ),

        "remaining":
            seconds_left(
                game
            ),

        "message":
            game.get(
                "message",
                ""
            ),

        "bid_log":
            game.get(
                "bid_log",
                []
            )
    })


# ============================================================
# RESULT
# ============================================================

@auction_bp.route(
    "/<game_id>/result",
    methods=["GET"]
)
def auction_result(
    game_id
):

    game = get_game(
        game_id
    )

    if game is None:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    if not game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id
            )
        )

    result = game.get(
        "result",
        {}
    )

    return render_template(
        "auction_result.html",

        game_id=game_id,

        state=game,

        result=result,

        results=result.get(
            "results",
            []
        ),

        user=result.get(
            "user",
            {}
        ),

        history=result.get(
            "history",
            []
        ),

        best_bargain=result.get(
            "best_bargain"
        ),

        roster_limits=result.get(
            "roster_limits",
            {}
        )
    )
