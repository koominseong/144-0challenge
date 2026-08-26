# auction_routes.py

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
)

from auction import (
    AI_NAMES,
    TOTAL_ROUNDS,
    create_game,
    export_state,
    import_state,
    user_action,
    finish_game,
)


auction_bp = Blueprint(
    "auction",
    __name__,
    url_prefix="/auction",
)


# ============================================================
# Supabase
# ============================================================

def get_supabase():
    """
    프로젝트의 기존 Supabase 연결 방식이 있으면
    아래 import를 해당 함수로 바꾸면 됨.

    우선 환경변수 기반으로 직접 연결.
    """

    try:
        from supabase import create_client
    except ImportError:
        return None

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        return None

    return create_client(
        url,
        key,
    )


# ============================================================
# player_pool.json
# ============================================================

def load_players():
    """
    player_pool.json을 읽는다.

    프로젝트 루트 기준:
        player_pool.json

    또는:
        /opt/render/project/src/player_pool.json
    """

    candidates = [
        os.path.join(
            os.path.dirname(__file__),
            "player_pool.json",
        ),
        os.path.join(
            os.getcwd(),
            "player_pool.json",
        ),
    ]

    path = None

    for candidate in candidates:
        if os.path.exists(candidate):
            path = candidate
            break

    if path is None:
        raise FileNotFoundError(
            "player_pool.json을 찾을 수 없습니다."
        )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    # 리스트
    if isinstance(data, list):
        return data

    # {"players": [...]}
    if isinstance(data, dict):

        for key in (
            "players",
            "player_pool",
            "data",
        ):
            if isinstance(
                data.get(key),
                list,
            ):
                return data[key]

    raise ValueError(
        "player_pool.json 형식을 확인해주세요."
    )


# ============================================================
# 공통
# ============================================================

def current_user_key():
    """
    로그인 시스템이 있는 경우
    기존 프로젝트의 user id로 교체 가능.

    로그인 시스템이 없으면 세션별 익명 ID.
    """

    # 흔히 사용하는 로그인 키 호환
    for key in (
        "user_id",
        "username",
        "nickname",
    ):
        value = session.get(key)

        if value:
            return str(value)

    if "auction_guest_id" not in session:
        session["auction_guest_id"] = (
            f"guest_"
            f"{random.randint(10000000, 99999999)}"
        )

    return session["auction_guest_id"]


def serialize_state(state):
    return json.loads(
        json.dumps(
            export_state(state),
            ensure_ascii=False,
        )
    )


# ============================================================
# DB - 게임
# ============================================================

def db_create_game(state):
    """
    auction_game 테이블에 게임 저장.

    테이블이 없거나 Supabase 설정이 없는 경우에는
    세션 fallback을 사용한다.
    """

    supabase = get_supabase()

    if supabase is None:
        session["auction_state"] = serialize_state(
            state
        )

        # 세션 게임 ID
        game_id = session.get(
            "auction_game_id"
        )

        if not game_id:
            game_id = random.randint(
                100000,
                999999,
            )

            session[
                "auction_game_id"
            ] = game_id

        return game_id

    payload = {
        "user_id": current_user_key(),
        "state": serialize_state(state),
        "status": "playing",
        "round": 1,
    }

    try:

        response = (
            supabase
            .table("auction_game")
            .insert(payload)
            .execute()
        )

        rows = response.data or []

        if not rows:
            raise RuntimeError(
                "auction_game INSERT 결과가 없습니다."
            )

        game_id = rows[0].get("id")

        session[
            "auction_game_id"
        ] = game_id

        return game_id

    except Exception:
        # DB 오류가 나도 게임 자체는 세션으로 계속 가능
        game_id = random.randint(
            100000,
            999999,
        )

        session[
            "auction_game_id"
        ] = game_id

        session[
            "auction_state"
        ] = serialize_state(state)

        return game_id


def db_get_game(game_id):
    supabase = get_supabase()

    # 세션 fallback
    if supabase is None:

        saved_id = session.get(
            "auction_game_id"
        )

        if str(saved_id) != str(game_id):
            return None

        data = session.get(
            "auction_state"
        )

        if not data:
            return None

        return import_state(data)

    try:

        response = (
            supabase
            .table("auction_game")
            .select("*")
            .eq("id", game_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        row = rows[0]

        state = row.get("state")

        if isinstance(state, str):
            state = json.loads(state)

        if not isinstance(state, dict):
            return None

        return import_state(state)

    except Exception:
        return None


def db_save_game(game_id, state):
    supabase = get_supabase()

    serialized = serialize_state(state)

    # 세션 fallback
    if supabase is None:

        session[
            "auction_game_id"
        ] = game_id

        session[
            "auction_state"
        ] = serialized

        return True

    try:

        (
            supabase
            .table("auction_game")
            .update({
                "state": serialized,
                "round": state.get(
                    "round",
                    1,
                ),
                "status": (
                    "finished"
                    if state.get("finished")
                    else "playing"
                ),
            })
            .eq("id", game_id)
            .execute()
        )

        return True

    except Exception:

        # DB 실패 시 세션 fallback
        session[
            "auction_game_id"
        ] = game_id

        session[
            "auction_state"
        ] = serialized

        return False


# ============================================================
# 결과 저장
# ============================================================

def save_result(game_id, state):
    """
    게임 종료 후 auction_record에 기록.
    """

    if not state.get("finished"):
        return

    result = state.get(
        "result"
    )

    if not result:
        return

    user = result.get(
        "user",
        {},
    )

    payload = {
        "game_id": game_id,
        "user_id": current_user_key(),

        "rank": user.get(
            "rank"
        ),

        "score": user.get(
            "score"
        ),

        "grade": user.get(
            "grade"
        ),

        "spent": user.get(
            "spent",
            0,
        ),

        "remaining": user.get(
            "remaining",
            0,
        ),

        "power": user.get(
            "power",
            0,
        ),

        "efficiency": user.get(
            "efficiency",
            0,
        ),

        "balance": user.get(
            "balance",
            0,
        ),

        "win_margin": user.get(
            "win_margin",
            0,
        ),

        "roster": user.get(
            "roster",
            [],
        ),

        "opponents": result.get(
            "results",
            [],
        ),

        "best_bargain": result.get(
            "best_bargain"
        ),

        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    supabase = get_supabase()

    if supabase is None:

        history = session.get(
            "auction_history",
            [],
        )

        history.append(
            payload
        )

        session[
            "auction_history"
        ] = history[-50:]

        return

    try:

        (
            supabase
            .table("auction_record")
            .insert(payload)
            .execute()
        )

    except Exception:
        # 결과 저장 실패가 게임 결과 페이지를 막으면 안 됨
        pass


# ============================================================
# 명예의 전당
# ============================================================

def get_hall_of_fame(limit=20):

    supabase = get_supabase()

    # --------------------------------------------
    # Supabase
    # --------------------------------------------

    if supabase is not None:

        try:

            response = (
                supabase
                .table("auction_record")
                .select(
                    "user_id,"
                    "score,"
                    "grade,"
                    "rank,"
                    "created_at"
                )
                .order(
                    "score",
                    desc=True,
                )
                .limit(limit)
                .execute()
            )

            return response.data or []

        except Exception:
            pass

    # --------------------------------------------
    # 세션 fallback
    # --------------------------------------------

    records = session.get(
        "auction_history",
        [],
    )

    records = sorted(
        records,
        key=lambda x: float(
            x.get("score", 0)
        ),
        reverse=True,
    )

    return records[:limit]


# ============================================================
# /auction
# ============================================================

@auction_bp.route("/")
def auction_home():

    hall_of_fame = (
        get_hall_of_fame(20)
    )

    my_records = [
        x
        for x in hall_of_fame
        if str(
            x.get("user_id")
        )
        == str(
            current_user_key()
        )
    ]

    best_score = 0
    best_grade = "-"
    wins = 0
    s_count = 0

    for record in my_records:

        score = float(
            record.get(
                "score",
                0,
            )
        )

        if score > best_score:
            best_score = score

        grade = record.get(
            "grade",
            "-",
        )

        if grade == "S+":
            s_count += 1

        if int(
            record.get(
                "rank",
                99,
            )
        ) == 1:
            wins += 1

        grade_order = {
            "S+": 8,
            "S": 7,
            "A+": 6,
            "A": 5,
            "B+": 4,
            "B": 3,
            "C": 2,
            "D": 1,
            "-": 0,
        }

        if grade_order.get(
            grade,
            0,
        ) > grade_order.get(
            best_grade,
            0,
        ):
            best_grade = grade

    return render_template(
        "auction_home.html",
        hall_of_fame=hall_of_fame,
        best_score=round(
            best_score,
            2,
        ),
        best_grade=best_grade,
        wins=wins,
        s_count=s_count,
        ai_names=AI_NAMES,
    )


# ============================================================
# /auction/new
# ============================================================

@auction_bp.route("/new")
def auction_new():

    try:

        players = load_players()

        state = create_game(
            players
        )

        game_id = db_create_game(
            state
        )

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    except Exception as e:

        flash(
            f"Auction 시작 오류: {e}",
            "error",
        )

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )


# ============================================================
# /auction/<game_id>
# ============================================================

@auction_bp.route(
    "/<int:game_id>",
    methods=["GET"],
)
def auction_play(game_id):

    state = db_get_game(
        game_id
    )

    if state is None:

        flash(
            "게임을 찾을 수 없습니다.",
            "error",
        )

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    # 게임 종료
    if state.get("finished"):

        return render_template(
            "auction_result.html",
            game_id=game_id,
            state=state,
            result=state.get(
                "result"
            ),
            ai_names=AI_NAMES,
        )

    current = state.get(
        "current",
        {},
    )

    return render_template(
        "auction_game.html",

        game_id=game_id,

        state=state,

        current=current,

        player=current,

        ai_names=AI_NAMES,

        total_rounds=TOTAL_ROUNDS,
    )


# ============================================================
# /auction/<game_id>/action
# ============================================================

@auction_bp.route(
    "/<int:game_id>/action",
    methods=["POST"],
)
def auction_action(game_id):

    state = db_get_game(
        game_id
    )

    if state is None:

        flash(
            "게임을 찾을 수 없습니다.",
            "error",
        )

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    if state.get("finished"):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    action = request.form.get(
        "action",
        ""
    ).strip()

    # 잘못된 요청 방지
    if action not in {
        "1",
        "3",
        "5",
        "pass",
    }:

        flash(
            "잘못된 경매 요청입니다.",
            "error",
        )

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    try:

        state = user_action(
            state,
            action,
        )

        db_save_game(
            game_id,
            state,
        )

        if state.get("finished"):
            save_result(
                game_id,
                state,
            )

    except Exception as e:

        flash(
            f"경매 처리 중 오류: {e}",
            "error",
        )

    return redirect(
        url_for(
            "auction.auction_play",
            game_id=game_id,
        )
    )


# ============================================================
# 결과 확인
# ============================================================

@auction_bp.route(
    "/<int:game_id>/result",
    methods=["GET"],
)
def auction_result(game_id):

    state = db_get_game(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "auction.auction_home"
            )
        )

    if not state.get("finished"):

        return redirect(
            url_for(
                "auction.auction_play",
                game_id=game_id,
            )
        )

    return render_template(
        "auction_result.html",
        game_id=game_id,
        state=state,
        result=state.get(
            "result"
        ),
        ai_names=AI_NAMES,
    )
