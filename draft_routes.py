# draft_routes.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)

import json
import os
import uuid
import random


# =========================================================
# Blueprint
# =========================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# =========================================================
# 파일 경로
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYER_POOL_FILE = os.path.join(
    BASE_DIR,
    "player_pool.json"
)


# =========================================================
# 기본 설정
# =========================================================

DEFAULT_SETTINGS = {

    "money": 10,

    "pitchers": 2,

    "infielders": 2,

    "outfielders": 2,

    "catchers": 1,

}


# =========================================================
# 선수 풀 로드
# =========================================================

def load_player_pool():

    if not os.path.exists(PLAYER_POOL_FILE):
        return []

    try:

        with open(
            PLAYER_POOL_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

    except Exception:
        return []


    # -----------------------------------------
    # JSON이 리스트인 경우
    # -----------------------------------------

    if isinstance(data, list):

        return data


    # -----------------------------------------
    # {"players": [...]} 형태
    # -----------------------------------------

    if isinstance(data, dict):

        if isinstance(data.get("players"), list):

            return data["players"]

        if isinstance(data.get("player_pool"), list):

            return data["player_pool"]

        if isinstance(data.get("pool"), list):

            return data["pool"]


    return []


# =========================================================
# 선수 포지션 정규화
# =========================================================

def normalize_group(player):

    group = (
        player.get("group")
        or player.get("position_group")
        or player.get("category")
        or ""
    )

    position = (
        player.get("position")
        or player.get("pos")
        or ""
    )


    group = str(group).strip()

    position = str(position).strip().upper()


    # 이미 한글 그룹이면 그대로 사용

    if group in (
        "투수",
        "내야수",
        "외야수",
        "포수"
    ):

        return group


    # 영문 그룹

    if group.upper() in (
        "P",
        "PITCHER",
        "PITCHERS"
    ):

        return "투수"


    if group.upper() in (
        "IF",
        "INF",
        "INFIELD",
        "INFIELDER",
        "INFIELDERS"
    ):

        return "내야수"


    if group.upper() in (
        "OF",
        "OUTFIELD",
        "OUTFIELDER",
        "OUTFIELDERS"
    ):

        return "외야수"


    if group.upper() in (
        "C",
        "CATCHER",
        "CATCHERS"
    ):

        return "포수"


    # position으로 판단

    if position in (
        "P",
        "SP",
        "RP"
    ):

        return "투수"


    if position in (
        "C",
        "포수"
    ):

        return "포수"


    if position in (
        "1B",
        "2B",
        "3B",
        "SS",
        "IF"
    ):

        return "내야수"


    if position in (
        "LF",
        "CF",
        "RF",
        "OF"
    ):

        return "외야수"


    return group or "기타"


# =========================================================
# 선수 데이터 정리
# =========================================================

def normalize_player(player):

    p = dict(player)

    p["name"] = (
        p.get("name")
        or p.get("player_name")
        or p.get("선수명")
        or "이름 없음"
    )

    p["team"] = (
        p.get("team")
        or p.get("팀")
        or ""
    )

    p["position"] = (
        p.get("position")
        or p.get("pos")
        or ""
    )

    p["group"] = normalize_group(p)

    try:

        p["overall"] = int(
            p.get("overall")
            or p.get("ovr")
            or p.get("rating")
            or 0
        )

    except Exception:

        p["overall"] = 0


    return p


# =========================================================
# 필요한 선수 수
# =========================================================

def required_counts(settings):

    return {

        "투수":
            int(settings["pitchers"]) * 2,

        "내야수":
            int(settings["infielders"]) * 2,

        "외야수":
            int(settings["outfielders"]) * 2,

        "포수":
            int(settings["catchers"]) * 2,

    }


# =========================================================
# 선수 풀 생성
# =========================================================

def build_pool(settings):

    players = [
        normalize_player(x)
        for x in load_player_pool()
        if isinstance(x, dict)
    ]


    required = required_counts(settings)


    groups = {

        "투수": [],

        "내야수": [],

        "외야수": [],

        "포수": [],

    }


    for player in players:

        group = player["group"]

        if group in groups:

            groups[group].append(player)


    # 부족한 포지션 확인

    for group, need in required.items():

        available = len(groups[group])

        if available < need:

            raise ValueError(
                f"{group} 선수 풀이 부족합니다. "
                f"필요 {need}명 / 보유 {available}명"
            )


    pool = []


    for group, count in required.items():

        selected = random.sample(
            groups[group],
            count
        )

        pool.extend(selected)


    # 전체 경매 순서 랜덤

    random.shuffle(pool)


    return pool


# =========================================================
# 게임 상태 생성
# =========================================================

def create_game(settings):

    pool = build_pool(settings)


    game = {

        "id": uuid.uuid4().hex,

        "settings": settings,

        "players": {

            "a": "PLAYER 1",

            "b": "PLAYER 2",

        },

        "money": {

            "a": int(settings["money"]),

            "b": int(settings["money"]),

        },

        "spent": {

            "a": 0,

            "b": 0,

        },

        "rosters": {

            "a": [],

            "b": [],

        },

        "pool": pool,

        "returned": [],

        "current": None,

        "bid": 0,

        "leader": None,

        "turn": random.choice(["a", "b"]),

        "log": [],

        "finished": False,

        "winner": None,

    }


    # 첫 선수

    advance_player(game)


    return game


# =========================================================
# 다음 선수
# =========================================================

def advance_player(game):

    if game["finished"]:

        return


    if game["pool"]:

        game["current"] = game["pool"].pop(0)

        game["bid"] = 0

        game["leader"] = None

        # 경매 시작자는 랜덤

        game["turn"] = random.choice(
            ["a", "b"]
        )

        return


    # 뒤로 밀렸던 선수

    if game["returned"]:

        game["pool"] = game["returned"]

        game["returned"] = []

        random.shuffle(game["pool"])

        advance_player(game)

        return


    game["current"] = None

    game["finished"] = True


    if len(game["rosters"]["a"]) > len(
        game["rosters"]["b"]
    ):

        game["winner"] = "a"

    elif len(game["rosters"]["b"]) > len(
        game["rosters"]["a"]
    ):

        game["winner"] = "b"

    else:

        game["winner"] = None


# =========================================================
# 로스터가 가득 찼는지
# =========================================================

def roster_full(game, side):

    settings = game["settings"]

    roster = game["rosters"][side]


    required = (

        int(settings["pitchers"])
        + int(settings["infielders"])
        + int(settings["outfielders"])
        + int(settings["catchers"])

    )


    return len(roster) >= required


# =========================================================
# 포지션 제한
# =========================================================

def position_full(game, side, player):

    group = player["group"]

    settings = game["settings"]

    roster = game["rosters"][side]


    limits = {

        "투수":
            int(settings["pitchers"]),

        "내야수":
            int(settings["infielders"]),

        "외야수":
            int(settings["outfielders"]),

        "포수":
            int(settings["catchers"]),

    }


    count = sum(
        1
        for p in roster
        if p.get("group") == group
    )


    return count >= limits.get(group, 999)


# =========================================================
# 현재 상태를 템플릿용으로 변환
# =========================================================

def template_state(game):

    state = dict(game)


    state["roster_size"] = (

        int(game["settings"]["pitchers"])
        + int(game["settings"]["infielders"])
        + int(game["settings"]["outfielders"])
        + int(game["settings"]["catchers"])

    )


    state["limits"] = {

        "투수":
            int(game["settings"]["pitchers"]),

        "내야수":
            int(game["settings"]["infielders"]),

        "외야수":
            int(game["settings"]["outfielders"]),

        "포수":
            int(game["settings"]["catchers"]),

    }


    return state


# =========================================================
# 임시 저장소
#
# 서버 재시작 전까지 사용
# =========================================================

GAMES = {}


# =========================================================
# /draft
# =========================================================

@draft_bp.route("/")
def draft_home():

    return render_template(
        "draft_setup.html",
        settings=DEFAULT_SETTINGS
    )


# =========================================================
# 게임 생성
# =========================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    try:

        money = int(
            request.form.get(
                "money",
                10
            )
        )

        pitchers = int(
            request.form.get(
                "pitchers",
                2
            )
        )

        infielders = int(
            request.form.get(
                "infielders",
                2
            )
        )

        outfielders = int(
            request.form.get(
                "outfielders",
                2
            )
        )

        catchers = int(
            request.form.get(
                "catchers",
                1
            )
        )


        if money < 1:

            raise ValueError(
                "초기 자본은 1달러 이상이어야 합니다."
            )


        settings = {

            "money": money,

            "pitchers": pitchers,

            "infielders": infielders,

            "outfielders": outfielders,

            "catchers": catchers,

        }


        game = create_game(settings)

        game_id = game["id"]

        GAMES[game_id] = game


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    except ValueError as e:

        return render_template(
            "draft_setup.html",
            settings=request.form,
            error=str(e)
        )


    except Exception as e:

        return render_template(
            "draft_setup.html",
            settings=request.form,
            error=f"게임 생성 오류: {e}"
        )


# =========================================================
# 게임 화면
# =========================================================

@draft_bp.route(
    "/game/<game_id>"
)
def game(game_id):

    game_data = GAMES.get(game_id)


    if not game_data:

        return "존재하지 않는 Draft 게임입니다.", 404


    state = template_state(
        game_data
    )


    return render_template(
        "draft_game.html",
        state=state,
        game=game_data,
        game_id=game_id,
        save_id=game_id,
        error=None
    )


# =========================================================
# 경매 액션
# =========================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(game_id):

    game = GAMES.get(game_id)


    if not game:

        return "존재하지 않는 Draft 게임입니다.", 404


    if game["finished"]:

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )


    current = game["current"]


    if not current:

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    side = request.form.get(
        "side"
    )


    action_type = request.form.get(
        "action"
    )


    if side not in ("a", "b"):

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    if side != game["turn"]:

        return render_template(
            "draft_game.html",
            state=template_state(game),
            game=game,
            game_id=game_id,
            save_id=game_id,
            error="현재 차례가 아닙니다."
        )


    # =====================================================
    # PASS
    # =====================================================

    if action_type == "pass":

        # 아직 아무도 입찰하지 않았다면
        # 이 선수는 선수풀 맨 뒤로

        if game["leader"] is None:

            game["returned"].append(
                current
            )

            game["log"].append(
                f"{current['name']} → 양쪽 모두 PASS. 선수풀 뒤로 이동"
            )


            advance_player(game)


            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )


        # 누군가 이미 입찰한 상태에서 PASS
        # 선두가 최종 낙찰

        winner = game["leader"]

        price = game["bid"]


        game["money"][winner] -= price

        game["spent"][winner] += price

        game["rosters"][winner].append(
            current
        )


        game["log"].append(
            f"{game['players'][winner]} → "
            f"{current['name']} 낙찰 (${price})"
        )


        # 상대가 로스터를 다 채웠으면
        # 남은 선수는 전부 반대쪽

        advance_player(game)


        if game["finished"]:

            return redirect(
                url_for(
                    "draft.result",
                    game_id=game_id
                )
            )


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    # =====================================================
    # BID
    # =====================================================

    if action_type == "bid":

        new_bid = game["bid"] + 1


        if new_bid > game["money"][side]:

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error="자본이 부족합니다."
            )


        if roster_full(
            game,
            side
        ):

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error="이미 로스터가 가득 찼습니다."
            )


        if position_full(
            game,
            side,
            current
        ):

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error=(
                    f"{current['group']} "
                    "포지션을 더 이상 채울 수 없습니다."
                )
            )


        game["bid"] = new_bid

        game["leader"] = side


        game["log"].append(
            f"{game['players'][side]} → "
            f"{current['name']} "
            f"${new_bid} 입찰"
        )


        game["turn"] = (
            "b"
            if side == "a"
            else "a"
        )


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    # =====================================================
    # ALL-IN
    # =====================================================

    if action_type == "allin":

        amount = game["money"][side]


        if amount <= game["bid"]:

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error="ALL-IN 할 수 있는 금액이 없습니다."
            )


        if roster_full(
            game,
            side
        ):

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error="이미 로스터가 가득 찼습니다."
            )


        if position_full(
            game,
            side,
            current
        ):

            return render_template(
                "draft_game.html",
                state=template_state(game),
                game=game,
                game_id=game_id,
                save_id=game_id,
                error=(
                    f"{current['group']} "
                    "포지션을 더 이상 채울 수 없습니다."
                )
            )


        # ---------------------------------------------
        # 같은 금액 ALL-IN
        # ---------------------------------------------

        if (
            game["leader"] is not None
            and game["bid"] == amount
            and game["leader"] != side
        ):

            # 같은 금액이면
            # ALL-IN을 선언한 사람이 승리

            winner = side

            price = amount


            game["money"][winner] = 0

            game["spent"][winner] += price

            game["rosters"][winner].append(
                current
            )


            game["log"].append(
                f"{game['players'][winner]} → "
                f"{current['name']} "
                f"동액 ALL-IN 낙찰 (${price})"
            )


            advance_player(game)


            if game["finished"]:

                return redirect(
                    url_for(
                        "draft.result",
                        game_id=game_id
                    )
                )


            return redirect(
                url_for(
                    "draft.game",
                    game_id=game_id
                )
            )


        # ---------------------------------------------
        # 일반 ALL-IN
        # ---------------------------------------------

        game["bid"] = amount

        game["leader"] = side


        game["log"].append(
            f"{game['players'][side]} → "
            f"{current['name']} "
            f"ALL-IN ${amount}"
        )


        # 상대 차례

        game["turn"] = (
            "b"
            if side == "a"
            else "a"
        )


        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )


    return redirect(
        url_for(
            "draft.game",
            game_id=game_id
        )
    )


# =========================================================
# 결과
# =========================================================

@draft_bp.route(
    "/game/<game_id>/result"
)
def result(game_id):

    game = GAMES.get(game_id)


    if not game:

        return "존재하지 않는 Draft 게임입니다.", 404


    return render_template(
        "draft_result.html",
        state=template_state(game),
        game=game,
        game_id=game_id
    )
