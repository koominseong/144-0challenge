# auction_routes.py

import uuid

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
)

from auction import (
    create_game,
)


# ============================================================
# BLUEPRINT
# ============================================================

auction_bp = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# ============================================================
# GAME STORAGE
# ============================================================

GAMES = {}


# ============================================================
# HOME
# ============================================================

@auction_bp.route("/")
def auction_home():

    return render_template(
        "auction_home.html",
        hall=[],
    )


# ============================================================
# NEW GAME
# ============================================================

@auction_bp.route(
    "/new",
    methods=["GET"],
)
def auction_new():

    game_id = str(
        uuid.uuid4()
    )

    state = create_game()

    state["game_id"] = game_id

    GAMES[game_id] = state

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

    game_id = str(game_id)

    state = GAMES.get(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    # 게임 종료
    if state.get(
        "finished",
        False,
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    # --------------------------------------------------------
    # GET 요청에서도 timeout 검사
    #
    # 브라우저가 닫혔다가 다시 들어와도
    # 서버 시간이 이미 끝났다면 처리한다.
    # --------------------------------------------------------

    from auction import (
        is_bid_expired,
        settle_current_auction,
        ai_response,
        next_round,
    )

    if is_bid_expired(state):

        if state.get("leader"):

            settle_current_auction(
                state
            )

        else:

            ai = ai_response(
                state
            )

            if not ai:
                next_round(
                    state
                )

        GAMES[game_id] = state

        if state.get(
            "finished",
            False,
        ):

            return redirect(
                url_for(
                    "auction.auction_result",
                    game_id=game_id,
                )
            )

    current = state.get(
        "current"
    )

    return render_template(
        "auction_game.html",

        state=state,

        current=current,

        game_id=game_id,

        total_rounds=state.get(
            "total_rounds",
            12,
        ),

        ai_names=state.get(
            "ai_names",
            {},
        ),
    )


# ============================================================
# ACTION
# ============================================================

@auction_bp.route(
    "/<game_id>/action",
    methods=["POST"],
)
def auction_action(game_id):

    game_id = str(game_id)

    state = GAMES.get(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    if state.get(
        "finished",
        False,
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id,
            )
        )

    action = request.form.get(
        "action"
    )

    if action is None:

        action = request.args.get(
            "action"
        )

    if action is None:

        state["message"] = (
            "잘못된 요청입니다."
        )

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    try:

        from auction import (
            user_action,
        )

        user_action(
            state,
            action,
        )

        GAMES[game_id] = state

    except Exception as e:

        print(
            "[AUCTION ERROR]",
            repr(e),
        )

        state["message"] = (
            "경매 처리 중 오류가 발생했습니다."
        )

        GAMES[game_id] = state

    # --------------------------------------------------------
    # 끝났으면 결과 페이지
    # --------------------------------------------------------

    if state.get(
        "finished",
        False,
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
    methods=["GET"],
)
def auction_result(game_id):

    game_id = str(game_id)

    state = GAMES.get(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    if not state.get(
        "finished",
        False,
    ):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    return render_template(
        "auction_result.html",

        result=state.get(
            "result",
            {},
        ),

        game_id=game_id,
    )


# ============================================================
# HALL
# ============================================================

@auction_bp.route(
    "/hall",
    methods=["GET"],
)
def auction_hall():

    return render_template(
        "auction_home.html",
        hall=[],
    )
