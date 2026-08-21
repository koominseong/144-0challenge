from flask import Blueprint, render_template, request, redirect, url_for

from draft import create_game, load_game, action


draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# =========================================================
# Draft 설정 화면
# /draft
# /draft/<save_id>
# =========================================================

@draft_bp.route("")
@draft_bp.route("/")
def draft_home():

    save_id = request.args.get("save_id", type=int)

    return render_template(
        "draft_setup.html",
        save_id=save_id
    )


@draft_bp.route("/<int:save_id>")
def draft_home_save(save_id):

    return render_template(
        "draft_setup.html",
        save_id=save_id
    )


# =========================================================
# Draft 시작
# =========================================================

@draft_bp.route("/start", methods=["POST"])
def draft_start_without_save():

    save_id = request.form.get(
        "save_id",
        type=int
    )

    return _start_game(save_id)


@draft_bp.route("/<int:save_id>/start", methods=["POST"])
def draft_start(save_id):

    return _start_game(save_id)


def _start_game(save_id):

    try:

        limits = {
            "P": request.form.get(
                "pitchers",
                2,
                type=int
            ),

            "IF": request.form.get(
                "infielders",
                2,
                type=int
            ),

            "OF": request.form.get(
                "outfielders",
                2,
                type=int
            ),

            "C": request.form.get(
                "catchers",
                1,
                type=int
            ),
        }


        money = request.form.get(
            "money",
            20,
            type=int
        )


        player_a = (
            request.form.get("player_a")
            or request.form.get("player1")
            or "PLAYER A"
        )


        player_b = (
            request.form.get("player_b")
            or request.form.get("player2")
            or "PLAYER B"
        )


        row = create_game(
            save_id=save_id,
            limits=limits,
            money=money,
            player_a=player_a,
            player_b=player_b
        )


        return redirect(
            url_for(
                "draft.draft_game",
                game_id=str(row["id"])
            )
        )


    except Exception as e:

        return render_template(
            "draft_setup.html",
            save_id=save_id,
            error=str(e),
            form=request.form
        )


# =========================================================
# 게임 화면
#
# UUID 사용
# =========================================================

@draft_bp.route("/game/<game_id>")
def draft_game(game_id):

    row = load_game(game_id)

    return render_template(
        "draft_game.html",

        game=row,

        state=row["state"],

        game_id=game_id,

        save_id=row.get("save_id")
    )


# =========================================================
# 경매 액션
# =========================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def draft_action(game_id):

    try:

        side = request.form.get("side")

        act = request.form.get("action")

        row = action(
            game_id,
            side,
            act
        )


    except Exception as e:

        row = load_game(game_id)

        return render_template(
            "draft_game.html",

            game=row,

            state=row["state"],

            game_id=game_id,

            save_id=row.get("save_id"),

            error=str(e)
        )


    if row["state"].get("finished"):

        return redirect(
            url_for(
                "draft.draft_result",
                game_id=str(game_id)
            )
        )


    return redirect(
        url_for(
            "draft.draft_game",
            game_id=str(game_id)
        )
    )


# =========================================================
# 결과
# =========================================================

@draft_bp.route("/result/<game_id>")
def draft_result(game_id):

    row = load_game(game_id)


    if not row["state"].get("finished"):

        return redirect(
            url_for(
                "draft.draft_game",
                game_id=str(game_id)
            )
        )


    return render_template(
        "draft_result.html",

        game=row,

        state=row["state"],

        game_id=game_id,

        save_id=row.get("save_id")
    )
