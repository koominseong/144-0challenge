from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    session,
)

from auction import (
    create_game,
    user_action,
    seconds_left,
)


auction_bp = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# ============================================================
# GAME STORAGE
# ============================================================

def get_games():
    return session.setdefault(
        "auction_games",
        {},
    )


def get_game(game_id):
    games = get_games()

    game = games.get(
        str(game_id)
    )

    return game


def save_game(game_id, game):
    games = get_games()

    games[str(game_id)] = game

    session[
        "auction_games"
    ] = games

    session.modified = True


# ============================================================
# AUCTION HOME
# ============================================================

@auction_bp.route("/")
def auction_home():

    games = get_games()

    history = []

    for game_id, game in games.items():

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
                    "-",
                ),

            "grade":
                user.get(
                    "grade",
                    "-",
                ),

            "score":
                user.get(
                    "score",
                    0,
                ),

            "date":
                game.get(
                    "created_at",
                    "",
                ),

        })

    history.sort(
        key=lambda x:
            x["score"],
        reverse=True,
    )

    return render_template(
        "auction_home.html",
        history=history,
    )


# ============================================================
# NEW GAME
# ============================================================

@auction_bp.route(
    "/new",
    methods=["GET"],
)
def auction_new():

    games = get_games()

    # 간단한 game_id 생성
    game_id = str(
        max(
            [
                int(x)
                for x in games.keys()
                if str(x).isdigit()
            ]
            or [0]
        )
        + 1
    )

    game = create_game()

    save_game(
        game_id,
        game,
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

    # 이미 끝났으면 결과
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

    # --------------------------------------------------------
    # 시간이 끝났으면 서버에서 자동 처리
    # --------------------------------------------------------

    if remaining <= 0:

        user_action(
            game,
            "timeout",
        )

        save_game(
            game_id,
            game,
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

        game_id=game_id,

        state=game,

        player=game.get(
            "current"
        ),

        price=game.get(
            "price",
            1,
        ),

        leader=game.get(
            "leader"
        ),

        message=game.get(
            "message",
            "",
        ),

        remaining=max(
            0,
            int(
                remaining
            ),
        ),

        ai_names=game.get(
            "ai_names",
            {},
        ),

        ai_budgets=game.get(
            "ai_budgets",
            {},
        ),

        ai_rosters=game.get(
            "ai_rosters",
            {},
        ),

        roster_limits=game.get(
            "roster_limits",
            {},
        ),

        bid_log=game.get(
            "bid_log",
            [],
        ),

        total_rounds=game.get(
            "total_rounds",
            0,
        ),

        roster=game.get(
            "roster",
            [],
        ),
    )


# ============================================================
# ACTION
# ============================================================

@auction_bp.route(
    "/<game_id>/action/<action>",
    methods=["POST"],
)
def auction_action(
    game_id,
    action,
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
            action,
        )

        save_game(
            game_id,
            game,
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
        {},
    )

    return render_template(
        "auction_result.html",

        game_id=game_id,

        state=game,

        result=result,

        results=result.get(
            "results",
            [],
        ),

        user=result.get(
            "user",
            {},
        ),

        history=result.get(
            "history",
            [],
        ),

        best_bargain=result.get(
            "best_bargain"
        ),

        roster_limits=result.get(
            "roster_limits",
            {},
        ),
    )
