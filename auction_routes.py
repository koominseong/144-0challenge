import uuid

from flask import (
    Blueprint,
    redirect,
    render_template,
    session,
    url_for,
    request,
)

from auction import (
    create_game,
    process_game,
    serialize_game,
    user_bid,
    settle_auction,
    auction_expired,
)


auction = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# =========================================================
# 게임 저장소
# =========================================================

GAMES = {}


# =========================================================
# 홈
# =========================================================

@auction.route("/")
def auction_home():

    return render_template(
        "auction_home.html"
    )


# =========================================================
# 새 게임
# =========================================================

@auction.route("/new")
def auction_new():

    game_id = str(
        uuid.uuid4()
    )

    try:

        game = create_game(
            game_id
        )

        GAMES[game_id] = game

        session[
            "auction_game_id"
        ] = game_id

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    except Exception as e:

        print(
            "[AUCTION START ERROR]",
            repr(e)
        )

        return render_template(
            "auction_error.html",
            error=str(e),
        ), 500


# =========================================================
# 게임 화면
# =========================================================

@auction.route("/<game_id>")
def auction_play(game_id):

    game = GAMES.get(
        str(game_id)
    )

    if not game:

        return render_template(
            "auction_error.html",
            error="게임을 찾을 수 없습니다.",
        ), 404

    process_game(game)

    if game["finished"]:

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    data = serialize_game(
        game
    )

    message = session.pop(
        "auction_message",
        None
    )

    return render_template(
        "auction_game.html",

        game=data,

        game_id=game_id,

        player=data[
            "current_player"
        ],

        roster=data[
            "roster"
        ],

        ais=data[
            "ais"
        ],

        logs=data[
            "logs"
        ],

        bid_history=data[
            "bid_history"
        ],

        budget=data[
            "budget"
        ],

        current_price=data[
            "current_price"
        ],

        highest_bidder=data[
            "highest_bidder"
        ],

        remaining_time=data[
            "remaining_time"
        ],

        initial_time=data[
            "initial_time"
        ],

        reset_time=data[
            "reset_time"
        ],

        round=data[
            "round"
        ],

        total_rounds=data[
            "total_rounds"
        ],

        message=message,
    )


# =========================================================
# 입찰 / 낙찰
# =========================================================

@auction.route(
    "/<game_id>/action/<action>",
    methods=["POST"]
)
def auction_action(
    game_id,
    action,
):

    game = GAMES.get(
        str(game_id)
    )

    if not game:

        return render_template(
            "auction_error.html",
            error="게임을 찾을 수 없습니다.",
        ), 404

    if game["finished"]:

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    # =====================================
    # 입찰
    # =====================================

    if action == "bid":

        try:

            amount = int(
                request.form.get(
                    "amount",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            amount = 0

        success, message = user_bid(
            game,
            amount
        )

        session[
            "auction_message"
        ] = message

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    # =====================================
    # 시간 종료 / 낙찰
    # =====================================

    if action == "timeout":

        if auction_expired(
            game
        ):

            settle_auction(
                game
            )

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id,
        )
    )


# =========================================================
# 결과
# =========================================================

@auction.route(
    "/<game_id>/result"
)
def auction_result(game_id):

    game = GAMES.get(
        str(game_id)
    )

    if not game:

        return render_template(
            "auction_error.html",
            error="게임을 찾을 수 없습니다.",
        ), 404

    if not game["finished"]:

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    result = game.get(
        "result"
    )

    return render_template(
        "auction_result.html",
        game=game,
        result=result,
        game_id=game_id,
    )


# =========================================================
# 삭제
# =========================================================

@auction.route(
    "/<game_id>/delete",
    methods=["POST"]
)
def auction_delete(game_id):

    GAMES.pop(
        str(game_id),
        None
    )

    if session.get(
        "auction_game_id"
    ) == str(game_id):

        session.pop(
            "auction_game_id",
            None
        )

    return redirect(
        url_for(
            "auction.auction_home"
        )
    )
