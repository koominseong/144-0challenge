# auction_routes.py
# =========================================
# 144-0 Challenge - PLAYER AUCTION
# =========================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
)

from auction import (
    new_game,
    restore_state,
    public_state,
    user_action,
    score_game,
    AI_NAMES,
    ROUNDS,
)

from dynasty_utils import get_supabase


auction_bp = Blueprint(
    "auction",
    __name__
)


def _get_game(sb, game_id):
    rows = (
        sb
        .table("auction_game")
        .select("*")
        .eq("id", game_id)
        .execute()
        .data
    )

    return rows[0] if rows else None


def _leaderboard(sb):
    try:

        rows = (
            sb
            .table("auction_record")
            .select("*")
            .execute()
            .data
        )

    except Exception as ex:

        print(
            f"[auction] "
            f"leaderboard skip: {ex}"
        )

        return []

    rows.sort(
        key=lambda r: (
            -float(
                r.get("score") or 0
            ),

            -float(
                r.get("avg_overall") or 0
            ),
        )
    )

    return rows[:100]


# =========================================
# AUCTION HOME
# =========================================

@auction_bp.route("/auction")
def auction_home():

    sb = get_supabase()

    return render_template(
        "auction_home.html",
        records=_leaderboard(sb),
    )


# =========================================
# NEW GAME
# =========================================

@auction_bp.route("/auction/new")
def auction_new():

    sb = get_supabase()

    state = new_game()

    # player_pool과 AI 숨은 최대 입찰가는
    # DB에 저장하지 않는다.
    row = (
        sb
        .table("auction_game")
        .insert({
            "state": public_state(state),
            "finished": False,
        })
        .execute()
        .data[0]
    )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=row["id"]
        )
    )


# =========================================
# GAME
# =========================================

@auction_bp.route(
    "/auction/<int:game_id>"
)
def auction_play(game_id):

    sb = get_supabase()

    row = _get_game(
        sb,
        game_id
    )

    if not row:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    state = restore_state(
        row["state"]
    )

    if state.get("done"):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    return render_template(
        "auction_game.html",

        game_id=game_id,

        state=state,

        ai_names=AI_NAMES,

        total_rounds=ROUNDS,
    )


# =========================================
# ACTION
# =========================================

@auction_bp.route(
    "/auction/<int:game_id>/action",
    methods=["POST"]
)
def auction_action(game_id):

    sb = get_supabase()

    row = _get_game(
        sb,
        game_id
    )

    if not row:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    state = restore_state(
        row["state"]
    )

    # 이미 끝난 게임이면 결과로
    if (
        state.get("done")
        or row.get("finished")
    ):

        return redirect(
            url_for(
                "auction.auction_result",
                game_id=game_id
            )
        )

    action = request.form.get(
        "action",
        ""
    )

    state = user_action(
        state,
        action
    )

    # 변경된 게임 상태 저장
    sb.table(
        "auction_game"
    ).update({
        "state": public_state(state)
    }).eq(
        "id",
        game_id
    ).execute()

    if state.get("done"):

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


# =========================================
# RESULT
# =========================================

@auction_bp.route(
    "/auction/<int:game_id>/result"
)
def auction_result(game_id):

    sb = get_supabase()

    row = _get_game(
        sb,
        game_id
    )

    if not row:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    state = restore_state(
        row["state"]
    )

    if not state.get("done"):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id
            )
        )

    result = score_game(
        state
    )

    # 종료 기록이 아직 없을 때만 저장
    if not row.get("finished"):

        try:

            (
                sb
                .table("auction_record")
                .insert({
                    "score": result["final"],
                    "grade": result["grade"],
                    "avg_overall": (
                        result["avg_overall"]
                    ),
                    "spent": result["spent"],
                    "remaining": (
                        result["remaining"]
                    ),
                    "roster": state["roster"],
                })
                .execute()
            )

        except Exception as ex:

            print(
                f"[auction] "
                f"기록 저장 skip: {ex}"
            )

        (
            sb
            .table("auction_game")
            .update({
                "finished": True
            })
            .eq(
                "id",
                game_id
            )
            .execute()
        )

    return render_template(
        "auction_result.html",

        game_id=game_id,

        state=state,

        result=result,

        records=_leaderboard(sb),
    )
