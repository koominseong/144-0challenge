# dynasty_live.py - 최종 통합본 Part1
# =========================================
# KBO Dynasty - 감독 모드 (라이브 경기 엔진)
# 매 타석 개입: 공격(강공/번트/도루/히트앤런/대타)
#             수비(투수 유지/불펜 지명/마무리/고의4구/시프트)
# 추가: 주루 판단(보내기/멈추기), 컨디션, 수비력, AI 대타,
#       승률 게이지, 박스스코어, 하이라이트, 팬 보너스
# =========================================

import math
import random
from dynasty_utils import get_supabase
from dynasty_game import _plate_appearance, _load_all
from dynasty_stats import flush_stats

FAN_MAX = 200000


# =========================================
# 라이브 경기 시작 (없으면 생성)
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
        sb.table("dynasty_schedule")
        .select("*")
        .eq("id", schedule_id)
        .execute()
        .data[0]
    )

    state = {
        "home_id": g["home_team"],
        "away_id": g["away_team"],
        "week": g["week"],
        "season": g["season"],
        "inning": 1,
        "half": "top",
        "h_score": 0,
        "a_score": 0,
        "outs": 0,
        "bases": [None, None, None],
        "h_order": 0,
        "a_order": 0,
        "h_pitcher": None,
        "a_pitcher": None,
        "h_pit_outs": 0,
        "a_pit_outs": 0,
        "h_used_cp": False,
        "a_used_cp": False,
        "shift": False,
        "ph_over": {},      # {"home": {"slot": pid}}
        "used_ph": [],
        "cond": {},         # {str(pid): -3..+3}
        "send_runner": None,
        "send_batter": None,
        "highlights": None,
        "log": [],
        "acc": {},
        "pending": "pregame",
    }

    row = (
        sb.table("dynasty_live_game")
        .insert(
            {"save_id": save_id, "schedule_id": schedule_id,
             "state": state, "finished": False}
        )
        .execute()
        .data[0]
    )
    return row


# =========================================
# 로스터/보정 로드 (벤치 + 수비력 평균 포함)
# =========================================
def load_context(save_id, state):
    sb = get_supabase()
    teams, rosters, mods = _load_all(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    home = rosters.get(state["home_id"])
    away = rosters.get(state["away_id"])

    # 벤치 (대타용, 양팀)
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

    # 수비력: 타자진 평균 OVR (호수비 확률에 사용)
    players = {}
    for team in (home, away):
        if not team:
            continue
        for p in team["batters"] + team["sps"] + team["rps"] + team.get("bench", []):
            players[p["id"]] = p
        if team["cp"]:
            players[team["cp"]["id"]] = team["cp"]
    
    # 수비력: 라인업 평균 OVR (대수비 오버라이드 반영)
    for side_key, team in (("home", home), ("away", away)):
        if not team or not team["batters"]:
            if team:
                team["def_avg"] = 60
            continue
        over = (state.get("ph_over") or {}).get(side_key, {})
        vals = []
        for i, p in enumerate(team["batters"]):
            oid = over.get(str(i))
            vals.append((players_pre.get(oid, p) if oid else p)["overall"])
        team["def_avg"] = sum(vals) / len(vals)

 # 스태프 상세 효과 (라이브 반영용)
    try:
        from dynasty_staff import get_staff_effects
        fx = get_staff_effects(save_id)
    except Exception:
        fx = {}

    return {
        "team_map": team_map,
        "home": home,
        "away": away,
        "home_mod": mods.get(state["home_id"], {}),
        "away_mod": mods.get(state["away_id"], {}),
        "home_fx": fx.get(state["home_id"], {}),
        "away_fx": fx.get(state["away_id"], {}),
        "players": players,
    }


# =========================================
# 유저 팀 / 공수 판별
# =========================================
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


# =========================================
# 결정 대기 판정 (매 타석)
# =========================================
def needs_decision(state, ctx):
    us = user_side(state, ctx)
    if us is None:
        return None
    off, _ = offense_defense(state)
    if off == us:
        return "offense"
    return "pitching"


# =========================================
# 컨디션 롤 (경기 시작 시 1회)
# =========================================
def roll_conditions(state, ctx):
    cond = {}
    for pid in ctx["players"]:
        cond[str(pid)] = random.randint(-3, 3)
    state["cond"] = cond


def _cond(state, pid):
    return state.get("cond", {}).get(str(pid), 0)


# =========================================
# 승률 게이지 (유저 팀 기준 간이 추정)
# =========================================
def win_prob(state, ctx):
    us = user_side(state, ctx)
    if us is None:
        return 50

    my = state["h_score"] if us == "home" else state["a_score"]
    opp = state["a_score"] if us == "home" else state["h_score"]
    diff = my - opp

    # 경기 진행률 (0~1)
    outs_total = (state["inning"] - 1) * 6 + (3 if state["half"] == "bot" else 0) + state["outs"]
    prog = min(1.0, outs_total / 54)

    # 점수차 가중: 후반일수록 크게
    x = diff * (0.45 + prog * 0.9)

    # 공격 중 주자 보너스
    off, _ = offense_defense(state)
    if off == us:
        x += sum(1 for b in state["bases"] if b) * 0.12

    # 홈팀 미세 우위
    if us == "home":
        x += 0.08

    p = 1 / (1 + math.exp(-x))
    return max(3, min(97, round(p * 100)))

# dynasty_live.py - 최종 통합본 Part2

# =========================================
# 개인 기록 acc (JSON 저장 대비 str 키 통일)
# =========================================
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


def _current_batter(state, ctx, off):
    team = ctx[off]
    order_key = "h_order" if off == "home" else "a_order"
    slot = state[order_key] % len(team["batters"])
    over = state.get("ph_over", {}).get(off, {})
    over_id = over.get(str(slot))
    return (ctx["players"][over_id] if over_id else team["batters"][slot]), slot


# =========================================
# 한 타석 진행
# action: None(강공) | "bunt" | "steal" | "hitrun" | "ibb"
# return: 사건 텍스트 (state["pending"]이 "running"이 되면 주루 판단 대기)
# =========================================
def play_at_bat(state, ctx, action=None):
    off, def_ = offense_defense(state)
    off_team = ctx[off]
    def_team = ctx[def_]

    order_key = "h_order" if off == "home" else "a_order"
    batter, slot = _current_batter(state, ctx, off)

    pitcher_key = "h_pitcher" if def_ == "home" else "a_pitcher"
    pitcher = ctx["players"][state[pitcher_key]]

    pit_outs_key = "h_pit_outs" if def_ == "home" else "a_pit_outs"
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21)
    
    def_fx = ctx["home_fx"] if def_ == "home" else ctx["away_fx"]
    off_fx = ctx["home_fx"] if off == "home" else ctx["away_fx"]

    pit_outs_key = "h_pit_outs" if def_ == "home" else "a_pit_outs"
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21) + def_fx.get("sp_outs", 0)
    fatigue = min(0.25, max(0.0, (state[pit_outs_key] - max_outs * 0.7) / 60))
    fatigue *= (1 - def_fx.get("sp_fatigue_cut", 0.0))
    
    off_id = state["home_id"] if off == "home" else state["away_id"]
    def_id = state["home_id"] if def_ == "home" else state["away_id"]

    mod = ctx["home_mod"] if off == "home" else ctx["away_mod"]
    bat_mod = mod.get("sim", 0.0) + ((0.02 + ctx["home_mod"].get("home_adv", 0.0)) if off == "home" else 0.0)
    # 컨디션 반영 (타자 컨디션 - 투수 컨디션)
    bat_mod += (_cond(state, batter["id"]) - _cond(state, pitcher["id"])) * 0.004
    bat_mod += off_fx.get("bat_mod", 0.0) - def_fx.get("so_bonus", 0.0)

    acc = state["acc"]
    bs = _ensure_acc(acc, batter, off_id)
    ps = _ensure_acc(acc, pitcher, def_id)

    us = user_side(state, ctx)
    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"

    # ---------- 고의4구 (수비 지시) ----------
    if action == "ibb":
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

    # ---------- 도루 지시 ----------
    if action == "steal" and state["bases"][0] and not state["bases"][1]:
        runner = ctx["players"][state["bases"][0]]
        rs = _ensure_acc(acc, runner, off_id)
        spd = (runner["speed"] or 40) + _cond(state, runner["id"])
        steal_p = 0.45 + (spd - 50) * 0.008 + off_fx.get("steal_bonus", 0.0) - def_fx.get("opp_steal_cut", 0.0)
        if random.random() < min(0.9, max(0.1, steal_p)):
            state["bases"][1] = state["bases"][0]
            state["bases"][0] = None
            rs["sb"] += 1
            return f"{log_prefix} 💨 {runner['name']} 도루 성공!"
        else:
            state["bases"][0] = None
            state["outs"] += 1
            return f"{log_prefix} ❌ {runner['name']} 도루 실패 (아웃)"

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
            txt = f"{log_prefix} 🥢 {batter['name']} 희생번트 성공"
            if runs:
                txt += f" (+{runs}점)"
            return txt
        else:
            state["outs"] += 1
            return f"{log_prefix} ❌ {batter['name']} 번트 실패 (아웃)"

    # ---------- 히트앤런 ----------
    hitrun = (action == "hitrun" and state["bases"][0] and state["outs"] < 2)

    # ---------- 일반 타석 ----------
    state[order_key] += 1
    result = _plate_appearance(batter, pitcher, fatigue, bat_mod + (0.015 if hitrun else 0.0))

    # 불펜코치: 구원 등판 투수 보정 (선발이 아니면)
    def_team_obj = ctx[def_]
    sp_today = def_team_obj["sps"][state["week"] % len(def_team_obj["sps"])] if def_team_obj["sps"] else None
    if sp_today and pitcher["id"] != sp_today["id"]:
        bat_mod -= def_fx.get("rp_boost", 0) * 0.004

    # 수비 시프트 (유저 수비 시)
    if state.get("shift") and def_ == us:
        my_fx = def_fx
        if result == "1B" and random.random() < 0.22 + my_fx.get("shift_plus", 0.0):
            result = "OUT"
            state["log"].append(f"{log_prefix} 🛡 시프트가 타구를 삼킴!")
        elif result == "OUT" and random.random() < max(0.02, 0.08 - my_fx.get("shift_backfire_cut", 0.0)):
            result = "1B"
            state["log"].append(f"{log_prefix} ⚠ 시프트 빈 곳으로 안타...")

    # 호수비 (수비팀 평균 OVR 기반, 안타 강탈)
    if result in ("1B", "2B"):
        def_avg = def_team.get("def_avg", 60) + def_fx.get("def_bonus", 0)
        if def_avg > 62 and random.random() < (def_avg - 62) * 0.004:
            result = "OUT"
            state["log"].append(f"{log_prefix} ✨ 호수비! 안타성 타구를 걷어냄")

    if result == "K":
        state["outs"] += 1
        ps["so"] += 1
        txt = f"{log_prefix} {batter['name']} 삼진"
        if hitrun and state["bases"][0] and random.random() < 0.4:
            runner = ctx["players"][state["bases"][0]]
            state["bases"][0] = None
            state["outs"] += 1
            txt += f" → 런앤히트 {runner['name']} 협살 아웃!"
        return txt

    if result == "OUT":
        state["outs"] += 1
        if hitrun and state["bases"][0] and state["outs"] < 3 and random.random() < 0.5:
            # 땅볼 사이 진루
            if not state["bases"][1]:
                state["bases"][1] = state["bases"][0]
                state["bases"][0] = None
                return f"{log_prefix} {batter['name']} 범타 (히트앤런: 주자 2루 진루)"
        if state["outs"] < 3 and state["bases"][2] and random.random() < 0.2:
            runner = ctx["players"][state["bases"][2]]
            state["bases"][2] = None
            bs["rbi"] += 1
            _add_runs(state, off, 1)
            return f"{log_prefix} {batter['name']} 희생타 → {runner['name']} 득점"
        return f"{log_prefix} {batter['name']} 범타"

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
        txt = f"{log_prefix} {batter['name']} 볼넷"
        if runs:
            txt += " (밀어내기 +1)"
        return txt

    # ----- 안타류 -----
    advance = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}[result]
    bs["hits"] += 1
    if result == "HR":
        bs["hr"] += 1

    runner_on_first = state["bases"][0]
    runs = 0
    for base_idx in (2, 1, 0):
        rid = state["bases"][base_idx]
        if rid is None:
            continue
        new_idx = base_idx + advance
        # 히트앤런: 단타에 1루 주자 무조건 3루행
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

    kind = {"1B": "안타", "2B": "2루타", "3B": "3루타", "HR": "🎆 홈런"}[result]
    txt = f"{log_prefix} {batter['name']} {kind}"
    if hitrun and result == "1B":
        txt += " (히트앤런: 주자 3루!)"
    if runs:
        txt += f" (+{runs}점)"
    if result == "HR":
        hl = state.setdefault("hl", [])
        hl.append(f"{log_prefix} {batter['name']} 홈런 (+{runs}점)")

    # ----- 유저 공격 단타 + 1루 주자가 2루에 멈춘 상황 → 3루행 판단 -----
    if (result == "1B" and not hitrun and off == us
            and runner_on_first and state["bases"][1] == runner_on_first
            and not state["bases"][2] and state["outs"] < 3):
        runner = ctx["players"][runner_on_first]
        state["send_runner"] = runner_on_first
        state["pending"] = "running"
        txt += f" — {runner['name']} 3루 도전?"

    return txt


# =========================================
# 주루 판단 실행 (보내기)
# =========================================
def try_send_runner(state, ctx):
    off, def_ = offense_defense(state)
    rid = state.get("send_runner")
    state["send_runner"] = None
    if not rid or state["bases"][1] != rid:
        return None

    runner = ctx["players"][rid]
    def_avg = ctx[def_].get("def_avg", 60)
    spd = (runner["speed"] or 40) + _cond(state, rid)
    off_fx = ctx["home_fx"] if off == "home" else ctx["away_fx"]
    succ = 0.55 + (spd - 50) * 0.01 - (def_avg - 60) * 0.005 + off_fx.get("send_bonus", 0.0)

    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"
    if random.random() < max(0.15, min(0.92, succ)):
        state["bases"][1] = None
        state["bases"][2] = rid
        return f"{log_prefix} 🏃 {runner['name']} 3루 슬라이딩 세이프!"
    else:
        state["bases"][1] = None
        state["outs"] += 1
        return f"{log_prefix} ❌ {runner['name']} 3루에서 태그 아웃..."


# =========================================
# 이닝/경기 전환
# =========================================
def advance_if_needed(state, ctx):
    pit_outs_key = "h_pit_outs" if state["half"] == "top" else "a_pit_outs"

    if state["outs"] >= 3:
        state[pit_outs_key] += 3
        state["outs"] = 0
        state["bases"] = [None, None, None]
        state["send_runner"] = None

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
# AI 투수 자동 운용
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

    stamina = pitcher["stamina"] or 50
    fx = ctx["home_fx"] if side == "home" else ctx["away_fx"]
    max_outs = int(12 + stamina * 0.21) + fx.get("rp_outs", 0) + fx.get("sp_outs", 0)
    if state[pit_outs_key] >= max_outs and team["rps"]:
        idx = min(len(team["rps"]) - 1, (state[pit_outs_key] - max_outs) // 6)
        state[pitcher_key] = team["rps"][idx]["id"]


# =========================================
# AI 대타 (7회+ 접전, 현재 타자보다 벤치 최강이 5+ 높으면)
# =========================================
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
        state["log"].append(f"🔁 [{ctx['team_map'][state['home_id'] if off=='home' else state['away_id']]['team_name']}] 대타 {best['name']} 투입")

# dynasty_live.py - 최종 통합본 Part3

# =========================================
# 경기 종료: 승패/세이브 → 스케줄/팀 반영 → MVP/하이라이트 → 팬 보너스
# =========================================
def finish_live_game(save_id, live_row, state, ctx):
    sb = get_supabase()

    hs, as_ = state["h_score"], state["a_score"]
    home_id, away_id = state["home_id"], state["away_id"]
    acc = state["acc"]

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

    # ----- MVP (이 경기 기여도) -----
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

    # ----- 스케줄 반영 -----
    sb.table("dynasty_schedule").update(
        {"home_score": hs, "away_score": as_, "played": True}
    ).eq("id", live_row["schedule_id"]).execute()

    # ----- 팀 승패 + 감독 경기 팬 보너스 -----
    us = user_side(state, ctx)
    for tid, my, opp in ((home_id, hs, as_), (away_id, as_, hs)):
        t = ctx["team_map"][tid]
        if my > opp:
            t["wins"] += 1
        elif opp > my:
            t["losses"] += 1
        else:
            t["ties"] += 1

        upd = {"wins": t["wins"], "losses": t["losses"], "ties": t["ties"]}

        if us and tid == (home_id if us == "home" else away_id):
            fans = t.get("fans") or 10000
            rate = 1.003 if my > opp else 1.001
            upd["fans"] = min(FAN_MAX, int(fans * rate))

        sb.table("dynasty_team").update(upd).eq("id", tid).execute()

    # ----- 개인 기록 (str → int 키) -----
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
# 진행 컨트롤러
# user_action:
#   공격: swing | bunt | steal | hitrun | ph(+ph_id)
#   주루: send | hold
#   수비: pitch_keep | pitch_rp(+rp_id) | pitch_cp | ibb
#   토글: shift_on | shift_off
# =========================================
def progress(save_id, live_id, user_action=None, ph_id=None, rp_id=None, user_action_slot=None):
    sb = get_supabase()

    live_row = (
        sb.table("dynasty_live_game").select("*").eq("id", live_id).execute().data[0]
    )
    if live_row["finished"]:
        return live_row

    state = live_row["state"]
    ctx = load_context(save_id, state)
    us = user_side(state, ctx)

    def _finish():
        finish_live_game(save_id, live_row, state, ctx)
        return _reload(sb, live_id)

    def _after_play():
        return advance_if_needed(state, ctx) == "game_over"

    # ----- 경기 전 -----
    if state["pending"] == "pregame":
        auto_manage_pitcher(state, ctx, "home")
        auto_manage_pitcher(state, ctx, "away")
        if not state.get("cond"):
            roll_conditions(state, ctx)
        state["log"].append("▶ 플레이볼!")
        state["pending"] = None

    # ----- 주루 판단 (send/hold) -----
    if state["pending"] == "running":
        if user_action == "send":
            txt = try_send_runner(state, ctx)
            if txt:
                state["log"].append(txt)
            state["pending"] = None
            if _after_play():
                return _finish()
        elif user_action == "hold":
            state["send_runner"] = None
            state["pending"] = None
        else:
            # 다른 액션은 무시하고 판단 대기 유지
            sb.table("dynasty_live_game").update({"state": state}).eq("id", live_id).execute()
            return _reload(sb, live_id)

    # ----- 시프트 토글 (타석 소비 안 함) -----
    if user_action in ("shift_on", "shift_off") and us:
        state["shift"] = (user_action == "shift_on")
        state["log"].append("🛡 수비 시프트 " + ("가동" if state["shift"] else "해제"))

    # ----- 대타 (교체 후 그 타석 강공) -----
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
            if state["pending"] != "running":
                state["pending"] = None
                if _after_play():
                    return _finish()

    # ----- 대주자 (1루 주자 교체, 타석 소비 안 함) -----
    if user_action == "pr" and us and ph_id and state["pending"] == "offense":
        team = ctx[us]
        rid = state["bases"][0]
        used = state.setdefault("used_ph", [])
        sub = next((p for p in team.get("bench", []) if p["id"] == ph_id and p["id"] not in used), None)
        if rid and sub:
            # 교체된 주자의 타순 슬롯 찾기 (오버라이드 포함)
            over = state.setdefault("ph_over", {}).setdefault(us, {})
            slot = None
            for i, p in enumerate(team["batters"]):
                cur_id = over.get(str(i), p["id"]) if isinstance(over.get(str(i)), int) else (over.get(str(i)) or p["id"])
                if cur_id == rid:
                    slot = i
                    break
            if slot is not None:
                over[str(slot)] = sub["id"]
            used.append(sub["id"])
            state["bases"][0] = sub["id"]
            state["log"].append(f"🏃 대주자 {sub['name']} 투입 (1루)")
        # pending 유지 → 이어서 도루/히트앤런 지시 가능

    # ----- 대수비 (라인업 슬롯 교체, 타석 소비 안 함) -----
    if user_action == "ds" and us and ph_id and state["pending"] == "pitching":
        team = ctx[us]
        slot = request_slot = None
        try:
            request_slot = int(user_action_slot) if user_action_slot is not None else None
        except (TypeError, ValueError):
            request_slot = None
        used = state.setdefault("used_ph", [])
        sub = next((p for p in team.get("bench", []) if p["id"] == ph_id and p["id"] not in used), None)
        if sub and request_slot is not None and 0 <= request_slot < len(team["batters"]):
            state.setdefault("ph_over", {}).setdefault(us, {})[str(request_slot)] = sub["id"]
            used.append(sub["id"])
            state["log"].append(f"🧤 대수비 {sub['name']} 투입 ({request_slot + 1}번 자리)")
        # pending 유지 → 이어서 투수 결정

    # ----- 공격 작전 -----
    if user_action in ("swing", "bunt", "steal", "hitrun") and us and state["pending"] == "offense":
        action = None if user_action == "swing" else user_action
        txt = play_at_bat(state, ctx, action)
        state["log"].append(txt)
        if state["pending"] != "running":
            state["pending"] = None
            if _after_play():
                return _finish()

    # ----- 수비: 투수 결정 → 상대 타석 1회 실행 -----
    if user_action in ("pitch_keep", "pitch_rp", "pitch_cp", "ibb") and us and state["pending"] == "pitching":
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

        # 상대(AI) 대타 체크 후 타석 진행
        off, _ = offense_defense(state)
        ai_pinch_hit(state, ctx, off)
        txt = play_at_bat(state, ctx, "ibb" if user_action == "ibb" else None)
        state["log"].append(txt)
        state["pending"] = None
        if _after_play():
            return _finish()

    # ----- 다음 결정 포인트 탐색 (자동 진행 안전망) -----
    guard = 0
    while guard < 200 and state["pending"] not in ("running",):
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

        if advance_if_needed(state, ctx) == "game_over":
            return _finish()

    state["log"] = state["log"][-60:]
    sb.table("dynasty_live_game").update({"state": state}).eq("id", live_id).execute()
    return _reload(sb, live_id)


def _reload(sb, live_id):
    return (
        sb.table("dynasty_live_game").select("*").eq("id", live_id).execute().data[0]
    )
