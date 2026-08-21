# =========================================================
# draft.py
# Draft Mode Game Engine
#
# 포지션:
#   선발 / 불펜 / 마무리 / 포수 / 내야 / 외야
#
# 선수풀:
#   player_pool.json
#
# 핵심 규칙:
#   - 2인 1대1 경매
#   - 포지션별 필요 인원 × 2 = 선수풀 등록 인원
#   - 경매 순서는 랜덤
#   - 다음 플레이어는 공개하지 않음
#   - 선공은 고정 순서가 아니라 매 경매 랜덤
#   - 두 명 모두 PASS → 선수는 선수풀 뒤로 이동
#   - 한 명이 포지션을 모두 채우면 해당 포지션의 남은 선수는 상대에게만 갈 수 있음
#   - 입찰 금액은 +1 고정이 아니라 원하는 금액 직접 입력 가능
#   - ALL-IN은 동일 금액일 경우 ALL-IN한 사람이 승리
# =========================================================

import json
import os
import random
import uuid
from copy import deepcopy


POSITIONS = (
    "선발",
    "불펜",
    "마무리",
    "포수",
    "내야",
    "외야",
)


# =========================================================
# player_pool.json
# =========================================================

def _pool_path():

    base = os.path.dirname(os.path.abspath(__file__))

    paths = [
        os.path.join(base, "player_pool.json"),
        os.path.join(base, "data", "player_pool.json"),
        os.path.join(base, "player_pool.json.txt"),
        os.path.join(base, "data", "player_pool.json.txt"),
    ]

    for path in paths:

        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        "player_pool.json을 찾을 수 없습니다."
    )


def load_player_pool():

    path = _pool_path()

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if not isinstance(data, list):

        raise ValueError(
            "player_pool.json은 선수 객체의 배열이어야 합니다."
        )

    return data


# =========================================================
# 포지션 정규화
# =========================================================

def normalize_position(player):

    raw = (
        player.get("position")
        or player.get("group")
        or player.get("positions")
        or ""
    )

    raw = str(raw).strip()

    aliases = {

        # 선발
        "SP": "선발",
        "선발투수": "선발",
        "선발 투수": "선발",

        # 불펜
        "RP": "불펜",
        "불펜투수": "불펜",
        "불펜 투수": "불펜",

        # 마무리
        "CP": "마무리",
        "CL": "마무리",
        "마무리투수": "마무리",
        "마무리 투수": "마무리",

        # 포수
        "C": "포수",
        "CATCHER": "포수",

        # 내야
        "IF": "내야",
        "INF": "내야",
        "INFIELD": "내야",
        "내야수": "내야",

        # 외야
        "OF": "외야",
        "OUTFIELD": "외야",
        "외야수": "외야",
    }

    return aliases.get(raw, raw)


# =========================================================
# 선수 변환
# =========================================================

def normalize_player(player):

    position = normalize_position(player)

    overall = player.get("overall")

    try:
        overall = int(float(overall))
    except Exception:
        overall = 0

    rank = player.get("rank")

    try:
        rank = int(rank)
    except Exception:
        rank = None

    return {

        "id": (
            player.get("id")
            or str(uuid.uuid4())
        ),

        "name": (
            player.get("name")
            or player.get("player")
            or player.get("선수")
            or "이름 없음"
        ),

        "team": (
            player.get("team")
            or player.get("대표팀")
            or ""
        ),

        "position": position,

        "group": position,

        "overall": overall,

        "rank": rank,
    }


# =========================================================
# 포지션별 선수풀 생성
# =========================================================

def build_position_pool(limits):

    players = load_player_pool()

    by_position = {
        pos: []
        for pos in POSITIONS
    }

    for raw in players:

        player = normalize_player(raw)

        pos = player["position"]

        if pos not in by_position:
            continue

        by_position[pos].append(player)

    result = []

    for position in POSITIONS:

        required = int(
            limits.get(position, 0)
        )

        if required <= 0:
            continue

        # 양 팀이 각각 required명을 가져야 하므로 ×2
        needed = required * 2

        available = by_position[position]

        if len(available) < needed:

            raise ValueError(
                f"{position} 선수 풀이 부족합니다. "
                f"필요 {needed}명 / 보유 {len(available)}명"
            )

        random.shuffle(available)

        selected = available[:needed]

        result.extend(
            deepcopy(selected)
        )

    # 전체 경매 순서는 랜덤
    random.shuffle(result)

    return result


# =========================================================
# 기본 상태
# =========================================================

def create_state(
    player_a,
    player_b,
    initial_money,
    limits,
):

    limits = {
        pos: int(limits.get(pos, 0))
        for pos in POSITIONS
    }

    roster_size = sum(
        limits.values()
    )

    pool = build_position_pool(
        limits
    )

    state = {

        "players": {
            "a": player_a,
            "b": player_b,
        },

        "money": {
            "a": int(initial_money),
            "b": int(initial_money),
        },

        "spent": {
            "a": 0,
            "b": 0,
        },

        "rosters": {
            "a": [],
            "b": [],
        },

        "limits": limits,

        "roster_size": roster_size,

        # 실제 아직 경매되지 않은 선수
        "pool": pool,

        # PASS → 뒤로 보낼 선수
        "returned_pool": [],

        # 현재 선수
        "current": None,

        # 현재 입찰가
        "bid": 0,

        # 최고 입찰자
        "leader": None,

        # 현재 경매에서 PASS한 사람
        "passed": [],

        # 마지막 입찰 행동
        "last_action": None,

        # 현재 선공
        "turn": random.choice(
            ["a", "b"]
        ),

        # 경매 번호
        "round": 0,

        # 로그
        "log": [],

        # 종료 여부
        "finished": False,

        # 결과
        "result": None,

        # 게임 ID
        "game_id": str(uuid.uuid4()),

        # 게임 버전
        "version": "4.0",
    }

    return state


# =========================================================
# 다음 선수
# =========================================================

def _next_player(state):

    # 일반 pool이 남아 있으면 먼저 사용
    if state["pool"]:

        return state["pool"].pop(0)

    # PASS된 선수들은 모든 신규 선수가 끝난 뒤 다시 등장
    if state["returned_pool"]:

        state["pool"] = state["returned_pool"]

        state["returned_pool"] = []

        random.shuffle(
            state["pool"]
        )

        return state["pool"].pop(0)

    return None


# =========================================================
# 현재 선수 시작
# =========================================================

def start_next_auction(state):

    # 게임 종료 검사
    if _is_finished(state):

        _finish(state)

        return state

    player = _next_player(state)

    if player is None:

        _finish(state)

        return state

    state["current"] = player

    state["bid"] = 0

    state["leader"] = None

    state["passed"] = []

    state["last_action"] = None

    # 매 선수마다 선공 랜덤
    state["turn"] = random.choice(
        ["a", "b"]
    )

    state["round"] += 1

    state["log"].append(
        f"새로운 선수 등장: "
        f"{player['name']} "
        f"({player['position']})"
    )

    return state


# =========================================================
# 포지션 충족 여부
# =========================================================

def roster_count(
    state,
    side,
    position,
):

    return sum(
        1
        for player in state["rosters"][side]
        if player.get("position") == position
    )


def position_full(
    state,
    side,
    position,
):

    return (
        roster_count(
            state,
            side,
            position
        )
        >= state["limits"].get(
            position,
            0
        )
    )


# =========================================================
# 전체 로스터 충족
# =========================================================

def roster_full(
    state,
    side,
):

    return (
        len(state["rosters"][side])
        >= state["roster_size"]
    )


# =========================================================
# 선수가 해당 팀에 갈 수 있는가
# =========================================================

def can_take_player(
    state,
    side,
    player=None,
):

    if player is None:
        player = state["current"]

    if player is None:
        return False

    position = player["position"]

    # 전체 로스터가 이미 끝난 팀
    if roster_full(
        state,
        side
    ):
        return False

    # 해당 포지션이 꽉 찬 팀
    if position_full(
        state,
        side,
        position
    ):
        return False

    return True


# =========================================================
# 두 팀 모두 해당 선수를 원하지 않는 경우
# =========================================================

def _return_current_player(state):

    player = state["current"]

    if player is None:
        return

    state["returned_pool"].append(
        player
    )

    state["log"].append(
        f"{player['name']} "
        f"→ 선수풀 맨 뒤로 이동"
    )


# =========================================================
# 턴 교체
# =========================================================

def _other(side):

    return "b" if side == "a" else "a"


# =========================================================
# 입찰
# =========================================================

def bid(
    state,
    side,
    amount,
):

    if state["finished"]:
        return False, "이미 게임이 종료되었습니다."

    if state["current"] is None:
        return False, "현재 경매 선수가 없습니다."

    if side not in ("a", "b"):
        return False, "잘못된 플레이어입니다."

    if side != state["turn"]:
        return False, "현재 선공 플레이어의 차례가 아닙니다."

    if not can_take_player(
        state,
        side
    ):
        return False, "이 선수의 포지션을 더 이상 채울 수 없습니다."

    try:
        amount = int(amount)
    except Exception:
        return False, "입찰 금액은 숫자여야 합니다."

    if amount <= 0:
        return False, "입찰 금액은 1달러 이상이어야 합니다."

    money = state["money"][side]

    if amount > money:
        return False, "보유 자금보다 많이 입찰할 수 없습니다."

    current_bid = state["bid"]

    if current_bid == 0:

        if amount < 1:
            return False, "첫 입찰은 최소 $1입니다."

    else:

        if amount <= current_bid:
            return False, (
                f"현재가 ${current_bid}보다 "
                "높게 입찰해야 합니다."
            )

    state["bid"] = amount

    state["leader"] = side

    state["last_action"] = "bid"

    state["passed"] = []

    state["log"].append(
        f"{state['players'][side]} "
        f"→ ${amount} 입찰"
    )

    # 다음 플레이어에게 턴
    state["turn"] = _other(side)

    return True, None


# =========================================================
# ALL-IN
# =========================================================

def all_in(
    state,
    side,
):

    if state["finished"]:
        return False, "이미 게임이 종료되었습니다."

    if state["current"] is None:
        return False, "현재 경매 선수가 없습니다."

    if side != state["turn"]:
        return False, "현재 선공 플레이어의 차례가 아닙니다."

    if not can_take_player(
        state,
        side
    ):
        return False, "이 선수의 포지션을 더 이상 채울 수 없습니다."

    amount = state["money"][side]

    if amount <= 0:
        return False, "올인할 자금이 없습니다."

    current_bid = state["bid"]

    # 현재가보다 작으면 올인 불가능
    if amount < current_bid:
        return False, "현재가보다 낮은 올인은 할 수 없습니다."

    # 동일 금액이라도 ALL-IN 우선
    state["bid"] = amount

    state["leader"] = side

    state["last_action"] = "all_in"

    state["log"].append(
        f"{state['players'][side]} "
        f"→ ${amount} ALL-IN"
    )

    # 상대가 대응
    state["turn"] = _other(side)

    return True, None


# =========================================================
# PASS
# =========================================================

def pass_turn(
    state,
    side,
):

    if state["finished"]:
        return False, "이미 게임이 종료되었습니다."

    if state["current"] is None:
        return False, "현재 경매 선수가 없습니다."

    if side != state["turn"]:
        return False, "현재 플레이어의 차례가 아닙니다."

    state["passed"].append(
        side
    )

    state["log"].append(
        f"{state['players'][side]} → PASS"
    )

    # =====================================================
    # 아직 아무도 입찰하지 않았다면
    # 한 명 PASS → 상대가 결정
    # =====================================================

    if state["leader"] is None:

        other = _other(side)

        # 상대도 PASS
        if other in state["passed"]:

            _return_current_player(
                state
            )

            state["current"] = None

            return True, "both_pass"

        # 상대에게 결정권
        state["turn"] = other

        return True, None

    # =====================================================
    # 이미 누군가 입찰한 상태
    # =====================================================

    leader = state["leader"]

    # 입찰자가 PASS했다는 것은
    # 현재 입찰 포기
    if side == leader:

        other = _other(side)

        # 상대가 아직 PASS하지 않았다면
        if other not in state["passed"]:

            state["turn"] = other

            state["leader"] = other

            return True, None

    # =====================================================
    # 상대가 PASS하면 현재 leader가 낙찰
    # =====================================================

    if state["leader"]:

        winner = state["leader"]

        _award_player(
            state,
            winner,
            state["bid"]
        )

        return True, "sold"

    return True, None


# =========================================================
# 선수 낙찰
# =========================================================

def _award_player(
    state,
    side,
    amount,
):

    player = state["current"]

    if player is None:
        return

    position = player["position"]

    # 최종 방어
    if not can_take_player(
        state,
        side,
        player
    ):

        other = _other(side)

        if can_take_player(
            state,
            other,
            player
        ):
            side = other

        else:
            _return_current_player(
                state
            )

            state["current"] = None

            return

    state["money"][side] -= amount

    state["spent"][side] += amount

    state["rosters"][side].append(
        deepcopy(player)
    )

    state["log"].append(
        f"{state['players'][side]} "
        f"→ {player['name']} "
        f"({position}) "
        f"${amount} 낙찰"
    )

    # 현재 경매 초기화
    state["current"] = None

    state["bid"] = 0

    state["leader"] = None

    state["passed"] = []

    state["last_action"] = None

    # 게임 종료
    if _is_finished(state):

        _finish(state)

        return

    # 다음 선수
    start_next_auction(
        state
    )


# =========================================================
# ALL-IN 동률 판정
# =========================================================

def resolve_all_in_tie(
    state,
):

    if not state["current"]:
        return

    if state["last_action"] != "all_in":
        return

    leader = state["leader"]

    if not leader:
        return

    other = _other(leader)

    # 상대가 같은 금액으로 ALL-IN
    if (
        state["bid"]
        == state["money"][other]
        + state["spent"][other]
    ):

        _award_player(
            state,
            leader,
            state["bid"]
        )


# =========================================================
# 게임 종료 판단
# =========================================================

def _is_finished(state):

    for side in ("a", "b"):

        if roster_full(
            state,
            side
        ):
            return True

    return False


# =========================================================
# 결과 계산
# =========================================================

def calculate_result(state):

    scores = {
        "a": 0,
        "b": 0,
    }

    position_scores = {
        "a": {},
        "b": {},
    }

    for side in ("a", "b"):

        for position in POSITIONS:

            players = [
                p
                for p in state["rosters"][side]
                if p["position"] == position
            ]

            total = sum(
                p.get("overall", 0)
                for p in players
            )

            position_scores[side][position] = total

            scores[side] += total

    if scores["a"] > scores["b"]:

        winner = "a"

    elif scores["b"] > scores["a"]:

        winner = "b"

    else:

        # 총 OVR 동률이면
        # 남은 자금이 많은 쪽
        if state["money"]["a"] > state["money"]["b"]:
            winner = "a"

        elif state["money"]["b"] > state["money"]["a"]:
            winner = "b"

        else:
            winner = "draw"

    return {

        "winner": winner,

        "scores": scores,

        "position_scores": position_scores,

        "players": {
            "a": deepcopy(
                state["rosters"]["a"]
            ),
            "b": deepcopy(
                state["rosters"]["b"]
            ),
        },

        "money": deepcopy(
            state["money"]
        ),

        "spent": deepcopy(
            state["spent"]
        ),
    }


# =========================================================
# 게임 종료
# =========================================================

def _finish(state):

    if state.get("finished"):
        return

    state["finished"] = True

    state["current"] = None

    state["result"] = calculate_result(
        state
    )

    winner = state["result"]["winner"]

    if winner == "draw":

        state["log"].append(
            "🏁 최종 결과: 무승부"
        )

    else:

        state["log"].append(
            "🏆 최종 승자: "
            f"{state['players'][winner]}"
        )


# =========================================================
# 외부에서 사용하는 액션 함수
# =========================================================

def process_action(
    state,
    side,
    action,
    amount=None,
):

    if state.get("finished"):

        return False, "게임이 종료되었습니다."

    if action == "bid":

        ok, msg = bid(
            state,
            side,
            amount
        )

        return ok, msg

    if action == "allin":

        ok, msg = all_in(
            state,
            side
        )

        return ok, msg

    if action == "pass":

        ok, msg = pass_turn(
            state,
            side
        )

        # 두 명 모두 PASS
        if ok and msg == "both_pass":

            start_next_auction(
                state
            )

        return ok, msg

    return False, "알 수 없는 액션입니다."


# =========================================================
# 게임 생성
# =========================================================

def create_game(
    player_a="PLAYER A",
    player_b="PLAYER B",
    initial_money=10,
    limits=None,
):

    if limits is None:

        limits = {
            "선발": 1,
            "불펜": 1,
            "마무리": 1,
            "포수": 1,
            "내야": 2,
            "외야": 2,
        }

    state = create_state(
        player_a,
        player_b,
        initial_money,
        limits
    )

    start_next_auction(
        state
    )

    return state
