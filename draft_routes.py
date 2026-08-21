# =========================================================
# draft_routes.py
# Draft Mode Routes
# =========================================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)

import uuid
import json

from draft import (
    create_game,
    process_action,
    calculate_result,
)


# =========================================================
# Blueprint
# =========================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# =========================================================
# 게임 저장
#
# 현재는 Flask session 기반.
# 나중에 Supabase로 옮겨도
# route 구조는 그대로 사용할 수 있게 작성.
# =========================================================

def _games():

    if "draft_games" not in session:
        session["draft_games"] = {}

    return session["draft_games"]


def _save_game(
    game_id,
    state,
):

    games = _games()

    games[game_id] = state

    session["draft_games"] = games

    session.modified = True


def _load_game(
    game_id,
):

    games = _games()

    return games.get(game_id)


def _delete_game(
    game_id,
):

    games = _games()

    if game_id in games:
        del games[game_id]

    session["draft_games"] = games

    session.modified = True


# =========================================================
# 공통 설정값 변환
# =========================================================

POSITIONS = (
    "선발",
    "불펜",
    "마무리",
    "포수",
    "내야",
    "외야",
)


def _int_value(
    value,
    default=0,
):

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


# =========================================================
# Draft 시작 화면
#
# GET /draft
# =========================================================

@draft_bp.route(
    "/",
    methods=["GET"]
)
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# =========================================================
# Draft 게임 생성
#
# POST /draft/start
# =========================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    # -----------------------------------------------------
    # 플레이어 이름
    # -----------------------------------------------------

    player_a = (
        request.form.get(
            "player_a"
        )
        or "PLAYER A"
    ).strip()

    player_b = (
        request.form.get(
            "player_b"
        )
        or "PLAYER B"
    ).strip()


    # -----------------------------------------------------
    # 초기 자금
    # -----------------------------------------------------

    initial_money = _int_value(
        request.form.get(
            "initial_money"
        ),
        10
    )

    if initial_money <= 0:

        return render_template(
            "draft_setup.html",
            error="초기 자금은 1달러 이상이어야 합니다."
        )


    # -----------------------------------------------------
    # 포지션별 인원
    #
    # 한 팀이 가져갈 인원
    # -----------------------------------------------------

    limits = {}

    for position in POSITIONS:

        limits[position] = _int_value(
            request.form.get(
                position
            ),
            0
        )

        if limits[position] < 0:

            limits[position] = 0


    # -----------------------------------------------------
    # 최소 한 자리 이상
    # -----------------------------------------------------

    roster_size = sum(
        limits.values()
    )

    if roster_size <= 0:

        return render_template(
            "draft_setup.html",
            error="최소 한 명 이상의 선수 정원이 필요합니다."
        )


    # -----------------------------------------------------
    # 게임 생성
    # -----------------------------------------------------

    try:

        state = create_game(
            player_a=player_a,
            player_b=player_b,
            initial_money=initial_money,
            limits=limits,
        )

    except ValueError as e:

        return render_template(
            "draft_setup.html",
            error=str(e)
        )

    except Exception as e:

        return render_template(
            "draft_setup.html",
            error=f"게임 생성 중 오류가 발생했습니다: {e}"
        )


    # -----------------------------------------------------
    # 게임 ID
    # -----------------------------------------------------

    game_id = str(
        uuid.uuid4()
    )

    state["game_id"] = game_id


    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    _save_game(
        game_id,
        state
    )


    # -----------------------------------------------------
    # 게임 화면
    # -----------------------------------------------------

    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# =========================================================
# 게임 화면
#
# GET /draft/game/<game_id>
# =========================================================

@draft_bp.route(
    "/game/<game_id>",
    methods=["GET"]
)
def game(
    game_id
):

    state = _load_game(
        game_id
    )


    # -----------------------------------------------------
    # 없는 게임
    # -----------------------------------------------------

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )


    # -----------------------------------------------------
    # 종료된 게임이면 결과 페이지
    # -----------------------------------------------------

    if state.get("finished"):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    # -----------------------------------------------------
    # 템플릿
    # -----------------------------------------------------

    return render_template(
        "draft_game.html",

        state=state,

        game_id=game_id,

        save_id=game_id,

        error=None,
    )


# =========================================================
# 경매 액션
#
# POST /draft/game/<game_id>/action
# =========================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(
    game_id
):

    state = _load_game(
        game_id
    )


    # -----------------------------------------------------
    # 게임 없음
    # -----------------------------------------------------

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )


    # -----------------------------------------------------
    # 이미 종료
    # -----------------------------------------------------

    if state.get("finished"):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    # -----------------------------------------------------
    # 현재 플레이어
    #
    # hidden side를 믿지 않고
    # 서버 state의 turn을 우선 사용
    # -----------------------------------------------------

    side = state.get(
        "turn"
    )

    if side not in (
        "a",
        "b"
    ):

        return _render_game_error(
            game_id,
            state,
            "현재 차례를 확인할 수 없습니다."
        )


    # -----------------------------------------------------
    # 액션
    # -----------------------------------------------------

    action_name = (
        request.form.get(
            "action"
        )
        or ""
    ).strip().lower()


    # -----------------------------------------------------
    # 직접 입찰 금액
    # -----------------------------------------------------

    amount_raw = (
        request.form.get(
            "amount"
        )
        or ""
    ).strip()

    amount = None

    if amount_raw:

        try:

            amount = int(
                amount_raw
            )

        except ValueError:

            return _render_game_error(
                game_id,
                state,
                "입찰 금액은 숫자로 입력해야 합니다."
            )


    # -----------------------------------------------------
    # 액션 실행
    # -----------------------------------------------------

    try:

        ok, message = process_action(
            state,
            side,
            action_name,
            amount,
        )

    except Exception as e:

        return _render_game_error(
            game_id,
            state,
            f"경매 처리 중 오류가 발생했습니다: {e}"
        )


    # -----------------------------------------------------
    # 실패
    # -----------------------------------------------------

    if not ok:

        return _render_game_error(
            game_id,
            state,
            message or "알 수 없는 오류입니다."
        )


    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------

    _save_game(
        game_id,
        state
    )


    # -----------------------------------------------------
    # 종료
    # -----------------------------------------------------

    if state.get("finished"):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    # -----------------------------------------------------
    # 다시 게임 화면
    # -----------------------------------------------------

    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# =========================================================
# 게임 오류 화면
# =========================================================

def _render_game_error(
    game_id,
    state,
    error,
):

    return render_template(
        "draft_game.html",

        state=state,

        game_id=game_id,

        save_id=game_id,

        error=error,
    )


# =========================================================
# 결과
#
# GET /draft/game/<game_id>/result
# =========================================================

@draft_bp.route(
    "/game/<game_id>/result",
    methods=["GET"]
)
def result(
    game_id
):

    state = _load_game(
        game_id
    )


    # -----------------------------------------------------
    # 게임 없음
    # -----------------------------------------------------

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )


    # -----------------------------------------------------
    # 구버전 / 비정상 state 방어
    #
    # 예전에 발생했던
    #
    # UndefinedError:
    # 'dict object' has no attribute 'result'
    #
    # 방지
    # -----------------------------------------------------

    if not state.get("result"):

        try:

            state["result"] = calculate_result(
                state
            )

        except Exception as e:

            return render_template(
                "draft_result.html",

                state=state,

                game_id=game_id,

                error=(
                    "결과를 계산할 수 없습니다: "
                    f"{e}"
                )
            )


    # -----------------------------------------------------
    # 결과 저장
    # -----------------------------------------------------

    state["finished"] = True

    _save_game(
        game_id,
        state
    )


    # -----------------------------------------------------
    # 결과 화면
    # -----------------------------------------------------

    return render_template(
        "draft_result.html",

        state=state,

        game_id=game_id,

        error=None,
    )


# =========================================================
# 새 게임
#
# GET /draft/game/<game_id>/restart
# =========================================================

@draft_bp.route(
    "/game/<game_id>/restart",
    methods=["GET"]
)
def restart(
    game_id
):

    _delete_game(
        game_id
    )

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )


# =========================================================
# 게임 삭제
#
# POST /draft/game/<game_id>/delete
# =========================================================

@draft_bp.route(
    "/game/<game_id>/delete",
    methods=["POST"]
)
def delete_game(
    game_id
):

    _delete_game(
        game_id
    )

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )
