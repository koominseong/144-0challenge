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
)


auction_bp = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# ============================================================
# SESSION
# ============================================================

def get_games():

    if "auction_games" not in session:

        session[
            "auction_games"
        ] = {}

    return session[
        "auction_games"
    ]


def get_game(game_id):

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

    session[
        "auction_games"
    ] = games

    session.modified = True


# ============================================================
# HOME
# ============================================================

@auction_bp.route("/")
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
        history=history,
    )


# ============================================================
# NEW
# ============================================================

@auction_bp.route(
    "/new",
    methods=["GET"],
)
def auction_new():

    games = get_games()

    ids = []

    for key in games.keys():

        try:
            ids.append(
                int(key)
            )
        except (
            TypeError,
            ValueError,
        ):
            pass

    game_id = str(
        max(
            ids or [0]
        ) + 1
    )

    # --------------------------------------------------------
    # 여기 중요
    #
    # 네 player_pool.json을 사용하는 기존 코드가 있다면
    # create_game(players)를 넘겨주면 됨.
    #
    # 현재는 session에 저장된 player_pool이 있으면 사용.
    # --------------------------------------------------------

    players = session.get(
        "auction_players",
        []
    )

    game = create_game(
        players
    )

    save_game(
        game_id,
        game
    )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id,
        )
    )


# ============================================================
# GAME
# ============================================================

@auction_bp.route(
    "/<game_id>",
    methods=["GET"],
)
def auction_play(game_id):

    game = get_game(
        game_id
    )

    if game is None:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    # --------------------------------------------------------
    # 게임 종료
    # --------------------------------------------------------

    if game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    # --------------------------------------------------------
    # 타임아웃
    # --------------------------------------------------------

    remaining = seconds_left(
        game
    )

    if remaining <= 0:

        user_action(
            game,
            "timeout"
        )

        save_game(
            game_id,
            game
        )

        if game.get(
            "finished"
        ):

            return redirect(
                url_for(
                    "auction.auction_result",
                    game_id=game_id,
                )
            )

        remaining = seconds_left(
            game
        )

    return render_template(
        "auction_game.html",

        game_id=
            game_id,

        state=
            game,

        player=
            game.get(
                "current"
            ),

        price=
            game.get(
                "price",
                1
            ),

        leader=
            game.get(
                "leader"
            ),

        message=
            game.get(
                "message",
                ""
            ),

        remaining=
            max(
                0,
                int(
                    remaining
                )
            ),

        ai_names=
            game.get(
                "ai_names",
                {}
            ),

        ai_budgets=
            game.get(
                "ai_budgets",
                {}
            ),

        ai_rosters=
            game.get(
                "ai_rosters",
                {}
            ),

        roster_limits=
            game.get(
                "roster_limits",
                {}
            ),

        bid_log=
            game.get(
                "bid_log",
                []
            ),

        total_rounds=
            game.get(
                "total_rounds",
                0
            ),

        roster=
            game.get(
                "roster",
                []
            ),
    )


# ============================================================
# USER ACTION
# ============================================================

@auction_bp.route(
    "/<game_id>/action/<action>",
    methods=["POST"],
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

    if game.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id,
        )
    )


# ============================================================
# AI
# ============================================================

@auction_bp.route(
    "/<game_id>/ai",
    methods=["POST"],
)
def auction_ai(game_id):

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

    run_ai_battle(
        game
    )

    save_game(
        game_id,
        game
    )

    return jsonify({

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
                "price"
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
            ),

    })


# ============================================================
# RESULT
# ============================================================

@auction_bp.route(
    "/<game_id>/result",
)
def auction_result(game_id):

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
                game_id=game_id,
            )
        )

    result = game.get(
        "result",
        {}
    )

    return render_template(
        "auction_result.html",

        game_id=
            game_id,

        state=
            game,

        result=
            result,

        results=
            result.get(
                "results",
                []
            ),

        user=
            result.get(
                "user",
                {}
            ),

        history=
            result.get(
                "history",
                []
            ),

        best_bargain=
            result.get(
                "best_bargain"
            ),

        roster_limits=
            result.get(
                "roster_limits",
                {}
            ),
    )
