# dynasty_live.py - v2 Part1
# =========================================
# KBO Dynasty - 감독 모드 v2
# 중계 멘트 풀 / 클러치 듀얼 / 작전 포인트 / 비디오 판독
# 관중 게이지 / 모멘텀 / 명장면 / 업적 / 시나리오
# =========================================

import math
import random
from dynasty_utils import get_supabase
from dynasty_game import _plate_appearance, _load_all
from dynasty_stats import flush_stats

FAN_MAX = 200000

# =========================================
# 중계 멘트 풀
# =========================================
COMMENT = {
    "1B": ["{b}, 중전 안타!", "{b}의 타구가 내야를 빠져나갑니다!", "{b}, 밀어쳐서 우전 안타!", "빗맞았지만 떨어집니다! {b} 출루!"],
    "2B": ["{b}, 좌중간을 가르는 2루타!", "{b}의 타구가 펜스까지 굴러갑니다! 2루타!", "라인선상! {b}, 여유 있게 2루!"],
    "3B": ["{b}! 우중간 깊숙이! 3루까지 갑니다!", "{b}의 총알 같은 타구! 3루타!"],
    "HR": ["🎆 {b}!!! 쳤습니다! 넘어갔습니다!!!", "🎆 {b}, 받아쳤습니다! 큽니다, 큽니다... 담장 밖!!!", "🎆 {b}의 타구, 까마득하게 날아갑니다! 홈런!!!"],
    "K":  ["{b}, 헛스윙 삼진!", "{p}의 결정구! {b} 꼼짝 못하고 삼진!", "{b}, 크게 돌았지만 방망이는 허공을 갈랐습니다."],
    "OUT": ["{b}, 평범한 뜬공.", "{b}의 타구, 유격수 정면. 아웃.", "{b}, 힘없는 땅볼로 물러납니다."],
    "BB": ["{b}, 볼넷으로 걸어나갑니다.", "{p}, 제구가 흔들립니다. {b} 볼넷."],
    "COLOR_HR": ["해설: 완벽한 스윙이었어요. 실투를 놓치지 않았습니다.", "해설: 저건 잡을 수 없죠. 타구음부터 달랐습니다."],
    "COLOR_K": ["해설: 승부구 선택이 아주 좋았습니다.", "해설: 타자 입장에선 손이 나갈 수밖에 없는 공이에요."],
    "CLUTCH_IN": ["🔥 승부처입니다. 덕아웃의 공기가 달라졌습니다.", "🔥 여기가 오늘 경기의 분수령이 되겠죠."],
}


def _say(kind, **kw):
    pool = COMMENT.get(kind)
    if not pool:
        return None
    return random.choice(pool).format(**kw)


# =========================================
# 라이브 시작 (schedule_id=None이면 시나리오)
# =========================================
def start_live_game(save_id, schedule_id):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_live_game")
        .select("*")
        .eq("save_id", save_id)
        .eq("schedule_id", schedule_id)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    g = (
        sb.table("dynasty_schedule").select("*").eq("id", schedule_id).execute().data[0]
    )

    state = _base_state(g["home_team"], g["away_team"], g["week"], g["season"])

    row = (
        sb.table("dynasty_live_game")
        .insert({"save_id": save_id, "schedule_id": schedule_id,
                 "state": state, "finished": False})
        .execute()
        .data[0]
    )
    return row


def _base_state(home_id, away_id, week, season):
    return {
        "home_id": home_id, "away_id": away_id,
        "week": week, "season": season,
        "inning": 1, "half": "top",
        "h_score": 0, "a_score": 0, "outs": 0,
        "bases": [None, None, None],
        "h_order": 0, "a_order": 0,
        "h_pitcher": None, "a_pitcher": None,
        "h_pit_outs": 0, "a_pit_outs": 0,
        "h_used_cp": False, "a_used_cp": False,
        "shift": False, "shift_boost_inning": None,
        "ph_over": {}, "used_ph": [],
        "cond": {},
        "send_runner": None,
        "op": 3,                       # 작전 포인트
        "focus_next": False,           # 집중 지시 예약
        "momentum": {"home": 0, "away": 0},
        "out_streak": {"home": 0, "away": 0},
        "crowd": 50,
        "challenge_used": False,
        "challenge_ctx": None,         # 판독 대기 정보
        "duel": None,                  # 듀얼 대기 정보
        "lead_side": None,             # 역전 감지용
        "lead_changes_late": 0,
        "scenes": [],
        "banner": None,
        "scenario": None,              # 시나리오 코드
        "log": [], "acc": {},
        "pending": "mode_select",
        "view_mode": None,             # manager | batter | pitcher
        "focus_player": None,          # 빙의 대상 pid
        "pregame_done": False,
    }

# dynasty_live.py - v2 Part2

# =========================================
# 컨텍스트 로드 (v1과 동일 + fx)
# =========================================
def load_context(save_id, state):
    sb = get_supabase()
    teams, rosters, mods = _load_all(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    home = rosters.get(state["home_id"])
    away = rosters.get(state["away_id"])

    bench_rows = (
        sb.table("dynasty_roster")
        .select("team_id, dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("role", "BENCH")
        .in_("team_id", [state["home_id"], state["away_id"]])
        .execute()
        .data
    )
    bench_map = {state["home_id"]: [], state["away_id"]: []}
    for r in bench_rows:
        p = r["dynasty_player"]
        if p and not p["retired"]:
            bench_map[r["team_id"]].append(p)
    if home:
        home["bench"] = bench_map.get(state["home_id"], [])
    if away:
        away["bench"] = bench_map.get(state["away_id"], [])

    players = {}
    for team in (home, away):
        if not team:
            continue
        for p in team["batters"] + team["sps"] + team["rps"] + team.get("bench", []):
            players[p["id"]] = p
        if team["cp"]:
            players[team["cp"]["id"]] = team["cp"]

    # 수비력 (대수비 오버라이드 반영)
    for side_key, team in (("home", home), ("away", away)):
        if not team or not team["batters"]:
            if team:
                team["def_avg"] = 60
            continue
        over = (state.get("ph_over") or {}).get(side_key, {})
        vals = []
        for i, p in enumerate(team["batters"]):
            oid = over.get(str(i))
            vals.append((players.get(oid, p) if oid else p)["overall"])
        team["def_avg"] = sum(vals) / len(vals)

    try:
        from dynasty_staff import get_staff_effects
        fx = get_staff_effects(save_id)
    except Exception:
        fx = {}

    return {
        "team_map": team_map, "home": home, "away": away,
        "home_mod": mods.get(state["home_id"], {}),
        "away_mod": mods.get(state["away_id"], {}),
        "home_fx": fx.get(state["home_id"], {}),
        "away_fx": fx.get(state["away_id"], {}),
        "players": players,
    }


def user_side(state, ctx):
    for side, tid in (("home", state["home_id"]), ("away", state["away_id"])):
        t = ctx["team_map"].get(tid)
        if t and t["is_user"]:
            return side
    return None


def offense_defense(state):
    if state["half"] == "top":
        return "away", "home"
    return "home", "away"


def roll_conditions(state, ctx):
    state["cond"] = {str(pid): random.randint(-3, 3) for pid in ctx["players"]}


def _cond(state, pid):
    return state.get("cond", {}).get(str(pid), 0)


def _ensure_acc(acc, p, team_id):
    key = str(p["id"])
    if key not in acc:
        acc[key] = {
            "team_id": team_id, "name": p["name"], "games": 0, "hits": 0,
            "hr": 0, "rbi": 0, "sb": 0, "wins": 0, "losses": 0, "saves": 0, "so": 0,
        }
    return acc[key]


def _add_runs(state, off, runs):
    if runs <= 0:
        return
    if off == "home":
        state["h_score"] += runs
    else:
        state["a_score"] += runs
    # 관중/모멘텀
    state["crowd"] = min(100, state.get("crowd", 50) + runs * 4)
    mo = state.setdefault("momentum", {"home": 0, "away": 0})
    mo[off] = min(3, mo.get(off, 0) + 1)


def _momentum_mod(state, off):
    mo = state.get("momentum", {})
    return (mo.get(off, 0) - mo.get("home" if off == "away" else "away", 0)) * 0.004


def _current_batter(state, ctx, off):
    team = ctx[off]
    order_key = "h_order" if off == "home" else "a_order"
    slot = state[order_key] % len(team["batters"])
    over = state.get("ph_over", {}).get(off, {})
    over_id = over.get(str(slot))
    return (ctx["players"][over_id] if over_id else team["batters"][slot]), slot


def _is_clutch(state):
    return (state["inning"] >= 7
            and abs(state["h_score"] - state["a_score"]) <= 3
            and (state["bases"][1] or state["bases"][2]))


# =========================================
# 결정 대기 판정 (모드별)
# =========================================
def needs_decision(state, ctx):
    us = user_side(state, ctx)
    if us is None:
        return None
    off, def_ = offense_defense(state)
    focus = state.get("focus_player")

    # ----- 빙의 선수 차례: 듀얼 우선 -----
    if focus and not state.get("duel_done_pa"):
        if off == us:
            batter, _ = _current_batter(state, ctx, off)
            if batter["id"] == focus:
                return "duel_bat"
        if def_ == us:
            pk = "h_pitcher" if def_ == "home" else "a_pitcher"
            if state.get(pk) == focus:
                return "duel_pitch"

    # ----- 기본: 감독 모드 -----
    if off == us:
        if _is_clutch(state) and not state.get("duel_done_pa"):
            return "duel_bat"
        return "offense"
    if _is_clutch(state) and not state.get("duel_done_pa"):
        return "duel_pitch"
    return "pitching"

# =========================================
# 듀얼 판정 매트릭스
# 타자 노림수: guess_fast / guess_break / cut
# 투수 승부구: attack(정면승부) / bait(유인구) / avoid(피해가기)
# =========================================
def resolve_duel(state, role, choice):
    """listener: 상대 선택은 AI 랜덤(약간의 경향). return (bat_mod_delta, forced, text)"""
    if role == "bat":
        pitch = random.choices(["attack", "bait", "avoid"], weights=[45, 40, 15])[0]
        if choice == "cut":
            if pitch == "avoid":
                return 0.0, "BB", "커트 자세… {p}가 승부를 피했습니다. 볼넷!"
            return -0.02, None, "끈질기게 커트! 유리한 카운트를 만듭니다."
        if choice == "guess_fast":
            if pitch == "attack":
                return 0.12, None, "노림수 적중! 직구를 노려쳤습니다!"
            if pitch == "bait":
                return -0.08, None, "유인구에 방망이가 나갔습니다…"
            return 0.0, "BB", "{p}, 정면승부를 피합니다. 볼넷."
        if choice == "guess_break":
            if pitch == "bait":
                return 0.12, None, "변화구 노림수 적중! 완벽히 받아쳤습니다!"
            if pitch == "attack":
                return -0.08, None, "몸쪽 직구에 얼어붙었습니다…"
            return 0.0, "BB", "{p}, 승부를 피해갑니다. 볼넷."
    else:  # role == "pitch"
        guess = random.choices(["guess_fast", "guess_break", "cut"], weights=[40, 40, 20])[0]
        if choice == "avoid":
            return 0.0, "BB", "정면승부를 피합니다. 고의성 볼넷."
        if choice == "attack":
            if guess == "guess_fast":
                return 0.10, None, "타자가 직구를 기다리고 있었습니다!"
            return -0.10, None, "과감한 정면승부! 타자의 타이밍을 뺏었습니다!"
        if choice == "bait":
            if guess == "cut":
                return 0.04, None, "커트당하며 카운트가 몰립니다…"
            if guess == "guess_break":
                return 0.08, None, "유인구를 노리고 있었습니다!"
            return -0.12, None, "절묘한 유인구! 타자의 방망이가 헛돕니다!"
    return 0.0, None, ""

# dynasty_live.py - v2 Part3

# =========================================
# 한 타석 진행 v2
# action: None | "bunt" | "steal" | "hitrun" | "ibb"
# duel_mod: 클러치 듀얼/시점 모드 보정 (float)
# duel_forced: "BB" 등 강제 결과
# =========================================
def play_at_bat(state, ctx, action=None, duel_mod=0.0, duel_forced=None):
    off, def_ = offense_defense(state)
    off_team = ctx[off]
    def_team = ctx[def_]

    order_key = "h_order" if off == "home" else "a_order"
    batter, slot = _current_batter(state, ctx, off)

    pitcher_key = "h_pitcher" if def_ == "home" else "a_pitcher"
    pitcher = ctx["players"][state[pitcher_key]]

    def_fx = ctx["home_fx"] if def_ == "home" else ctx["away_fx"]
    off_fx = ctx["home_fx"] if off == "home" else ctx["away_fx"]

    pit_outs_key = "h_pit_outs" if def_ == "home" else "a_pit_outs"
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21) + def_fx.get("sp_outs", 0)
    fatigue = min(0.25, max(0.0, (state[pit_outs_key] - max_outs * 0.7) / 60))
    fatigue *= (1 - def_fx.get("sp_fatigue_cut", 0.0))

    off_id = state["home_id"] if off == "home" else state["away_id"]
    def_id = state["home_id"] if def_ == "home" else state["away_id"]

    us = user_side(state, ctx)

    mod = ctx["home_mod"] if off == "home" else ctx["away_mod"]
    crowd_adv = 0.005 if (state.get("crowd", 50) >= 90 and off == "home") else 0.0
    bat_mod = mod.get("sim", 0.0) + ((0.02 + ctx["home_mod"].get("home_adv", 0.0) + crowd_adv) if off == "home" else 0.0)
    bat_mod += (_cond(state, batter["id"]) - _cond(state, pitcher["id"])) * 0.004
    bat_mod += off_fx.get("bat_mod", 0.0) - def_fx.get("so_bonus", 0.0)
    bat_mod += _momentum_mod(state, off)
    bat_mod += duel_mod

    # 집중 지시 (작전 포인트)
    if state.get("focus_next") and off == us:
        bat_mod += 0.05
        state["focus_next"] = False
        state["log"].append("📣 벤치의 집중 지시가 타석에 전달됩니다.")

    acc = state["acc"]
    bs = _ensure_acc(acc, batter, off_id)
    ps = _ensure_acc(acc, pitcher, def_id)

    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"

    # 클러치 진입 멘트 (타석마다 1회)
    if _is_clutch(state) and not state.get("_clutch_said"):
        state["log"].append(_say("CLUTCH_IN"))
        state["_clutch_said"] = True
    elif not _is_clutch(state):
        state["_clutch_said"] = False

    def _out_streak(reset=False):
        osk = state.setdefault("out_streak", {"home": 0, "away": 0})
        if reset:
            osk[off] = 0
        else:
            osk[off] += 1
            if osk[off] >= 4:
                mo = state.setdefault("momentum", {"home": 0, "away": 0})
                mo[off] = max(-3, mo[off] - 1)
                osk[off] = 0

    # ---------- 고의4구 ----------
    if action == "ibb" or duel_forced == "BB_IBB":
        runs = 0
        if state["bases"][0]:
            if state["bases"][1]:
                if state["bases"][2]:
                    runs += 1
                    bs["rbi"] += 1
                state["bases"][2] = state["bases"][1]
            state["bases"][1] = state["bases"][0]
        state["bases"][0] = batter["id"]
        state[order_key] += 1
        _add_runs(state, off, runs)
        txt = f"{log_prefix} 🚶 {batter['name']} 고의4구"
        if runs:
            txt += " (밀어내기 +1)"
        return txt

    # ---------- 도루 ----------
    if action == "steal" and state["bases"][0] and not state["bases"][1]:
        runner = ctx["players"][state["bases"][0]]
        rs = _ensure_acc(acc, runner, off_id)
        spd = (runner["speed"] or 40) + _cond(state, runner["id"])
        steal_p = 0.45 + (spd - 50) * 0.008 + off_fx.get("steal_bonus", 0.0) - def_fx.get("opp_steal_cut", 0.0)
        if random.random() < min(0.9, max(0.1, steal_p)):
            state["bases"][1] = state["bases"][0]
            state["bases"][0] = None
            rs["sb"] += 1
            return f"{log_prefix} 💨 {runner['name']} 도루 성공! 포수의 송구가 늦었습니다!"
        else:
            state["bases"][0] = None
            state["outs"] += 1
            # 비디오 판독 트리거 (유저 공격 + 미사용 + 30%)
            if off == us and not state.get("challenge_used") and random.random() < 0.3:
                state["challenge_ctx"] = {"type": "steal", "runner": runner["id"]}
                state["pending"] = "challenge"
            return f"{log_prefix} ❌ {runner['name']} 도루 실패… 태그가 먼저였을까요?"

    # ---------- 번트 ----------
    if action == "bunt" and any(state["bases"]) and state["outs"] < 2:
        state[order_key] += 1
        succ = 0.72 + ((batter["contact"] or 50) - 50) * 0.002 + off_fx.get("bunt_bonus", 0.0)
        if random.random() < succ:
            runs = 0
            if state["bases"][2]:
                runs += 1
                bs["rbi"] += 1
                state["bases"][2] = None
            if state["bases"][1]:
                state["bases"][2] = state["bases"][1]
                state["bases"][1] = None
            if state["bases"][0]:
                state["bases"][1] = state["bases"][0]
                state["bases"][0] = None
            state["outs"] += 1
            _add_runs(state, off, runs)
            txt = f"{log_prefix} 🥢 {batter['name']}, 완벽한 희생번트."
            if runs:
                txt += f" (+{runs}점)"
            return txt
        else:
            state["outs"] += 1
            _out_streak()
            return f"{log_prefix} ❌ {batter['name']} 번트 실패! 투수 정면으로 굴렀습니다."

    # ---------- 히트앤런 ----------
    hitrun = (action == "hitrun" and state["bases"][0] and state["outs"] < 2)

    # ---------- 일반 타석 ----------
    state[order_key] += 1
    state["duel_done_pa"] = False  # 다음 타석 듀얼 허용 리셋

    if duel_forced == "BB":
        result = "BB"
    else:
        # 불펜코치: 구원 투수 보정
        sp_today = def_team["sps"][state["week"] % len(def_team["sps"])] if def_team["sps"] else None
        if sp_today and pitcher["id"] != sp_today["id"]:
            bat_mod -= def_fx.get("rp_boost", 0) * 0.004
        result = _plate_appearance(batter, pitcher, fatigue, bat_mod + (0.015 if hitrun else 0.0))

    # 시프트 (부스트 이닝이면 강화)
    if state.get("shift") and def_ == us:
        boost = 0.08 if state.get("shift_boost_inning") == f"{state['inning']}-{state['half']}" else 0.0
        if result == "1B" and random.random() < 0.22 + def_fx.get("shift_plus", 0.0) + boost:
            result = "OUT"
            state["log"].append(f"{log_prefix} 🛡 시프트가 정확히 그 자리에 있었습니다!")
        elif result == "OUT" and random.random() < max(0.02, 0.08 - def_fx.get("shift_backfire_cut", 0.0) - boost * 0.5):
            result = "1B"
            state["log"].append(f"{log_prefix} ⚠ 시프트의 빈 곳으로… 안타가 됩니다.")

    # 호수비
    if result in ("1B", "2B"):
        def_avg = def_team.get("def_avg", 60) + def_fx.get("def_bonus", 0)
        if def_avg > 62 and random.random() < (def_avg - 62) * 0.004:
            result = "OUT"
            state["log"].append(f"{log_prefix} ✨ 믿을 수 없는 호수비! 안타를 도둑맞았습니다!")

    if result == "K":
        state["outs"] += 1
        ps["so"] += 1
        _out_streak()
        txt = f"{log_prefix} " + _say("K", b=batter["name"], p=pitcher["name"])
        if random.random() < 0.3:
            state["log"].append(_say("COLOR_K"))
        if hitrun and state["bases"][0] and random.random() < 0.4:
            runner = ctx["players"][state["bases"][0]]
            state["bases"][0] = None
            state["outs"] += 1
            txt += f" 포수 2루 송구… {runner['name']} 협살 아웃! 최악의 결과!"
        return txt

    if result == "OUT":
        state["outs"] += 1
        if hitrun and state["bases"][0] and state["outs"] < 3 and random.random() < 0.5:
            if not state["bases"][1]:
                state["bases"][1] = state["bases"][0]
                state["bases"][0] = None
                _out_streak()
                return f"{log_prefix} {batter['name']} 땅볼, 그 사이 주자는 2루로. 작전은 절반의 성공."
        if state["outs"] < 3 and state["bases"][2] and random.random() < 0.2:
            runner = ctx["players"][state["bases"][2]]
            state["bases"][2] = None
            bs["rbi"] += 1
            _add_runs(state, off, 1)
            return f"{log_prefix} {batter['name']}의 희생타! {runner['name']} 홈인!"
        _out_streak()
        return f"{log_prefix} " + _say("OUT", b=batter["name"], p=pitcher["name"])

    if result == "BB":
        runs = 0
        if state["bases"][0]:
            if state["bases"][1]:
                if state["bases"][2]:
                    runs += 1
                    bs["rbi"] += 1
                state["bases"][2] = state["bases"][1]
            state["bases"][1] = state["bases"][0]
        state["bases"][0] = batter["id"]
        _add_runs(state, off, runs)
        txt = f"{log_prefix} " + _say("BB", b=batter["name"], p=pitcher["name"])
        if runs:
            txt += " 밀어내기 실점!"
        return txt

    # 안타류
    advance = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}[result]
    bs["hits"] += 1
    _out_streak(reset=True)
    if result == "HR":
        bs["hr"] += 1

    runner_on_first = state["bases"][0]
    runs = 0
    for base_idx in (2, 1, 0):
        rid = state["bases"][base_idx]
        if rid is None:
            continue
        new_idx = base_idx + advance
        if result == "1B" and base_idx == 0 and hitrun:
            new_idx = 2
        state["bases"][base_idx] = None
        if new_idx >= 3:
            runs += 1
            bs["rbi"] += 1
        else:
            state["bases"][new_idx] = rid

    if advance >= 4:
        runs += 1
        bs["rbi"] += 1
    else:
        state["bases"][advance - 1] = batter["id"]

    _add_runs(state, off, runs)

    # 역전 감지 (명장면/업적용)
    lead = "home" if state["h_score"] > state["a_score"] else ("away" if state["a_score"] > state["h_score"] else None)
    if lead and lead != state.get("lead_side"):
        if state["inning"] >= 7 and state.get("lead_side"):
            state["lead_changes_late"] = state.get("lead_changes_late", 0) + 1
            state.setdefault("scenes", []).append(
                f"{log_prefix} {batter['name']}의 {'홈런' if result == 'HR' else '적시타'}로 역전!"
            )
        state["lead_side"] = lead

    txt = f"{log_prefix} " + _say(result, b=batter["name"], p=pitcher["name"])
    if result == "HR" and random.random() < 0.5:
        state["log"].append(_say("COLOR_HR"))
    if hitrun and result == "1B":
        txt += " 히트앤런! 1루 주자는 3루까지!"
    if runs:
        txt += f" (+{runs}점)"
    if result == "HR":
        state.setdefault("scenes", []).append(f"{log_prefix} {batter['name']} 홈런 (+{runs}점)")

    # 주루 판단 (감독 모드만)
    if ((state.get("view_mode") or "manager") == "manager"
            and result == "1B" and not hitrun and off == us
            and runner_on_first and state["bases"][1] == runner_on_first
            and not state["bases"][2] and state["outs"] < 3):
        runner = ctx["players"][runner_on_first]
        state["send_runner"] = runner_on_first
        state["pending"] = "running"
        txt += f" — 3루 코치가 팔을 돌릴까요? {runner['name']}!"

    return txt


# =========================================
# 주루 판단 + 판독 트리거
# =========================================
def try_send_runner(state, ctx):
    off, def_ = offense_defense(state)
    us = user_side(state, ctx)
    rid = state.get("send_runner")
    state["send_runner"] = None
    if not rid or state["bases"][1] != rid:
        return None

    runner = ctx["players"][rid]
    off_fx = ctx["home_fx"] if off == "home" else ctx["away_fx"]
    def_avg = ctx[def_].get("def_avg", 60)
    spd = (runner["speed"] or 40) + _cond(state, rid)
    succ = 0.55 + (spd - 50) * 0.01 - (def_avg - 60) * 0.005 + off_fx.get("send_bonus", 0.0)

    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"
    if random.random() < max(0.15, min(0.92, succ)):
        state["bases"][1] = None
        state["bases"][2] = rid
        return f"{log_prefix} 🏃 {runner['name']}, 헤드퍼스트 슬라이딩! 세이프!!!"
    else:
        state["bases"][1] = None
        state["outs"] += 1
        if off == us and not state.get("challenge_used") and random.random() < 0.3:
            state["challenge_ctx"] = {"type": "send", "runner": rid}
            state["pending"] = "challenge"
        return f"{log_prefix} ❌ {runner['name']}, 3루에서 태그 아웃… 아슬아슬했습니다."


# =========================================
# 비디오 판독 실행
# =========================================
def resolve_challenge(state, ctx, use):
    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"
    cc = state.get("challenge_ctx")
    state["challenge_ctx"] = None
    state["pending"] = None
    if not use or not cc:
        return None

    state["challenge_used"] = True
    if random.random() < 0.45:
        # 번복: 아웃 취소, 주자 복귀
        state["outs"] = max(0, state["outs"] - 1)
        rid = cc["runner"]
        if cc["type"] == "steal" and not state["bases"][1]:
            state["bases"][1] = rid
        elif cc["type"] == "send" and not state["bases"][2]:
            state["bases"][2] = rid
        runner = ctx["players"][rid]
        return f"{log_prefix} 📺 비디오 판독 결과… 세이프!!! {runner['name']} 살아 돌아옵니다!"
    else:
        return f"{log_prefix} 📺 비디오 판독 결과… 원심 유지, 아웃입니다."


# =========================================
# 작전 포인트 사용
# op_focus: 다음 내 타석 +5% / op_cut: 상대 모멘텀 리셋 / op_shift: 이번 이닝 시프트 강화
# =========================================
def use_op(state, ctx, kind):
    if state.get("op", 0) <= 0:
        return "작전 포인트가 없습니다."
    us = user_side(state, ctx)
    opp = "away" if us == "home" else "home"
    state["op"] -= 1
    if kind == "op_focus":
        state["focus_next"] = True
        return "📣 벤치가 사인을 냅니다. (다음 내 타석 집중 +5%)"
    if kind == "op_cut":
        state.setdefault("momentum", {"home": 0, "away": 0})[opp] = 0
        return "🧊 타임! 상대의 흐름을 끊었습니다. (상대 기세 리셋)"
    if kind == "op_shift":
        state["shift"] = True
        state["shift_boost_inning"] = f"{state['inning']}-{state['half']}"
        return "🛡 필승 시프트 가동! (이번 이닝 시프트 대폭 강화)"
    state["op"] += 1
    return None


# =========================================
# 이닝/경기 전환 (v1 동일 + 클러치 플래그 리셋)
# =========================================
def advance_if_needed(state, ctx):
    pit_outs_key = "h_pit_outs" if state["half"] == "top" else "a_pit_outs"

    if state["outs"] >= 3:
        state[pit_outs_key] += 3
        state["outs"] = 0
        state["bases"] = [None, None, None]
        state["send_runner"] = None
        state["_clutch_said"] = False

        if state["half"] == "top":
            if state["inning"] >= 9 and state["h_score"] > state["a_score"]:
                return "game_over"
            state["half"] = "bot"
        else:
            if state["inning"] >= 9 and state["h_score"] != state["a_score"]:
                return "game_over"
            if state["inning"] >= 12:
                return "game_over"
            state["inning"] += 1
            state["half"] = "top"

    return "continue"


# =========================================
# AI 투수 운용 / AI 대타 (v1 동일)
# =========================================
def auto_manage_pitcher(state, ctx, side):
    team = ctx[side]
    pitcher_key = "h_pitcher" if side == "home" else "a_pitcher"
    pit_outs_key = "h_pit_outs" if side == "home" else "a_pit_outs"
    used_cp_key = "h_used_cp" if side == "home" else "a_used_cp"

    if state[pitcher_key] is None:
        sp = team["sps"][state["week"] % len(team["sps"])] if team["sps"] else team["batters"][0]
        state[pitcher_key] = sp["id"]
        return

    pitcher = ctx["players"][state[pitcher_key]]
    my_score = state["h_score"] if side == "home" else state["a_score"]
    opp_score = state["a_score"] if side == "home" else state["h_score"]
    lead = my_score - opp_score

    if state["inning"] >= 9 and 0 < lead <= 3 and team["cp"] and not state[used_cp_key]:
        state[pitcher_key] = team["cp"]["id"]
        state[pit_outs_key] = 0
        state[used_cp_key] = True
        return

    fx = ctx["home_fx"] if side == "home" else ctx["away_fx"]
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21) + fx.get("rp_outs", 0) + fx.get("sp_outs", 0)
    if state[pit_outs_key] >= max_outs and team["rps"]:
        idx = min(len(team["rps"]) - 1, (state[pit_outs_key] - max_outs) // 6)
        state[pitcher_key] = team["rps"][idx]["id"]


def ai_pinch_hit(state, ctx, off):
    if state["inning"] < 7:
        return
    if abs(state["h_score"] - state["a_score"]) > 2:
        return
    team = ctx[off]
    bench = [p for p in team.get("bench", []) if p["id"] not in state.get("used_ph", [])]
    if not bench:
        return
    batter, slot = _current_batter(state, ctx, off)
    best = max(bench, key=lambda p: p["overall"])
    if best["overall"] >= (batter["overall"] or 0) + 5:
        state.setdefault("ph_over", {}).setdefault(off, {})[str(slot)] = best["id"]
        state.setdefault("used_ph", []).append(best["id"])
        tname = ctx["team_map"][state["home_id"] if off == "home" else state["away_id"]]["team_name"]
        state["log"].append(f"🔁 [{tname}] 승부수! 대타 {best['name']} 투입")


# =========================================
# 승률 게이지 (v1 동일)
# =========================================
def win_prob(state, ctx):
    us = user_side(state, ctx)
    if us is None:
        return 50
    my = state["h_score"] if us == "home" else state["a_score"]
    opp = state["a_score"] if us == "home" else state["h_score"]
    diff = my - opp
    outs_total = (state["inning"] - 1) * 6 + (3 if state["half"] == "bot" else 0) + state["outs"]
    prog = min(1.0, outs_total / 54)
    x = diff * (0.45 + prog * 0.9)
    off, _ = offense_defense(state)
    if off == us:
        x += sum(1 for b in state["bases"] if b) * 0.12
    if us == "home":
        x += 0.08
    p = 1 / (1 + math.exp(-x))
    return max(3, min(97, round(p * 100)))

# dynasty_live.py - v2 Part4

# =========================================
# 경기 종료 v2: 승패/세이브 + MVP + 명장면 + 업적 + 관중 수익
# (시나리오 경기는 기록 미반영)
# =========================================
def finish_live_game(save_id, live_row, state, ctx):
    sb = get_supabase()

    hs, as_ = state["h_score"], state["a_score"]
    home_id, away_id = state["home_id"], state["away_id"]
    acc = state["acc"]
    us = user_side(state, ctx)
    scenario = state.get("scenario")

    # ----- 승/패/세이브 -----
    if hs != as_:
        if hs > as_:
            w_side, w_id, l_side, l_id = "home", home_id, "away", away_id
        else:
            w_side, w_id, l_side, l_id = "away", away_id, "home", home_id

        w_team, l_team = ctx[w_side], ctx[l_side]

        w_sp = w_team["sps"][state["week"] % len(w_team["sps"])] if w_team["sps"] else None
        w_cur = ctx["players"].get(state["h_pitcher" if w_side == "home" else "a_pitcher"])
        w_pitcher = w_sp if (w_sp and random.random() < 0.65) else (w_cur or w_sp)
        if w_pitcher:
            _ensure_acc(acc, w_pitcher, w_id)["wins"] += 1

        l_sp = l_team["sps"][state["week"] % len(l_team["sps"])] if l_team["sps"] else None
        l_cur = ctx["players"].get(state["h_pitcher" if l_side == "home" else "a_pitcher"])
        l_pitcher = l_sp if (l_sp and random.random() < 0.7) else (l_cur or l_sp)
        if l_pitcher:
            _ensure_acc(acc, l_pitcher, l_id)["losses"] += 1

        used_cp = state["h_used_cp"] if w_side == "home" else state["a_used_cp"]
        if used_cp and abs(hs - as_) <= 3 and w_team["cp"]:
            _ensure_acc(acc, w_team["cp"], w_id)["saves"] += 1

    # ----- 출장 기록 -----
    for side, tid in (("home", home_id), ("away", away_id)):
        team = ctx[side]
        for p in team["batters"]:
            _ensure_acc(acc, p, tid)["games"] += 1
        if team["sps"]:
            sp = team["sps"][state["week"] % len(team["sps"])]
            _ensure_acc(acc, sp, tid)["games"] += 1

    # ----- MVP -----
    best_key, best_score = None, -1
    for k, v in acc.items():
        score = v["hits"] + v["hr"] * 2.5 + v["rbi"] * 1.5 + v["sb"] + v["so"] * 0.4 + v["wins"] * 3 + v["saves"] * 2
        if score > best_score:
            best_key, best_score = k, score
    if best_key:
        v = acc[best_key]
        state["mvp"] = {
            "name": v.get("name", "?"),
            "line": f"{v['hits']}안타 {v['hr']}홈런 {v['rbi']}타점" if v["hits"] or v["hr"] else f"{v['so']}K",
        }

    # ----- 업적 판정 -----
    feats = []
    my_id = home_id if us == "home" else away_id
    my_score = hs if us == "home" else as_
    opp_score = as_ if us == "home" else hs
    won = my_score > opp_score

    if won:
        if state["half"] == "bot" and us == "home" and state["inning"] >= 9:
            feats.append("🏆 끝내기 승리!")
        if opp_score == 0:
            feats.append("🏆 완봉승!")
        if state.get("lead_changes_late", 0) >= 2:
            feats.append("🏆 대역전극!")
    for k, v in acc.items():
        if v.get("team_id") != my_id:
            continue
        if v["so"] >= 12:
            feats.append(f"🏆 {v.get('name','?')} 탈삼진 {v['so']}개!")
        if v["hr"] >= 3:
            feats.append(f"🏆 {v.get('name','?')} 한 경기 3홈런!")
    team_sb = sum(v["sb"] for v in acc.values() if v.get("team_id") == my_id)
    if team_sb >= 5:
        feats.append(f"🏆 팀 도루 {team_sb}개!")
    state["feats"] = feats

    # ----- 시나리오면 여기서 종료 (기록 미반영) -----
    if scenario:
        state["pending"] = "finished"
        sb.table("dynasty_live_game").update(
            {"state": state, "finished": True}
        ).eq("id", live_row["id"]).execute()
        return

    # ----- 스케줄/팀 반영 -----
    sb.table("dynasty_schedule").update(
        {"home_score": hs, "away_score": as_, "played": True}
    ).eq("id", live_row["schedule_id"]).execute()

    for tid, my, opp in ((home_id, hs, as_), (away_id, as_, hs)):
        t = ctx["team_map"][tid]
        if my > opp:
            t["wins"] += 1
        elif opp > my:
            t["losses"] += 1
        else:
            t["ties"] += 1

        upd = {"wins": t["wins"], "losses": t["losses"], "ties": t["ties"]}

        if us and tid == my_id:
            fans = t.get("fans") or 10000
            rate = 1.003 if my > opp else 1.001
            if state.get("crowd", 50) >= 90:
                rate += 0.002  # 만원 관중 보너스
            upd["fans"] = min(FAN_MAX, int(fans * rate))
            # 만원 관중 수익
            if state.get("crowd", 50) >= 90:
                upd["budget"] = (t.get("budget") or 0) + 5

        sb.table("dynasty_team").update(upd).eq("id", tid).execute()

    # ----- 명장면/업적 뉴스 기록 -----
    events = []
    for sc in state.get("scenes", [])[:2]:
        events.append({"save_id": save_id, "season": state["season"], "week": state["week"],
                       "icon": "🎬", "message": f"[명장면] {sc}"})
    for f in feats[:2]:
        events.append({"save_id": save_id, "season": state["season"], "week": state["week"],
                       "icon": "🏆", "message": f"[감독 모드] {f.replace('🏆 ', '')}"})
    if events:
        try:
            sb.table("dynasty_event").insert(events).execute()
        except Exception as ex:
            print(f"[dynasty_live] 뉴스 기록 skip: {ex}")

    # ----- 개인 기록 -----
    int_acc = {}
    for k, v in acc.items():
        try:
            row = dict(v)
            row.pop("name", None)
            int_acc[int(k)] = row
        except (TypeError, ValueError):
            continue
    flush_stats(save_id, state["season"], int_acc)

    state["pending"] = "finished"
    sb.table("dynasty_live_game").update(
        {"state": state, "finished": True}
    ).eq("id", live_row["id"]).execute()


# =========================================
# 연승/맥락 배너 (경기 시작 시 1회)
# =========================================
def build_banner(sb, save_id, state, ctx):
    us = user_side(state, ctx)
    if not us:
        return None
    my_id = state["home_id"] if us == "home" else state["away_id"]
    try:
        recent = (
            sb.table("dynasty_schedule")
            .select("home_team, away_team, home_score, away_score")
            .eq("save_id", save_id)
            .eq("season", state["season"])
            .eq("played", True)
            .or_(f"home_team.eq.{my_id},away_team.eq.{my_id}")
            .order("week", desc=True)
            .limit(5)
            .execute()
            .data
        )
    except Exception:
        return None
    streak = 0
    for g in recent:
        my = g["home_score"] if g["home_team"] == my_id else g["away_score"]
        opp = g["away_score"] if g["home_team"] == my_id else g["home_score"]
        if my > opp:
            if streak >= 0:
                streak += 1
            else:
                break
        elif my < opp:
            if streak <= 0:
                streak -= 1
            else:
                break
        else:
            break
    if streak >= 3:
        return f"🔥 {streak}연승 도전!"
    if streak <= -3:
        return f"🧯 {-streak}연패 탈출전!"
    return None


# =========================================
# 진행 컨트롤러 v2
# user_action 추가분:
#   모드: mode_manager | mode_batter | mode_pitcher (+ph_id=빙의 대상, batter만)
#   듀얼: guess_fast | guess_break | cut | duel_attack | duel_bait | duel_avoid
#   판독: challenge_yes | challenge_no
#   작전: op_focus | op_cut | op_shift
# =========================================
def progress(save_id, live_id, user_action=None, ph_id=None, rp_id=None, user_action_slot=None):
    sb = get_supabase()

    live_row = sb.table("dynasty_live_game").select("*").eq("id", live_id).execute().data[0]
    if live_row["finished"]:
        return live_row

    state = live_row["state"]
    ctx = load_context(save_id, state)
    us = user_side(state, ctx)
    mode = state.get("view_mode") or "manager"

    def _save_and_reload():
        state["log"] = state["log"][-60:]
        sb.table("dynasty_live_game").update({"state": state}).eq("id", live_id).execute()
        return _reload(sb, live_id)

    def _finish():
        finish_live_game(save_id, live_row, state, ctx)
        return _reload(sb, live_id)

# ----- 시점 선택 -----
    if state["pending"] == "mode_select":
        if user_action == "mode_manager":
            state["view_mode"] = "manager"
        elif user_action == "mode_batter" and us and ph_id:
            state["view_mode"] = "batter"
            state["focus_player"] = ph_id
        elif user_action == "mode_pitcher" and us:
            team = ctx[us]
            sp = team["sps"][state["week"] % len(team["sps"])] if team["sps"] else None
            if sp:
                state["view_mode"] = "pitcher"
                state["focus_player"] = sp["id"]
            else:
                state["view_mode"] = "manager"
        else:
            return _save_and_reload()
        state["pending"] = "pregame"

    # ----- 경기 중 시점 전환 (언제든, 타석 소비 안 함) -----
    if user_action == "view_manager" and us:
        state["view_mode"] = "manager"
        state["focus_player"] = None
        state["log"].append("🧢 빙의 해제 — 감독 시점")
        if state["pending"] not in ("running", "challenge", "finished"):
            state["pending"] = None

    if user_action == "view_focus" and us and ph_id:
        p = ctx["players"].get(ph_id)
        if p:
            is_pitcher = "P" in (p.get("positions") or "")
            state["view_mode"] = "pitcher" if is_pitcher else "batter"
            state["focus_player"] = ph_id
            state["log"].append(f"👁 {p['name']} 시점으로 전환")
            if state["pending"] not in ("running", "challenge", "finished"):
                state["pending"] = None

    # ----- 경기 전 -----
    if state["pending"] == "pregame":
        auto_manage_pitcher(state, ctx, "home")
        auto_manage_pitcher(state, ctx, "away")
        if not state.get("cond"):
            roll_conditions(state, ctx)
        if state.get("banner") is None:
            state["banner"] = build_banner(sb, save_id, state, ctx) or ""
        if state["banner"]:
            state["log"].append(state["banner"])
        state["log"].append("▶ 플레이볼!")
        state["pending"] = None

    # ----- 비디오 판독 -----
    if state["pending"] == "challenge":
        if user_action in ("challenge_yes", "challenge_no"):
            txt = resolve_challenge(state, ctx, user_action == "challenge_yes")
            if txt:
                state["log"].append(txt)
            if advance_if_needed(state, ctx) == "game_over":
                return _finish()
        else:
            return _save_and_reload()

    # ----- 주루 판단 -----
    if state["pending"] == "running":
        if user_action == "send":
            txt = try_send_runner(state, ctx)
            if txt:
                state["log"].append(txt)
            if state["pending"] != "challenge":
                state["pending"] = None
                if advance_if_needed(state, ctx) == "game_over":
                    return _finish()
        elif user_action == "hold":
            state["send_runner"] = None
            state["pending"] = None
        else:
            return _save_and_reload()

    # ----- 작전 포인트 (타석 소비 안 함) -----
    if user_action in ("op_focus", "op_cut", "op_shift") and us:
        txt = use_op(state, ctx, user_action)
        if txt:
            state["log"].append(txt)

    # ----- 시프트 토글 -----
    if user_action in ("shift_on", "shift_off") and us:
        state["shift"] = (user_action == "shift_on")
        state["log"].append("🛡 수비 시프트 " + ("가동" if state["shift"] else "해제"))

    # ----- 클러치/시점 듀얼: 타자 -----
    if user_action in ("guess_fast", "guess_break", "cut") and state["pending"] == "duel_bat":
        _, def_ = offense_defense(state)
        pitcher = ctx["players"][state["h_pitcher" if def_ == "home" else "a_pitcher"]]
        dmod, forced, dtxt = resolve_duel(state, "bat", user_action)
        if dtxt:
            state["log"].append("🎯 " + dtxt.format(p=pitcher["name"]))
        state["duel_done_pa"] = True
        txt = play_at_bat(state, ctx, None, duel_mod=dmod, duel_forced=forced)
        state["log"].append(txt)
        if state["pending"] not in ("running", "challenge"):
            state["pending"] = None
            if advance_if_needed(state, ctx) == "game_over":
                return _finish()

    # ----- 클러치/시점 듀얼: 투수 -----
    if user_action in ("duel_attack", "duel_bait", "duel_avoid") and state["pending"] == "duel_pitch":
        choice = {"duel_attack": "attack", "duel_bait": "bait", "duel_avoid": "avoid"}[user_action]
        dmod, forced, dtxt = resolve_duel(state, "pitch", choice)
        if dtxt:
            state["log"].append("🎯 " + dtxt)
        state["duel_done_pa"] = True
        off, _ = offense_defense(state)
        if mode == "manager":
            ai_pinch_hit(state, ctx, off)
        txt = play_at_bat(state, ctx, None, duel_mod=dmod, duel_forced=forced)
        state["log"].append(txt)
        if state["pending"] not in ("running", "challenge"):
            state["pending"] = None
            if advance_if_needed(state, ctx) == "game_over":
                return _finish()

    # ----- 대타 -----
    if user_action == "ph" and us and ph_id and state["pending"] == "offense":
        team = ctx[us]
        order_key = "h_order" if us == "home" else "a_order"
        slot = state[order_key] % len(team["batters"])
        used = state.setdefault("used_ph", [])
        sub = next((p for p in team.get("bench", []) if p["id"] == ph_id and p["id"] not in used), None)
        if sub:
            state.setdefault("ph_over", {}).setdefault(us, {})[str(slot)] = sub["id"]
            used.append(sub["id"])
            state["log"].append(f"🔁 대타 {sub['name']} 투입")
            txt = play_at_bat(state, ctx, None)
            state["log"].append(txt)
            if state["pending"] not in ("running", "challenge"):
                state["pending"] = None
                if advance_if_needed(state, ctx) == "game_over":
                    return _finish()

    # ----- 대주자 / 대수비 (v1 동일, pending 유지) -----
    if user_action == "pr" and us and ph_id and state["pending"] in ("offense", "duel_bat"):
        team = ctx[us]
        rid = state["bases"][0]
        used = state.setdefault("used_ph", [])
        sub = next((p for p in team.get("bench", []) if p["id"] == ph_id and p["id"] not in used), None)
        if rid and sub:
            over = state.setdefault("ph_over", {}).setdefault(us, {})
            for i, p in enumerate(team["batters"]):
                cur_id = over.get(str(i)) or p["id"]
                if cur_id == rid:
                    over[str(i)] = sub["id"]
                    break
            used.append(sub["id"])
            state["bases"][0] = sub["id"]
            state["log"].append(f"🏃 대주자 {sub['name']} 투입 (1루)")

    if user_action == "ds" and us and ph_id and state["pending"] in ("pitching", "duel_pitch"):
        team = ctx[us]
        used = state.setdefault("used_ph", [])
        sub = next((p for p in team.get("bench", []) if p["id"] == ph_id and p["id"] not in used), None)
        if sub and user_action_slot is not None and 0 <= user_action_slot < len(team["batters"]):
            state.setdefault("ph_over", {}).setdefault(us, {})[str(user_action_slot)] = sub["id"]
            used.append(sub["id"])
            state["log"].append(f"🧤 대수비 {sub['name']} 투입 ({user_action_slot + 1}번 자리)")

    # ----- 공격 작전 -----
    if user_action in ("swing", "bunt", "steal", "hitrun") and us and state["pending"] in ("offense", "duel_bat"):
        action = None if user_action == "swing" else user_action
        state["duel_done_pa"] = True
        txt = play_at_bat(state, ctx, action)
        state["log"].append(txt)
        if state["pending"] not in ("running", "challenge"):
            state["pending"] = None
            if advance_if_needed(state, ctx) == "game_over":
                return _finish()

    # ----- 수비 투수 결정 -----
    if user_action in ("pitch_keep", "pitch_rp", "pitch_cp", "ibb") and us and state["pending"] in ("pitching", "duel_pitch"):
        team = ctx[us]
        pitcher_key = "h_pitcher" if us == "home" else "a_pitcher"
        pit_outs_key = "h_pit_outs" if us == "home" else "a_pit_outs"
        used_cp_key = "h_used_cp" if us == "home" else "a_used_cp"

        if user_action == "pitch_rp" and team["rps"]:
            if rp_id:
                nxt = next((p for p in team["rps"] if p["id"] == rp_id), None)
            else:
                cur = state[pitcher_key]
                nxt = next((p for p in team["rps"] if p["id"] != cur), None)
            if nxt and nxt["id"] != state[pitcher_key]:
                state[pitcher_key] = nxt["id"]
                state[pit_outs_key] = 0
                state["log"].append(f"🔄 투수 교체: {nxt['name']}")
        elif user_action == "pitch_cp" and team["cp"] and not state[used_cp_key]:
            state[pitcher_key] = team["cp"]["id"]
            state[pit_outs_key] = 0
            state[used_cp_key] = True
            state["log"].append(f"🧯 마무리 등판: {team['cp']['name']}")

        off, _ = offense_defense(state)
        ai_pinch_hit(state, ctx, off)
        state["duel_done_pa"] = True
        txt = play_at_bat(state, ctx, "ibb" if user_action == "ibb" else None)
        state["log"].append(txt)
        if state["pending"] not in ("running", "challenge"):
            state["pending"] = None
            if advance_if_needed(state, ctx) == "game_over":
                return _finish()

    # ----- 자동 진행 루프 -----
    guard = 0
    while guard < 250 and state["pending"] not in ("running", "challenge", "mode_select"):
        guard += 1

        off, def_ = offense_defense(state)
        if us != def_ or state["h_pitcher" if def_ == "home" else "a_pitcher"] is None:
            auto_manage_pitcher(state, ctx, def_)

        decision = needs_decision(state, ctx)
        if decision:
            state["pending"] = decision
            break

        if us != off:
            ai_pinch_hit(state, ctx, off)
        txt = play_at_bat(state, ctx, None)
        state["log"].append(txt)

        if state["pending"] == "challenge":
            break
        if advance_if_needed(state, ctx) == "game_over":
            return _finish()

    return _save_and_reload()


def _reload(sb, live_id):
    return sb.table("dynasty_live_game").select("*").eq("id", live_id).execute().data[0]


# =========================================
# 시나리오 모드: 상황 생성 (기록 미반영)
# code: save_lead(9회말 수비 3점차 리드) / comeback(9회초 공격 2점 뒤짐 만루)
# =========================================
def start_scenario(save_id, code):
    sb = get_supabase()

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    user_team = next(t for t in teams if t["is_user"])
    opp = random.choice([t for t in teams if not t["is_user"]])

    save = sb.table("dynasty_save").select("season, week").eq("id", save_id).execute().data[0]

    if code == "save_lead":
        # 유저 홈, 9회초 수비, 3점 리드, 상대 무사 1·2루
        state = _base_state(user_team["id"], opp["id"], min(save["week"], 23), save["season"])
        state.update({
            "inning": 9, "half": "top",
            "h_score": 5, "a_score": 2,
            "view_mode": "manager", "pending": "pregame",
            "scenario": code,
        })
    else:  # comeback
        # 유저 원정, 9회초 공격, 2점 뒤짐, 1사 만루
        state = _base_state(opp["id"], user_team["id"], min(save["week"], 23), save["season"])
        state.update({
            "inning": 9, "half": "top",
            "h_score": 6, "a_score": 4,
            "outs": 1,
            "view_mode": "manager", "pending": "pregame",
            "scenario": code,
        })

    row = (
        sb.table("dynasty_live_game")
        .insert({"save_id": save_id, "schedule_id": None,
                 "state": state, "finished": False})
        .execute()
        .data[0]
    )

    # 주자 배치는 컨텍스트 로드 후
    ctx = load_context(save_id, state)
    off, _ = offense_defense(state)
    bat = ctx[off]["batters"]
    if code == "save_lead":
        state["bases"] = [bat[0]["id"], bat[1]["id"], None]
    else:
        state["bases"] = [bat[0]["id"], bat[1]["id"], bat[2]["id"]]
        state["a_order"] = 3
    sb.table("dynasty_live_game").update({"state": state}).eq("id", row["id"]).execute()
    row["state"] = state
    return row
