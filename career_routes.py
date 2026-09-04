from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from Career import Career


career_bp = Blueprint(
    "career",
    __name__,
    url_prefix="/career"
)


# ---------------------------------
# 임시 Career 저장소
# ---------------------------------

CAREERS = {}


def get_career():
    career_id = session.get("career_id")

    if not career_id:
        return None

    return CAREERS.get(career_id)


# ---------------------------------
# Career 시작
# ---------------------------------

@career_bp.route("/")
def career_create():
    return render_template(
        "career_create.html"
    )


@career_bp.route("/start", methods=["POST"])
def career_start():

    name = request.form.get(
        "name",
        "Unknown Player"
    )

    nationality = request.form.get(
        "nationality",
        "KOR"
    )

    position = request.form.get(
        "position",
        "외야수"
    )

    team = request.form.get(
        "team",
        "LG Twins"
    )

    mode = request.form.get(
        "mode",
        "normal"
    )

    try:
        age = int(
            request.form.get(
                "age",
                18
            )
        )
    except ValueError:
        age = 18

    career = Career(
        name=name,
        nationality=nationality,
        position=position,
        age=age,
        team=team,
        mode=mode
    )

    import uuid

    career_id = str(
        uuid.uuid4()
    )

    CAREERS[career_id] = career

    session["career_id"] = career_id

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ---------------------------------
# Career Home
# ---------------------------------

@career_bp.route("/home")
def career_home():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(
        "career_home.html",
        career=career.to_dict()
    )


# ---------------------------------
# 시즌 진행
# ---------------------------------

@career_bp.route(
    "/season",
    methods=["POST"]
)
def career_season():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    season = career.play_season()

    event = career.check_event()

    if event:

        session["career_event"] = event

        return redirect(
            url_for(
                "career.career_event"
            )
        )

    return render_template(
        "career_home.html",
        career=career.to_dict(),
        season_result=season
    )


# ---------------------------------
# 이벤트
# ---------------------------------

@career_bp.route("/event")
def career_event():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    event = session.get(
        "career_event"
    )

    if not event:
        return redirect(
            url_for(
                "career.career_home"
            )
        )

    return render_template(
        "career_event.html",
        career=career.to_dict(),
        event=event
    )


# ---------------------------------
# 이벤트 선택
# ---------------------------------

@career_bp.route(
    "/event/choice",
    methods=["POST"]
)
def career_event_choice():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    event = session.get(
        "career_event"
    )

    choice = request.form.get(
        "choice"
    )

    if event and choice:
        career.apply_event_choice(
            event,
            choice
        )

    session.pop(
        "career_event",
        None
    )

    return redirect(
        url_for(
            "career.career_home"
        )
    )


# ---------------------------------
# Timeline
# ---------------------------------

@career_bp.route("/timeline")
def career_timeline():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(
        "career_timeline.html",
        career=career.to_dict()
    )


# ---------------------------------
# 은퇴
# ---------------------------------

@career_bp.route(
    "/retire",
    methods=["POST"]
)
def career_retire():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    career.retire()

    return redirect(
        url_for(
            "career.career_summary"
        )
    )


# ---------------------------------
# Career Summary
# ---------------------------------

@career_bp.route("/summary")
def career_summary():

    career = get_career()

    if not career:
        return redirect(
            url_for(
                "career.career_create"
            )
        )

    return render_template(
        "career_summary.html",
        career=career.to_dict()
    )
