# ============================================================
# Draft Mode
# draft_routes.py
#
# 서버측 SQLite 저장 버전
#
# 중요:
#   - Flask session에는 게임 데이터를 저장하지 않는다.
#   - Player_pool.json은 절대 수정하지 않는다.
#   - 게임 상태는 SQLite에 JSON 형태로 저장한다.
#
# 게임 방식:
#   1vs1 경매
#   선수풀 = 설정 인원 × 2
#   경매 순서 = 랜덤
#   다음 선수 공개 X
#   첫 행동 = Player 1 / Player 2 중 먼저 행동한 사람
#   이후 = 서로 번갈아 행동
#   입찰금액 = 직접 입력
#   ALL-IN 가능
#   동일 금액 ALL-IN = ALL-IN한 사람 승리
#   둘 다 PASS = 선수풀 맨 뒤
#   포지션 정원 한쪽 완성 = 남은 해당 포지션 자동 배정
#
# ============================================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
)

import os
import json
import uuid
import random
import sqlite3
import threading
from datetime import datetime


# ============================================================
# Blueprint
# ============================================================

draft_bp = Blueprint(
    "draft",
    __name__,
    url_prefix="/draft"
)


# ============================================================
# 설정
# ============================================================

POSITION_KEYS = [
    "투수",
    "내야수",
    "외야수",
    "포수",
]


SOURCE_POSITION = {
    # 투수
    "선발": "투수",
    "불펜": "투수",
    "마무리": "투수",
    "투수": "투수",

    # 내야
    "내야": "내야수",
    "내야수": "내야수",

    # 외야
    "외야": "외야수",
    "외야수": "외야수",

    # 포수
    "포수": "포수",
}


# ============================================================
# SQLite 위치
#
# Render 환경에서는 환경변수 DRAFT_DB_PATH를 지정할 수 있다.
#
# 지정하지 않으면 /tmp 사용.
#
# 주의:
# Render 인스턴스가 완전히 재시작되면 /tmp DB는 사라질 수 있다.
# 하지만 세션 쿠키에는 게임 상태가 들어가지 않는다.
# ============================================================

DRAFT_DB_PATH = os.environ.get(
    "DRAFT_DB_PATH",
    "/tmp/draft_games.sqlite3"
)


# SQLite 동시 접근 보호
DB_LOCK = threading.RLock()


# ============================================================
# DB 연결
# ============================================================

def _db_connect():
    """
    SQLite 연결 생성.

    여러 Gunicorn worker가 같은 DB 파일을 사용할 수 있도록
    timeout을 충분히 준다.
    """

    conn = sqlite3.connect(
        DRAFT_DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def _ensure_db():
    """
    Draft 게임 테이블이 없으면 생성한다.
    """

    directory = os.path.dirname(
        os.path.abspath(DRAFT_DB_PATH)
    )

    if directory:
        os.makedirs(
            directory,
            exist_ok=True
        )

    with DB_LOCK:

        conn = _db_connect()

        try:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS draft_games (
                    game_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            conn.commit()

        finally:

            conn.close()


# 모듈 로드 시 DB 준비
_ensure_db()


# ============================================================
# 게임 상태 저장
# ============================================================

def save_state(
    game_id,
    state
):
    """
    게임 상태를 SQLite에 저장한다.

    Flask session을 전혀 사용하지 않는다.
    """

    state_json = json.dumps(
        state,
        ensure_ascii=False,
        separators=(",", ":")
    )

    now = datetime.utcnow().isoformat()

    with DB_LOCK:

        conn = _db_connect()

        try:

            conn.execute(
                """
                INSERT INTO draft_games
                (
                    game_id,
                    state_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(game_id)
                DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (
                    game_id,
                    state_json,
                    now,
                    now,
                )
            )

            conn.commit()

        finally:

            conn.close()


# ============================================================
# 게임 상태 불러오기
# ============================================================

def get_state(
    game_id
):
    """
    SQLite에서 게임 상태를 읽는다.
    """

    with DB_LOCK:

        conn = _db_connect()

        try:

            row = conn.execute(
                """
                SELECT state_json
                FROM draft_games
                WHERE game_id = ?
                """,
                (game_id,)
            ).fetchone()

        finally:

            conn.close()

    if row is None:
        return None

    try:

        return json.loads(
            row["state_json"]
        )

    except Exception:

        return None


# ============================================================
# 게임 삭제
# ============================================================

def delete_state(
    game_id
):
    """
    게임 상태 삭제.
    """

    with DB_LOCK:

        conn = _db_connect()

        try:

            conn.execute(
                """
                DELETE FROM draft_games
                WHERE game_id = ?
                """,
                (game_id,)
            )

            conn.commit()

        finally:

            conn.close()


# ============================================================
# 선수풀 파일 찾기
# ============================================================

def _find_player_pool():

    base = os.path.dirname(
        os.path.abspath(__file__)
    )

    candidates = [

        os.path.join(
            base,
            "Player_pool.json"
        ),

        os.path.join(
            base,
            "player_pool.json"
        ),

        os.path.join(
            base,
            "Player_pool.json.txt"
        ),

        os.path.join(
            base,
            "player_pool.json.txt"
        ),
    ]

    for path in candidates:

        if os.path.exists(path):

            return path

    raise FileNotFoundError(
        "Player_pool.json 파일을 찾을 수 없습니다."
    )


# ============================================================
# 선수풀 로드
# ============================================================

def load_players():

    path = _find_player_pool()

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if not isinstance(
        data,
        list
    ):

        raise ValueError(
            "Player_pool.json의 최상위 구조가 list가 아닙니다."
        )

    players = []

    for index, raw in enumerate(data):

        if not isinstance(
            raw,
            dict
        ):
            continue

        source_position = str(
            raw.get(
                "position",
                ""
            )
        ).strip()

        group = SOURCE_POSITION.get(
            source_position
        )

        if not group:
            continue

        name = str(
            raw.get(
                "name",
                ""
            )
        ).strip()

        if not name:
            continue

        # overall 숫자 변환
        try:

            overall = float(
                raw.get(
                    "overall",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            overall = 0

        player = {

            "pool_id": index,

            "name": name,

            "position": source_position,

            "group": group,

            "rank": raw.get(
                "rank",
                999
            ),

            "team": raw.get(
                "team",
                ""
            ),

            "overall": overall,
        }

        players.append(
            player
        )

    return players


# ============================================================
# 선수풀 보유 수
# ============================================================

def available_counts(
    players
):

    counts = {

        "투수": 0,

        "내야수": 0,

        "외야수": 0,

        "포수": 0,
    }

    for player in players:

        group = player.get(
            "group"
        )

        if group in counts:

            counts[group] += 1

    return counts


# ============================================================
# 게임용 선수풀 생성
# ============================================================

def make_player_pool(
    limits
):
    """
    설정 인원의 정확히 2배를 뽑는다.

    예:

        투수 2
        내야수 2
        외야수 2
        포수 1

    Player 1:
        투수 2
        내야수 2
        외야수 2
        포수 1

    Player 2:
        동일

    총 14명
    """

    players = load_players()

    counts = available_counts(
        players
    )

    required = {

        key: int(
            limits[key]
        ) * 2

        for key in POSITION_KEYS
    }

    # 선수풀 충분한지 확인
    for key in POSITION_KEYS:

        need = required[key]

        if need <= 0:
            continue

        have = counts.get(
            key,
            0
        )

        if have < need:

            raise ValueError(
                f"{key} 선수 풀이 부족합니다. "
                f"필요 {need}명 / "
                f"보유 {have}명"
            )

    selected = []

    # 포지션별 정확한 수량 선택
    for key in POSITION_KEYS:

        candidates = [

            p.copy()

            for p in players

            if p.get(
                "group"
            ) == key
        ]

        chosen = random.sample(
            candidates,
            required[key]
        )

        selected.extend(
            chosen
        )

    # 최종 경매 순서 랜덤
    random.shuffle(
        selected
    )

    return selected


# ============================================================
# 새로운 State
# ============================================================

def new_state(
    player_pool,
    initial_money,
    limits
):

    return {

        "players": {

            "a": "PLAYER 1",

            "b": "PLAYER 2",
        },

        "money": {

            "a": int(
                initial_money
            ),

            "b": int(
                initial_money
            ),
        },

        "spent": {

            "a": 0,

            "b": 0,
        },

        "rosters": {

            "a": [],

            "b": [],
        },

        "roster_size": sum(
            int(
                limits[key]
            )
            for key in POSITION_KEYS
        ),

        "limits": {

            key: int(
                limits[key]
            )

            for key in POSITION_KEYS
        },

        "pool": player_pool,

        "current": None,

        "current_bid": 0,

        "leader": None,

        "turn": None,

        "auction_started": False,

        "passed": {

            "a": False,

            "b": False,
        },

        "log": [],

        "done": False,

        "winner": None,

        "score": {

            "a": 0,

            "b": 0,
        },
    }


# ============================================================
# 로스터 카운트
# ============================================================

def roster_count(
    state,
    side,
    group
):

    return sum(

        1

        for player in state[
            "rosters"
        ][side]

        if player.get(
            "group"
        ) == group
    )


# ============================================================
# 로스터 전체 완성 여부
# ============================================================

def roster_full(
    state,
    side
):

    return (

        len(
            state["rosters"][side]
        )

        >=

        state["roster_size"]
    )


# ============================================================
# 특정 포지션 완성 여부
# ============================================================

def group_full(
    state,
    side,
    group
):

    return (

        roster_count(
            state,
            side,
            group
        )

        >=

        int(
            state["limits"].get(
                group,
                0
            )
        )
    )


# ============================================================
# 자동 배정
# ============================================================

def assign_if_position_forced(
    state
):
    """
    한쪽이 특정 포지션 정원을 채웠으면
    남은 그 포지션 선수는 상대방에게 자동 배정.

    현재 경매 중인 선수는 이 함수가 건드리지 않는다.
    """

    changed = True

    while changed:

        changed = False

        for player in list(
            state["pool"]
        ):

            group = player.get(
                "group"
            )

            if group not in POSITION_KEYS:
                continue

            a_full = group_full(
                state,
                "a",
                group
            )

            b_full = group_full(
                state,
                "b",
                group
            )

            # A가 완성 → B에게
            if a_full and not b_full:

                state["pool"].remove(
                    player
                )

                state[
                    "rosters"
                ]["b"].append(
                    player
                )

                state["log"].append(

                    "자동 배정: "
                    f"{player['name']} → "
                    f"{state['players']['b']}"
                )

                changed = True

                break

            # B가 완성 → A에게
            if b_full and not a_full:

                state["pool"].remove(
                    player
                )

                state[
                    "rosters"
                ]["a"].append(
                    player
                )

                state["log"].append(

                    "자동 배정: "
                    f"{player['name']} → "
                    f"{state['players']['a']}"
                )

                changed = True

                break


# ============================================================
# 다음 선수
# ============================================================

def next_player(
    state
):

    # 먼저 자동 배정
    assign_if_position_forced(
        state
    )

    # 둘 다 로스터가 완성된 경우
    if (
        roster_full(
            state,
            "a"
        )
        and
        roster_full(
            state,
            "b"
        )
    ):

        finish_game(
            state
        )

        return

    # 선수풀이 없으면 종료
    if not state["pool"]:

        finish_game(
            state
        )

        return

    # 다음 선수 하나만 꺼낸다.
    # 이후 선수들은 화면에 공개되지 않는다.
    player = state["pool"].pop(
        0
    )

    state["current"] = player

    state["current_bid"] = 0

    state["leader"] = None

    # 핵심:
    # 첫 행동은 어느 플레이어든 가능
    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,
    }


# ============================================================
# 점수 계산
# ============================================================

def calculate_scores(
    state
):

    score_a = sum(

        float(
            p.get(
                "overall",
                0
            )
        )

        for p in state[
            "rosters"
        ]["a"]
    )

    score_b = sum(

        float(
            p.get(
                "overall",
                0
            )
        )

        for p in state[
            "rosters"
        ]["b"]
    )

    return (

        round(
            score_a,
            1
        ),

        round(
            score_b,
            1
        )
    )


# ============================================================
# 게임 종료
# ============================================================

def finish_game(
    state
):

    # 남은 선수가 있다면 가능한 팀에 배정
    while state["pool"]:

        player = state["pool"].pop(
            0
        )

        a_full = roster_full(
            state,
            "a"
        )

        b_full = roster_full(
            state,
            "b"
        )

        if not a_full:

            state[
                "rosters"
            ]["a"].append(
                player
            )

        elif not b_full:

            state[
                "rosters"
            ]["b"].append(
                player
            )

    score_a, score_b = calculate_scores(
        state
    )

    if score_a > score_b:

        winner = "a"

    elif score_b > score_a:

        winner = "b"

    else:

        winner = "draw"

    state["winner"] = winner

    state["score"] = {

        "a": score_a,

        "b": score_b,
    }

    state["done"] = True

    state["current"] = None

    state["current_bid"] = 0

    state["leader"] = None

    state["turn"] = None


# ============================================================
# 선수 획득
# ============================================================

def award_player(
    state,
    side,
    price
):

    player = state.get(
        "current"
    )

    if player is None:

        raise ValueError(
            "현재 경매 중인 선수가 없습니다."
        )

    price = int(
        price
    )

    if price < 0:

        raise ValueError(
            "가격은 0 이상이어야 합니다."
        )

    if price > state[
        "money"
    ][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    state[
        "money"
    ][side] -= price

    state[
        "spent"
    ][side] += price

    state[
        "rosters"
    ][side].append(
        player
    )

    state["log"].append(

        f"{state['players'][side]} → "
        f"{player['name']} "
        f"(${price})"
    )

    # 현재 경매 초기화
    state["current"] = None

    state["current_bid"] = 0

    state["leader"] = None

    state["turn"] = None

    state["auction_started"] = False

    state["passed"] = {

        "a": False,

        "b": False,
    }

    # 자동 배정
    assign_if_position_forced(
        state
    )

    # 둘 다 로스터 완성
    if (
        roster_full(
            state,
            "a"
        )
        and
        roster_full(
            state,
            "b"
        )
    ):

        finish_game(
            state
        )

        return

    # 다음 선수
    next_player(
        state
    )


# ============================================================
# 첫 입찰
# ============================================================

def start_bid(
    state,
    side,
    amount
):

    amount = int(
        amount
    )

    if amount <= 0:

        raise ValueError(
            "입찰 금액은 1달러 이상이어야 합니다."
        )

    if amount > state[
        "money"
    ][side]:

        raise ValueError(
            "보유 자금보다 큰 금액을 입찰할 수 없습니다."
        )

    if roster_full(
        state,
        side
    ):

        raise ValueError(
            "이미 로스터가 완성되었습니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    state["current_bid"] = amount

    state["leader"] = side

    # 선공 이후 상대방 차례
    state["turn"] = (
        "b"
        if side == "a"
        else "a"
    )

    state["auction_started"] = True

    state["passed"] = {

        "a": False,

        "b": False,
    }

    state["log"].append(

        f"{state['players'][side]} "
        f"선공 입찰 ${amount}"
    )


# ============================================================
# 일반 입찰
# ============================================================

def normal_bid(
    state,
    side,
    amount
):

    amount = int(
        amount
    )

    current_bid = int(
        state["current_bid"]
    )

    # 반드시 현재가보다 높아야 함
    if amount <= current_bid:

        raise ValueError(
            "현재가보다 높은 금액을 입력하세요."
        )

    if amount > state[
        "money"
    ][side]:

        raise ValueError(
            "보유 자금보다 큰 금액입니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    state["current_bid"] = amount

    state["leader"] = side

    state["turn"] = (
        "b"
        if side == "a"
        else "a"
    )

    state["passed"][side] = False

    state["log"].append(

        f"{state['players'][side]} "
        f"→ ${amount}"
    )


# ============================================================
# PASS
# ============================================================

def pass_action(
    state,
    side
):

    other = (
        "b"
        if side == "a"
        else "a"
    )

    # ========================================================
    # 아직 아무도 입찰하지 않음
    # ========================================================

    if not state[
        "auction_started"
    ]:

        state[
            "passed"
        ][side] = True

        state["log"].append(

            f"{state['players'][side']} PASS"
        )

        # 둘 다 PASS
        if state[
            "passed"
        ][other]:

            player = state[
                "current"
            ]

            # 선수풀 맨 뒤로
            state[
                "pool"
            ].append(
                player
            )

            state["log"].append(

                f"{player['name']} "
                "→ 선수풀 맨 뒤"
            )

            state["current"] = None

            state["current_bid"] = 0

            state["leader"] = None

            state["turn"] = None

            state["auction_started"] = False

            state["passed"] = {

                "a": False,

                "b": False,
            }

            next_player(
                state
            )

        else:

            # 상대방에게 차례
            state["turn"] = other

        return

    # ========================================================
    # 이미 입찰 중
    # ========================================================

    # 선두가 PASS
    if state[
        "leader"
    ] == side:

        state["log"].append(

            f"{state['players'][side]} "
            "경매 포기"
        )

        # 상대방에게 현재가로 획득
        award_player(

            state,

            other,

            state[
                "current_bid"
            ]
        )

        return

    # ========================================================
    # 선두가 아닌 사람이 PASS
    # ========================================================

    state["log"].append(

        f"{state['players'][side]} PASS"
    )

    # 현재 선두가 획득
    award_player(

        state,

        state[
            "leader"
        ],

        state[
            "current_bid"
        ]
    )


# ============================================================
# ALL-IN
# ============================================================

def all_in(
    state,
    side
):

    money = int(
        state[
            "money"
        ][side]
    )

    if money <= 0:

        raise ValueError(
            "사용 가능한 자금이 없습니다."
        )

    group = state[
        "current"
    ]["group"]

    if group_full(
        state,
        side,
        group
    ):

        raise ValueError(
            "이 포지션은 이미 정원을 채웠습니다."
        )

    current_bid = int(
        state[
            "current_bid"
        ]
    )

    # ========================================================
    # 아직 경매 시작 전
    # ========================================================

    if not state[
        "auction_started"
    ]:

        amount = money

        state[
            "current_bid"
        ] = amount

        state[
            "leader"
        ] = side

        state["log"].append(

            f"{state['players'][side]} "
            f"ALL-IN ${amount}"
        )

        # 선공 ALL-IN은 즉시 획득
        award_player(

            state,

            side,

            amount
        )

        return

    # ========================================================
    # 이미 경매 중
    # ========================================================

    # 현재가보다 적으면 ALL-IN 불가능
    if money < current_bid:

        raise ValueError(

            "현재가보다 적은 금액으로 "
            "ALL-IN할 수 없습니다."
        )

    # 같은 금액이면 ALL-IN 우선
    if money == current_bid:

        state["log"].append(

            f"{state['players'][side]} "
            f"ALL-IN ${money} "
            "(동일 금액 우선)"
        )

        award_player(

            state,

            side,

            money
        )

        return

    # 더 높은 ALL-IN
    state[
        "current_bid"
    ] = money

    state[
        "leader"
    ] = side

    state["log"].append(

        f"{state['players'][side]} "
        f"ALL-IN ${money}"
    )

    # ALL-IN은 즉시 획득
    award_player(

        state,

        side,

        money
    )


# ============================================================
# 시작 화면
# ============================================================

@draft_bp.route(
    "",
    methods=["GET"]
)
def draft_home():

    return render_template(
        "draft_setup.html"
    )


# ============================================================
# 게임 생성
# ============================================================

@draft_bp.route(
    "/start",
    methods=["POST"]
)
def draft_start():

    try:

        # ----------------------------------------------------
        # 초기 자본
        # ----------------------------------------------------

        initial_money = int(
            request.form.get(
                "initial_money",
                20
            )
        )

        if initial_money <= 0:

            raise ValueError(
                "초기 자본은 1달러 이상이어야 합니다."
            )

        # ----------------------------------------------------
        # 포지션별 인원
        # ----------------------------------------------------

        limits = {

            "투수": int(
                request.form.get(
                    "pitchers",
                    2
                )
            ),

            "내야수": int(
                request.form.get(
                    "infielders",
                    2
                )
            ),

            "외야수": int(
                request.form.get(
                    "outfielders",
                    2
                )
            ),

            "포수": int(
                request.form.get(
                    "catchers",
                    1
                )
            ),
        }

        # 음수 방지
        for key in POSITION_KEYS:

            if limits[key] < 0:

                raise ValueError(
                    "선수 수는 0 이상이어야 합니다."
                )

        # 최소 1명
        if sum(
            limits.values()
        ) <= 0:

            raise ValueError(
                "최소 1명 이상의 선수를 설정하세요."
            )

        # ----------------------------------------------------
        # 선수풀 생성
        # ----------------------------------------------------

        player_pool = make_player_pool(
            limits
        )

        # ----------------------------------------------------
        # State 생성
        # ----------------------------------------------------

        state = new_state(

            player_pool,

            initial_money,

            limits
        )

        # ----------------------------------------------------
        # 플레이어 이름
        # ----------------------------------------------------

        player_a = request.form.get(
            "player_a",
            "PLAYER 1"
        ).strip()

        player_b = request.form.get(
            "player_b",
            "PLAYER 2"
        ).strip()

        state[
            "players"
        ]["a"] = (
            player_a
            or "PLAYER 1"
        )

        state[
            "players"
        ]["b"] = (
            player_b
            or "PLAYER 2"
        )

        # ----------------------------------------------------
        # 첫 선수
        # ----------------------------------------------------

        next_player(
            state
        )

        # ----------------------------------------------------
        # 게임 ID
        # ----------------------------------------------------

        game_id = uuid.uuid4().hex

        # ----------------------------------------------------
        # SQLite 저장
        # ----------------------------------------------------

        save_state(
            game_id,
            state
        )

        # ----------------------------------------------------
        # 게임 화면
        # ----------------------------------------------------

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    except Exception as e:

        return render_template(

            "draft_setup.html",

            error=str(e)
        )


# ============================================================
# 게임 화면
# ============================================================

@draft_bp.route(
    "/game/<game_id>",
    methods=["GET"]
)
def game(
    game_id
):

    state = get_state(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )

    # 게임 종료
    if state.get(
        "done"
    ):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )

    return render_template(

        "draft_game.html",

        state=state,

        game_id=game_id,

        error=None,
    )


# ============================================================
# 액션
# ============================================================

@draft_bp.route(
    "/game/<game_id>/action",
    methods=["POST"]
)
def action(
    game_id
):

    state = get_state(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )

    # 이미 종료
    if state.get(
        "done"
    ):

        return redirect(
            url_for(
                "draft.result",
                game_id=game_id
            )
        )

    error = None

    try:

        # ----------------------------------------------------
        # Player
        # ----------------------------------------------------

        side = request.form.get(
            "side"
        )

        if side not in (
            "a",
            "b"
        ):

            raise ValueError(
                "잘못된 플레이어입니다."
            )

        # ----------------------------------------------------
        # 현재 선수 확인
        # ----------------------------------------------------

        if state.get(
            "current"
        ) is None:

            raise ValueError(
                "현재 경매 중인 선수가 없습니다."
            )

        # ----------------------------------------------------
        # 차례 확인
        #
        # turn == None
        #   → 첫 행동
        #   → 누구든 먼저 누를 수 있음
        #
        # turn != None
        #   → 해당 플레이어만 행동 가능
        # ----------------------------------------------------

        if state.get(
            "turn"
        ) is not None:

            if state[
                "turn"
            ] != side:

                raise ValueError(
                    "상대방의 차례입니다."
                )

        # ----------------------------------------------------
        # Action
        # ----------------------------------------------------

        action_type = request.form.get(
            "action"
        )

        # ====================================================
        # BID
        # ====================================================

        if action_type == "bid":

            amount_raw = request.form.get(
                "amount",
                ""
            ).strip()

            if not amount_raw:

                raise ValueError(
                    "입찰 금액을 입력하세요."
                )

            try:

                amount = int(
                    amount_raw
                )

            except ValueError:

                raise ValueError(
                    "입찰 금액은 숫자로 입력하세요."
                )

            if amount <= 0:

                raise ValueError(
                    "입찰 금액은 1달러 이상이어야 합니다."
                )

            if not state[
                "auction_started"
            ]:

                # 첫 행동
                start_bid(

                    state,

                    side,

                    amount
                )

            else:

                # 이후 입찰
                normal_bid(

                    state,

                    side,

                    amount
                )

        # ====================================================
        # ALL-IN
        # ====================================================

        elif action_type == "allin":

            all_in(

                state,

                side
            )

        # ====================================================
        # PASS
        # ====================================================

        elif action_type == "pass":

            pass_action(

                state,

                side
            )

        else:

            raise ValueError(
                "알 수 없는 액션입니다."
            )

        # ----------------------------------------------------
        # 저장
        # ----------------------------------------------------

        save_state(
            game_id,
            state
        )

        # ----------------------------------------------------
        # 종료
        # ----------------------------------------------------

        if state.get(
            "done"
        ):

            return redirect(
                url_for(
                    "draft.result",
                    game_id=game_id
                )
            )

        # ----------------------------------------------------
        # 게임 화면
        # ----------------------------------------------------

        return redirect(
            url_for(
                "draft.game",
                game_id=game_id
            )
        )

    except Exception as e:

        error = str(e)

        # 오류가 발생하더라도 현재 상태 저장
        save_state(
            game_id,
            state
        )

        return render_template(

            "draft_game.html",

            state=state,

            game_id=game_id,

            error=error,
        )


# ============================================================
# 결과
# ============================================================

@draft_bp.route(
    "/game/<game_id>/result",
    methods=["GET"]
)
def result(
    game_id
):

    state = get_state(
        game_id
    )

    if state is None:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )

    # --------------------------------------------------------
    # 이전 버전 state 호환
    # --------------------------------------------------------

    if "rosters" not in state:

        return redirect(
            url_for(
                "draft.draft_home"
            )
        )

    # --------------------------------------------------------
    # 결과가 아직 없으면 계산
    # --------------------------------------------------------

    if not state.get(
        "done"
    ):

        score_a, score_b = calculate_scores(
            state
        )

        if score_a > score_b:

            winner = "a"

        elif score_b > score_a:

            winner = "b"

        else:

            winner = "draw"

        state["score"] = {

            "a": score_a,

            "b": score_b,
        }

        state["winner"] = winner

        state["done"] = True

        save_state(
            game_id,
            state
        )

    # --------------------------------------------------------
    # 결과 화면
    # --------------------------------------------------------

    return render_template(

        "draft_result.html",

        state=state,

        game_id=game_id
    )


# ============================================================
# 다시 시작
# ============================================================

@draft_bp.route(
    "/reset/<game_id>",
    methods=["GET"]
)
def reset(
    game_id
):

    delete_state(
        game_id
    )

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )


# ============================================================
# 게임 삭제 API 성격의 내부용 라우트
# ============================================================

@draft_bp.route(
    "/delete/<game_id>",
    methods=["POST"]
)
def delete_game(
    game_id
):

    delete_state(
        game_id
    )

    return redirect(
        url_for(
            "draft.draft_home"
        )
    )
