# auction_routes.py

import os
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
# Blueprint
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
# GAME PAGE
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

    # 존재하지 않는 게임
    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )


    # 이미 끝났으면 결과
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


    # 현재 선수
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
            {
                "veteran": "베테랑",
                "data": "데이터파",
                "gambler": "승부사",
            },
        ),
    )


# ============================================================
# AUCTION ACTION
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

    # 게임이 없으면 새 게임
    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )


    # 끝난 게임
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


    # ========================================================
    # ACTION
    # ========================================================

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


    # ========================================================
    # AUCTION.PY
    # ========================================================

    try:

        from auction import (
            user_action,
        )

        state = user_action(
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


    # ========================================================
    # RESULT
    # ========================================================

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


    # ========================================================
    # GAME
    # ========================================================

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


    result = state.get(
        "result",
        {},
    )


    return render_template(
        "auction_result.html",

        result=result,

        game_id=game_id,

    )


# ============================================================
# HALL OF FAME
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
