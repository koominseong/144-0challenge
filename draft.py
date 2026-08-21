from __future__ import annotations

import json, os, random, uuid
from copy import deepcopy
from flask import session

BASE = os.path.dirname(os.path.abspath(__file__))
POOL_FILE = os.path.join(BASE, "player_pool.json")

# Excel 원본의 180명을 그대로 추출해 player_pool.json으로 사용한다.
# 투수는 선발/불펜/마무리를 하나의 '투수' 슬롯으로 취급한다.
GROUPS = {"투수": ("선발", "불펜", "마무리"), "내야수": ("내야",), "외야수": ("외야",), "포수": ("포수",)}


def load_pool():
    with open(POOL_FILE, encoding="utf-8") as f:
        return json.load(f)


def group_of(p):
    for g, cats in GROUPS.items():
        if p["position"] in cats:
            return g
    raise ValueError(f"알 수 없는 포지션: {p['position']}")


def public_player(p):
    return {"name": p["name"], "team": p["team"], "position": p["position"], "group": group_of(p), "overall": p["overall"], "rank": p["rank"]}


def new_game(save_id, limits, money, a_name, b_name):
    limits = {k: max(0, int(limits.get(k, 0))) for k in GROUPS}
    roster_size = sum(limits.values())
    if roster_size < 1: raise ValueError("최소 1명 이상의 선수를 설정해야 합니다.")
    money = int(money)
    if money < 1: raise ValueError("초기 자본은 1달러 이상이어야 합니다.")

    pool = load_pool()
    buckets = {g: [] for g in GROUPS}
    for p in pool: buckets[group_of(p)].append(p)

    chosen = []
    for g, n in limits.items():
        need = n * 2
        if len(buckets[g]) < need:
            raise ValueError(f"{g} 선수풀이 부족합니다. 필요한 {need}명 / 보유 {len(buckets[g])}명")
        # 매 게임마다 무작위 선수풀이 생성. 선수 능력치 순서는 공개하지 않는다.
        c = buckets[g][:]
        random.shuffle(c)
        chosen.extend(c[:need])
    random.shuffle(chosen)

    state = {
        "id": str(uuid.uuid4()), "save_id": str(save_id),
        "players": {"a": a_name or "PLAYER A", "b": b_name or "PLAYER B"},
        "limits": limits, "roster_size": roster_size,
        "money": {"a": money, "b": money}, "spent": {"a": 0, "b": 0},
        "rosters": {"a": [], "b": []},
        "queue": chosen, "current": None,
        "bid": 0, "leader": None, "turn": None, "all_in": None,
        "passed": {"a": False, "b": False}, "finished": False, "result": None,
        "log": ["🎲 경매 순서를 랜덤으로 섞었습니다."]
    }
    start_next(state)
    save(state)
    return state


def save(state):
    session.setdefault("draft_games", {})[state["id"]] = state
    session.modified = True


def get(game_id):
    games = session.get("draft_games", {})
    state = games.get(game_id)
    if not state: raise KeyError("Draft 게임을 찾을 수 없습니다.")
    return state


def need(state, side, group):
    return state["limits"][group] - sum(p["group"] == group for p in state["rosters"][side])


def full(state, side): return len(state["rosters"][side]) >= state["roster_size"]


def start_next(state):
    state["current"] = None
    state["bid"] = 0; state["leader"] = None; state["all_in"] = None
    state["passed"] = {"a": False, "b": False}

    # 현재 선수가 공개되기 전까지 서버 내부 큐만 처리한다.
    while state["queue"]:
        p = state["queue"].pop(0)
        g = group_of(p)
        a_need, b_need = need(state,"a",g), need(state,"b",g)
        if a_need <= 0 and b_need <= 0:
            continue
        if a_need <= 0:
            state["rosters"]["b"].append(p)
            state["log"].append(f"📌 {p['name']} → B 자동 배정 ({g})")
            continue
        if b_need <= 0:
            state["rosters"]["a"].append(p)
            state["log"].append(f"📌 {p['name']} → A 자동 배정 ({g})")
            continue
        state["current"] = p
        state["turn"] = random.choice(["a","b"])
        return
    finish(state)


def finish(state):
    if full(state,"a") and not full(state,"b"):
        loser="b"
        for p in state["queue"]:
            if need(state,loser,group_of(p))>0: state["rosters"][loser].append(p)
        state["queue"]=[]
    elif full(state,"b") and not full(state,"a"):
        loser="a"
        for p in state["queue"]:
            if need(state,loser,group_of(p))>0: state["rosters"][loser].append(p)
        state["queue"]=[]
    if full(state,"a") and full(state,"b"):
        state["current"]=None
        state["finished"]=True
        state["result"]=final_result(state)


def final_result(state):
    # 원본의 종합능력치를 기반으로 포지션별 평균을 계산한다.
    # 점수 자체는 게임의 승자를 정하기 위한 Draft 전용 지표다.
    def score(side):
        rs=state["rosters"][side]
        av={g:(sum(p["overall"] for p in rs if p["group"]==g)/max(1,sum(p["group"]==g for p in rs))) for g in GROUPS}
        return round(av["투수"]*.35+av["내야수"]*.30+av["외야수"]*.25+av["포수"]*.10,2)
    sa,sb=score("a"),score("b")
    if sa>sb: w="a"
    elif sb>sa: w="b"
    else: w=random.choice(["a","b"])
    return {"winner":w,"strength":{"a":sa,"b":sb},"tie":sa==sb}


def act(game_id, side, action_name):
    state=get(game_id)
    if state["finished"]: return state
    if side not in ("a","b"): raise ValueError("플레이어가 올바르지 않습니다.")
    if state["turn"] != side: raise ValueError("상대 플레이어의 차례입니다.")
    p=state["current"]
    if not p: start_next(state); save(state); return state
    opp="b" if side=="a" else "a"

    if action_name=="bid":
        amount=state["bid"]+1
        if state["money"][side] < amount: raise ValueError("자본이 부족합니다.")
        state["bid"]=amount; state["leader"]=side; state["passed"][side]=False; state["turn"]=opp

    elif action_name=="allin":
        amount=state["money"][side]
        if amount<=state["bid"]: raise ValueError("현재가보다 높은 올인 금액이 없습니다.")
        state["bid"]=amount; state["leader"]=side; state["all_in"]=side
        # 상대의 최대 자본이 같은 경우도 ALL-IN 우선 낙찰.
        if state["money"][opp] <= amount:
            award(state,side,amount,"🔥 ALL-IN")
            start_next(state)
        else:
            state["turn"]=opp

    elif action_name=="pass":
        state["passed"][side]=True
        if state["bid"]==0:
            if state["passed"][opp]:
                state["queue"].append(p)
                state["log"].append(f"↩️ {p['name']} 양쪽 PASS → 선수풀 맨 뒤")
                start_next(state)
            else:
                state["turn"]=opp
        elif state["leader"]==opp:
            award(state,opp,state["bid"],"🔨 낙찰")
            start_next(state)
        else:
            state["turn"]=opp
    else: raise ValueError("알 수 없는 경매 액션입니다.")

    finish(state); save(state); return state


def award(state,side,amount,prefix):
    p=state["current"]
    state["rosters"][side].append(p); state["money"][side]-=amount; state["spent"][side]+=amount
    state["log"].append(f"{prefix} {p['name']} — {state['players'][side]} ${amount}")
    state["current"]=None


def view(state):
    # 클라이언트에는 현재 선수와 공개 가능한 정보만 전달한다.
    out=deepcopy(state)
    out["queue"] = [{"hidden":True} for _ in state["queue"]]
    if state.get("current"): out["current"]=public_player(state["current"])
    out["rosters"]={s:[public_player(p) for p in state["rosters"][s]] for s in ("a","b")}
    return out
