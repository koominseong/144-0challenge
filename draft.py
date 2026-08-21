import random

from copy import deepcopy

from dynasty_utils import get_supabase


# =========================================================
# 포지션
# =========================================================

POSITIONS = (
    "P",
    "IF",
    "OF",
    "C",
)


# 한글 이름
POSITION_NAMES = {
    "P": "투수",
    "IF": "내야수",
    "OF": "외야수",
    "C": "포수",
}


# =========================================================
# 선수 포지션 판별
# =========================================================

def _group(player):

    raw = str(
        player.get("positions")
        or player.get("position")
        or ""
    ).upper()


    values = {
        x.strip()
        for x in
        raw
        .replace("/", ",")
        .replace("|", ",")
        .split(",")
        if x.strip()
    }


    # 포수
    if values & {
        "C",
        "CATCHER",
        "포수"
    }:

        return "C"


    # 투수
    if values & {
        "P",
        "SP",
        "RP",
        "CP",
        "투수"
    }:

        return "P"


    # stamina가 존재하면 투수로 취급
    if player.get("stamina") is not None:

        return "P"


    # 내야
    if values & {
        "1B",
        "2B",
        "3B",
        "SS",
        "IF",
        "INF",
        "내야",
        "내야수"
    }:

        return "IF"


    # 나머지는 외야
    return "OF"


# =========================================================
# OVR
# =========================================================

def _ovr(player):

    try:

        return float(
            player.get("overall")
            or 0
        )

    except Exception:

        return 0


# =========================================================
# 선수 안전 데이터
# =========================================================

def _safe(player):

    group = _group(player)


    return {

        "id":
            player.get("id"),


        "name":
            player.get("name")
            or "이름 없음",


        # 기존 코드 호환
        "position":
            group,


        # 새 HTML 호환
        "group":
            POSITION_NAMES[group],


        "overall":
            _ovr(player),


        "positions":
            player.get("positions")
            or player.get("position")
            or "",


        "team":
            player.get("team")
            or player.get("team_name")
            or "",

    }


# =========================================================
# DB에서 게임 가져오기
# =========================================================

def _load(game_id):

    sb = get_supabase()


    rows = (
        sb
        .table("draft_game")
        .select("*")
        .eq("id", str(game_id))
        .execute()
        .data
    )


    if not rows:

        raise ValueError(
            "Draft game not found"
        )


    return rows[0]


# =========================================================
# 상태 저장
# =========================================================

def _save(game_id, state):

    sb = get_supabase()


    return (
        sb
        .table("draft_game")
        .update({
            "state": state,
            "finished":
                state.get(
                    "finished",
                    False
                )
        })
        .eq("id", str(game_id))
        .execute()
        .data[0]
    )


# =========================================================
# 기존 게임 STATE 보정
#
# 중요:
# 예전 버전에서 players가 없는 게임도
# 여기서 자동으로 복구한다.
# =========================================================

def _normalize_state(state):

    if not isinstance(state, dict):

        state = {}


    # -----------------------------------------------------
    # players
    # -----------------------------------------------------

    players = state.get("players")


    if not isinstance(players, dict):

        players = {}


    # 예전 버전에서 이름이 다른 경우
    if not players.get("a"):

        players["a"] = (
            state.get("player_a")
            or state.get("player1")
            or "PLAYER A"
        )


    if not players.get("b"):

        players["b"] = (
            state.get("player_b")
            or state.get("player2")
            or "PLAYER B"
        )


    state["players"] = players


    # -----------------------------------------------------
    # limits
    # -----------------------------------------------------

    limits = state.get("limits")


    if not isinstance(limits, dict):

        limits = {}


    # 기존 코드 포지션
    limits["P"] = int(
        limits.get(
            "P",
            limits.get("투수", 2)
        )
        or 0
    )


    limits["IF"] = int(
        limits.get(
            "IF",
            limits.get("내야수", 2)
        )
        or 0
    )


    limits["OF"] = int(
        limits.get(
            "OF",
            limits.get("외야수", 2)
        )
        or 0
    )


    limits["C"] = int(
        limits.get(
            "C",
            limits.get("포수", 1)
        )
        or 0
    )


    # HTML에서 한글 key를 사용하는 경우도 지원
    limits["투수"] = limits["P"]

    limits["내야수"] = limits["IF"]

    limits["외야수"] = limits["OF"]

    limits["포수"] = limits["C"]


    state["limits"] = limits


    # -----------------------------------------------------
    # roster size
    # -----------------------------------------------------

    if not state.get("roster_size"):

        state["roster_size"] = sum(
            limits[x]
            for x in POSITIONS
        )


    # -----------------------------------------------------
    # money
    # -----------------------------------------------------

    money = state.get("money")


    if not isinstance(money, dict):

        initial = int(
            state.get(
                "initial_money",
                20
            )
            or 20
        )

        money = {
            "a": initial,
            "b": initial
        }


    else:

        money.setdefault(
            "a",
            state.get(
                "initial_money",
                20
            )
        )

        money.setdefault(
            "b",
            state.get(
                "initial_money",
                20
            )
        )


    state["money"] = money


    # -----------------------------------------------------
    # spent
    # -----------------------------------------------------

    spent = state.get("spent")


    if not isinstance(spent, dict):

        spent = {
            "a": 0,
            "b": 0
        }


    spent.setdefault("a", 0)

    spent.setdefault("b", 0)


    state["spent"] = spent


    # -----------------------------------------------------
    # roster
    # -----------------------------------------------------

    rosters = state.get("rosters")


    if not isinstance(rosters, dict):

        rosters = {
            "a": [],
            "b": []
        }


    rosters.setdefault("a", [])

    rosters.setdefault("b", [])


    # 기존 선수 데이터에도 group 보정
    for side in ("a", "b"):

        fixed = []

        for player in rosters[side]:

            if not isinstance(player, dict):

                continue


            p = dict(player)


            position = (
                p.get("position")
                or p.get("group")
                or "OF"
            )


            # 한글 → 코드
            position_map = {
                "투수": "P",
                "내야수": "IF",
                "외야수": "OF",
                "포수": "C",
            }


            position = position_map.get(
                position,
                position
            )


            p["position"] = position

            p["group"] = POSITION_NAMES.get(
                position,
                "외야수"
            )


            fixed.append(p)


        rosters[side] = fixed


    state["rosters"] = rosters


    # -----------------------------------------------------
    # queue
    # -----------------------------------------------------

    if not isinstance(
        state.get("queue"),
        list
    ):

        state["queue"] = []


    # -----------------------------------------------------
    # current
    # -----------------------------------------------------

    current = state.get("current")


    if isinstance(current, dict):

        p = dict(current)


        position = (
            p.get("position")
            or p.get("group")
            or "OF"
        )


        position_map = {
            "투수": "P",
            "내야수": "IF",
            "외야수": "OF",
            "포수": "C",
        }


        position = position_map.get(
            position,
            position
        )


        p["position"] = position

        p["group"] = POSITION_NAMES.get(
            position,
            "외야수"
        )


        state["current"] = p


    # -----------------------------------------------------
    # bid
    # -----------------------------------------------------

    if state.get("current_bid") is None:

        state["current_bid"] = int(
            state.get("bid", 0)
            or 0
        )


    # HTML 호환용
    state["bid"] = state["current_bid"]


    # -----------------------------------------------------
    # leader
    # -----------------------------------------------------

    state.setdefault(
        "leader",
        None
    )


    # -----------------------------------------------------
    # all in
    # -----------------------------------------------------

    state.setdefault(
        "all_in",
        None
    )


    # -----------------------------------------------------
    # pass
    # -----------------------------------------------------

    passed = state.get("passed")


    if not isinstance(passed, dict):

        passed = {
            "a": False,
            "b": False
        }


    passed.setdefault("a", False)

    passed.setdefault("b", False)


    state["passed"] = passed


    # -----------------------------------------------------
    # turn
    # -----------------------------------------------------

    state.setdefault(
        "turn",
        None
    )


    # -----------------------------------------------------
    # log
    # -----------------------------------------------------

    if not isinstance(
        state.get("log"),
        list
    ):

        state["log"] = []


    # -----------------------------------------------------
    # finished
    # -----------------------------------------------------

    state.setdefault(
        "finished",
        False
    )


    # -----------------------------------------------------
    # result
    # -----------------------------------------------------

    state.setdefault(
        "result",
        None
    )


    return state


# =========================================================
# 필요한 포지션 수
# =========================================================

def _need(
    state,
    side,
    position
):

    return (
        state["limits"][position]
        -
        sum(
            p.get("position") == position
            for p in state["rosters"][side]
        )
    )


# =========================================================
# 로스터 완성 여부
# =========================================================

def _full(
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


# =========================================================
# 다음 선수
# =========================================================

def _next(state):

    if _full(state, "a"):

        return


    if _full(state, "b"):

        return


    while state["queue"]:

        player = state["queue"].pop(0)

        position = player["position"]


        need_a = _need(
            state,
            "a",
            position
        )


        need_b = _need(
            state,
            "b",
            position
        )


        # 양쪽 모두 해당 포지션이 꽉 참
        if need_a <= 0 and need_b <= 0:

            continue


        # A가 해당 포지션을 다 채움
        if need_a <= 0:

            state["rosters"]["b"].append(
                player
            )

            state["log"].append(
                f"📌 {player['name']} → "
                f"{state['players']['b']} 자동 배정"
            )

            continue


        # B가 해당 포지션을 다 채움
        if need_b <= 0:

            state["rosters"]["a"].append(
                player
            )

            state["log"].append(
                f"📌 {player['name']} → "
                f"{state['players']['a']} 자동 배정"
            )

            continue


        # 경매 시작
        state["current"] = player

        state["current_bid"] = 0

        state["bid"] = 0

        state["leader"] = None

        state["all_in"] = None

        state["passed"] = {
            "a": False,
            "b": False
        }

        state["turn"] = random.choice(
            ["a", "b"]
        )

        return


    # 선수풀이 완전히 비었으면 종료
    if not state.get("current"):

        _finish(state)


# =========================================================
# 결과 계산
# =========================================================

def _result(state):

    def power(side):

        players = state["rosters"][side]


        if not players:

            return 0


        average = (
            sum(
                _ovr(p)
                for p in players
            )
            /
            len(players)
        )


        bonus = sum(
            _need(
                state,
                side,
                position
            ) == 0
            for position in POSITIONS
        ) * 1.5


        return round(
            average + bonus,
            2
        )


    power_a = power("a")

    power_b = power("b")


    random.seed(
        state.get(
            "seed",
            1
        )
        +
        len(
            state.get(
                "log",
                []
            )
        )
    )


    score_a = 0

    score_b = 0


    for _ in range(9):

        prob_a = max(
            .05,
            min(
                .45,
                .18
                +
                (power_a - power_b)
                * .012
            )
        )


        prob_b = max(
            .05,
            min(
                .45,
                .18
                +
                (power_b - power_a)
                * .012
            )
        )


        if random.random() < prob_a:

            score_a += 1


        if random.random() < prob_b:

            score_b += 1


    if score_a == score_b:

        if power_a >= power_b:

            score_a += 1

        else:

            score_b += 1


    return {

        "winner":
            "a"
            if score_a > score_b
            else "b",


        "score": {
            "a": int(score_a),
            "b": int(score_b)
        },


        "strength": {
            "a": power_a,
            "b": power_b
        }

    }


# =========================================================
# 종료
# =========================================================

def _finish(state):

    for side, other in (
        ("a", "b"),
        ("b", "a")
    ):

        if (
            _full(state, side)
            and
            not _full(state, other)
        ):

            remaining = list(
                state["queue"]
            )


            for player in remaining:

                if (
                    _need(
                        state,
                        other,
                        player["position"]
                    )
                    >
                    0
                ):

                    state["rosters"][other].append(
                        player
                    )


            state["queue"] = []

            state["current"] = None

            state["finished"] = True

            state["result"] = _result(
                state
            )

            return


    if (
        _full(state, "a")
        and
        _full(state, "b")
    ):

        state["current"] = None

        state["finished"] = True

        state["result"] = _result(
            state
        )


# =========================================================
# 게임 생성
# =========================================================

def create_game(
    save_id,
    limits,
    money,
    player_a="PLAYER A",
    player_b="PLAYER B"
):

    limits = {

        "P":
            max(
                0,
                int(
                    limits.get(
                        "P",
                        0
                    )
                )
            ),

        "IF":
            max(
                0,
                int(
                    limits.get(
                        "IF",
                        0
                    )
                )
            ),

        "OF":
            max(
                0,
                int(
                    limits.get(
                        "OF",
                        0
                    )
                )
            ),

        "C":
            max(
                0,
                int(
                    limits.get(
                        "C",
                        0
                    )
                )
            ),
    }


    money = int(money)


    roster_size = sum(
        limits.values()
    )


    if roster_size < 1:

        raise ValueError(
            "선수 구성을 확인하세요."
        )


    if money < 1:

        raise ValueError(
            "초기 자본은 1 이상이어야 합니다."
        )


    # -----------------------------------------------------
    # 선수 DB
    # -----------------------------------------------------

    rows = (
        get_supabase()
        .table("dynasty_player")
        .select("*")
        .execute()
        .data
        or []
    )


    rows = [
        p
        for p in rows
        if not p.get("retired")
    ]


    by = {
        position: []
        for position in POSITIONS
    }


    for player in rows:

        group = _group(player)


        if group in by:

            by[group].append(
                player
            )


    pool = []


    # 각 포지션은 2팀 분량
    for position, count in limits.items():

        need = count * 2


        random.shuffle(
            by[position]
        )


        if len(by[position]) < need:

            raise ValueError(
                f"{POSITION_NAMES[position]} "
                f"선수 풀이 부족합니다. "
                f"필요 {need}명 / "
                f"보유 {len(by[position])}명"
            )


        pool.extend(
            _safe(player)
            for player
            in by[position][:need]
        )


    # 경매 순서 랜덤
    random.shuffle(pool)


    state = {

        "version": 2,

        "seed":
            random.randint(
                1,
                10**9
            ),

        "save_id":
            save_id,


        "players": {

            "a":
                player_a
                or "PLAYER A",

            "b":
                player_b
                or "PLAYER B",

        },


        "limits": {

            **limits,

            "투수":
                limits["P"],

            "내야수":
                limits["IF"],

            "외야수":
                limits["OF"],

            "포수":
                limits["C"],

        },


        "roster_size":
            roster_size,


        "initial_money":
            money,


        "money": {

            "a": money,

            "b": money,

        },


        "spent": {

            "a": 0,

            "b": 0,

        },


        "rosters": {

            "a": [],

            "b": [],

        },


        "queue":
            pool,


        "current":
            None,


        "current_bid":
            0,


        "bid":
            0,


        "leader":
            None,


        "all_in":
            None,


        "passed": {

            "a": False,

            "b": False,

        },


        "turn":
            None,


        "finished":
            False,


        "result":
            None,


        "log": [

            "🎲 경매 순서를 랜덤으로 섞었습니다."

        ]

    }


    sb = get_supabase()


    row = (
        sb
        .table("draft_game")
        .insert({
            "save_id": save_id,
            "state": state,
            "finished": False
        })
        .execute()
        .data[0]
    )


    _next(state)


    return _save(
        row["id"],
        state
    )


# =========================================================
# 게임 로드
# =========================================================

def load_game(game_id):

    row = _load(game_id)


    state = _normalize_state(
        deepcopy(
            row.get("state") or {}
        )
    )


    # 기존 게임의 state도 DB에
    # 자동으로 보정해서 저장
    if state != row.get("state"):

        try:

            row = _save(
                game_id,
                state
            )

        except Exception:

            # 렌더링 자체는 계속 진행
            row["state"] = state


    else:

        row["state"] = state


    return row


# =========================================================
# 경매 액션
# =========================================================

def action(
    game_id,
    side,
    act
):

    row = _load(game_id)


    state = _normalize_state(
        deepcopy(
            row["state"]
        )
    )


    # -----------------------------------------------------
    # 이미 종료
    # -----------------------------------------------------

    if state.get("finished"):

        row["state"] = state

        return row


    # -----------------------------------------------------
    # 턴 확인
    # -----------------------------------------------------

    if side not in (
        "a",
        "b"
    ):

        raise ValueError(
            "잘못된 플레이어입니다."
        )


    if side != state.get("turn"):

        raise ValueError(
            "현재 차례가 아닙니다."
        )


    player = state.get("current")


    if not player:

        _finish(state)

        return _save(
            game_id,
            state
        )


    opponent = (
        "b"
        if side == "a"
        else "a"
    )


    position = player["position"]


    # =====================================================
    # +$1
    # =====================================================

    if act == "bid":

        new_bid = (
            state["current_bid"]
            + 1
        )


        if (
            state["money"][side]
            <
            new_bid
        ):

            raise ValueError(
                "자본이 부족합니다."
            )


        state["current_bid"] = (
            new_bid
        )


        state["bid"] = new_bid


        state["leader"] = side


        state["passed"][side] = False


        state["turn"] = opponent


    # =====================================================
    # ALL-IN
    # =====================================================

    elif act in (
        "all_in",
        "all-in"
    ):

        amount = state["money"][side]


        if (
            amount
            <=
            state["current_bid"]
        ):

            raise ValueError(
                "현재가보다 높은 금액으로 "
                "올인할 수 없습니다."
            )


        state["current_bid"] = amount

        state["bid"] = amount

        state["leader"] = side

        state["all_in"] = side


        # 상대가 같은 금액까지
        # 낼 수 없는 경우 즉시 낙찰
        if (
            state["money"][opponent]
            <= amount
        ):

            state["rosters"][side].append(
                player
            )


            state["money"][side] -= amount


            state["spent"][side] += amount


            state["log"].append(

                f"🔥 {player['name']} — "
                f"{state['players'][side]} "
                f"ALL-IN ${amount} 낙찰"

            )


            state["current"] = None


            state["current_bid"] = 0

            state["bid"] = 0


            state["leader"] = None

            state["all_in"] = None


            _next(state)


        else:

            state["turn"] = opponent


    # =====================================================
    # PASS
    # =====================================================

    elif act == "pass":

        state["passed"][side] = True


        # 아직 아무도 입찰하지 않은 경우
        if state["current_bid"] == 0:

            state["turn"] = opponent


        # 상대가 선두인 경우
        elif state["leader"] == opponent:

            amount = (
                state["current_bid"]
            )


            state["rosters"][opponent].append(
                player
            )


            state["money"][opponent] -= amount


            state["spent"][opponent] += amount


            state["log"].append(

                f"🔨 {player['name']} — "
                f"{state['players'][opponent]} "
                f"${amount} 낙찰"

            )


            state["current"] = None


            state["current_bid"] = 0

            state["bid"] = 0


            state["leader"] = None

            state["all_in"] = None


            _next(state)


        else:

            state["turn"] = opponent


        # 둘 다 PASS
        if (
            state["passed"]["a"]
            and
            state["passed"]["b"]
            and
            state["current_bid"] == 0
        ):

            state["log"].append(

                f"↩️ {player['name']} "
                f"유찰 → 선수풀 맨 뒤"

            )


            state["queue"].append(
                player
            )


            state["current"] = None


            state["turn"] = None


            _next(state)


    else:

        raise ValueError(
            "알 수 없는 액션입니다."
        )


    # =====================================================
    # 종료 확인
    # =====================================================

    _finish(state)


    if (
        not state.get("finished")
        and
        not state.get("current")
    ):

        _next(state)

        _finish(state)


    # =====================================================
    # 항상 HTML 호환 상태 유지
    # =====================================================

    state["bid"] = state.get(
        "current_bid",
        0
    )


    state["version"] = 2


    return _save(
        game_id,
        state
    )
