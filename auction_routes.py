# auction_routes.py

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    session,
)

import json
import os
import uuid

from auction import (
    create_game,
    user_action,
    AI_NAMES,
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
# Supabase
# ============================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY"
)

supabase = None


try:

    if (
        SUPABASE_URL
        and SUPABASE_KEY
    ):

        from supabase import create_client

        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

except Exception as e:

    print(
        "[AUCTION] Supabase disabled:",
        e
    )


# ============================================================
# 게임 저장소
#
# Render 인스턴스가 재시작되면
# 메모리 게임은 사라질 수 있다.
#
# 실제 영구 저장은 Supabase를 사용.
# ============================================================

GAMES = {}


# ============================================================
# 게임 가져오기
# ============================================================

def get_game(game_id):

    return GAMES.get(
        str(game_id)
    )


# ============================================================
# Supabase 결과 저장
# ============================================================

def save_result_to_supabase(
    state
):

    if supabase is None:
        return

    result = state.get(
        "result"
    )

    if not result:
        return

    user = result.get(
        "user",
        {}
    )

    try:

        payload = {

            "game_id":
                str(
                    state.get(
                        "game_id",
                        ""
                    )
                ),

            "rank":
                int(
                    user.get(
                        "rank",
                        4
                    )
                ),

            "score":
                float(
                    user.get(
                        "score",
                        0
                    )
                ),

            "grade":
                user.get(
                    "grade",
                    "D"
                ),

            "spent":
                int(
                    user.get(
                        "spent",
                        0
                    )
                ),

            "remaining":
                int(
                    user.get(
                        "remaining",
                        0
                    )
                ),

            "efficiency":
                float(
                    user.get(
                        "efficiency",
                        0
                    )
                ),

            "win_margin":
                float(
                    user.get(
                        "win_margin",
                        0
                    )
                ),

            "roster":
                user.get(
                    "roster",
                    []
                ),

            "results":
                result.get(
                    "results",
                    []
                ),

        }

        supabase.table(
            "auction_results"
        ).insert(
            payload
        ).execute()

        print(
            "[AUCTION] result saved"
        )

    except Exception as e:

        print(
            "[AUCTION] result save error:",
            e
        )


# ============================================================
# 명예의 전당 조회
# ============================================================

def get_hall_of_fame():

    if supabase is None:

        return []

    try:

        response = (
            supabase
            .table(
                "auction_results"
            )
            .select(
                "rank,score,grade,spent,remaining,created_at"
            )
            .order(
                "score",
                desc=True
            )
            .limit(
                20
            )
            .execute()
        )

        return response.data or []

    except Exception as e:

        print(
            "[AUCTION] hall error:",
            e
        )

        return []


# ============================================================
# HOME
# ============================================================

@auction_bp.route("/")
def auction_home():

    hall = get_hall_of_fame()

    return render_template(
        "auction_home.html",
        hall=hall,
    )


# ============================================================
# NEW GAME
# ============================================================

@auction_bp.route(
    "/new",
    methods=["GET"]
)
def auction_new():

    game_id = str(
        uuid.uuid4()
    )

    state = create_game()

    state["game_id"] = game_id

    GAMES[game_id] = state

    session[
        "auction_game_id"
    ] = game_id

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id
        )
    )


# ============================================================
# PLAY
# ============================================================

@auction_bp.route(
    "/<game_id>",
    methods=["GET"]
)
def auction_play(
    game_id
):

    game_id = str(game_id)

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    # 게임 끝났으면 결과로
    if state.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
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
            12
        ),

        ai_names=AI_NAMES,
    )


# ============================================================
# ACTION
# ============================================================

@auction_bp.route(
    "/<game_id>/action",
    methods=["POST"]
)
def auction_action(
    game_id
):

    game_id = str(game_id)

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    if state.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    # ========================================================
    # 중요
    #
    # auction_game.html에서
    #
    # <input name="action">
    #
    # 으로 POST한다.
    # ========================================================

    action = request.form.get(
        "action"
    )

    if action is None:

        # 기존 URL 방식도 혹시 모르게 지원
        action = request.args.get(
            "action",
            "pass"
        )

    try:

        state = user_action(
            state,
            action
        )

    except Exception as e:

        print(
            "[AUCTION] action error:",
            e
        )

        state["message"] = (
            "입찰 처리 중 오류가 발생했습니다."
        )

        GAMES[game_id] = state

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id
            )
        )

    state["game_id"] = game_id

    GAMES[game_id] = state

    # ========================================================
    # 종료
    # ========================================================

    if state.get(
        "finished"
    ):

        save_result_to_supabase(
            state
        )

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
# RESULT
# ============================================================

@auction_bp.route(
    "/<game_id>/result",
    methods=["GET"]
)
def auction_result(
    game_id
):

    game_id = str(game_id)

    state = get_game(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_new"
            )
        )

    if not state.get(
        "finished"
    ):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id
            )
        )

    result = state.get(
        "result",
        {}
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
    methods=["GET"]
)
def auction_hall():

    hall = get_hall_of_fame()

    return render_template(
        "auction_home.html",
        hall=hall,
    )
