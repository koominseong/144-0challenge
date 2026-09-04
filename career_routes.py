from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from career_Career import CareerPlayer


career_bp = Blueprint(
    "career",
    __name__,
    url_prefix="/career"
)


CAREER_PLAYERS = {}


def get_player():

    player_id = session.get(
        "career_player_id"
    )

    if not player_id:
        return None

    return CAREER_PLAYERS.get(
        player_id
    )


# ==================================================
# 생성
# ==================================================

@career_bp.route("/")
def career_create():

    return render_template(
        "career_create.html"
    )


@career_bp.route(
    "/start",
    methods=["POST"]
)
def career_start():

    player = CareerPlayer(

        name=request.form.get(
            "name",
            "신인 선수"
        ),

        nationality=request.form.get(
            "nationality",
            "KOR"
        ),

        position=request.form.get(
            "position",
            "SS"
        ),

        age=int(
            request.form.get(
                "age",
                18
            )
        ),

        league_id=request.form.get(
            "league_id",
            "KBO"
        ),

        team_id=request.form.get(
            "team_id",
            "LG"
        ),

        mode=request.form.get(
            "mode",
            "normal"
        )
    )

    CAREER_PLAYERS[
        player.player_id
    ] = player

    session[
        "career_player_id"
    ] = player.player_id

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ==================================================
# 홈
# ==================================================

@career_bp.route("/home")
def career_home():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(

        "career_home.html",

        player=player.to_dict()

    )


# ==================================================
# 시즌
# ==================================================

@career_bp.route(
    "/season",
    methods=["POST"]
)
def career_season():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    result = player.simulate_season()

    session[
        "career_last_season"
    ] = result

    return render_template(

        "career_season.html",

        player=player.to_dict(),

        result=result

    )


# ==================================================
# 이벤트
# ==================================================

@career_bp.route("/event")
def career_event():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(

        "career_event.html",

        player=player.to_dict()

    )


# ==================================================
# 이적
# ==================================================

@career_bp.route(
    "/transfer",
    methods=["POST"]
)
def career_transfer():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    league = request.form.get(
        "league_id"
    )

    team = request.form.get(
        "team_id"
    )

    if league and team:

        player.transfer(
            league,
            team,
            "career_transfer"
        )

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ==================================================
# 계약
# ==================================================

@career_bp.route(
    "/contract",
    methods=["POST"]
)
def career_contract():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    years = int(
        request.form.get(
            "years",
            1
        )
    )

    salary = int(
        request.form.get(
            "salary",
            0
        )
    )

    player.sign_contract(
        years,
        salary
    )

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ==================================================
# 국가대표
# ==================================================

@career_bp.route(
    "/national",
    methods=["POST"]
)
def career_national():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    competition = request.form.get(
        "competition",
        "WBC"
    )

    player.national_team_callup(
        competition
    )

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ==================================================
# 타임라인
# ==================================================

@career_bp.route("/timeline")
def career_timeline():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(

        "career_timeline.html",

        player=player.to_dict()

    )


# ==================================================
# 은퇴
# ==================================================

@career_bp.route(
    "/retire",
    methods=["POST"]
)
def career_retire():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    player.retire()

    return redirect(
        url_for(
            "career.career_summary"
        )
    )


# ==================================================
# Summary
# ==================================================

@career_bp.route("/summary")
def career_summary():

    player = get_player()

    if not player:

        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(

        "career_summary.html",

        summary=player.summary()

    )
