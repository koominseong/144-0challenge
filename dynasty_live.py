# dynasty_live.py - Part1
# =========================================
# KBO Dynasty - 감독 모드 (라이브 경기 엔진)
# 유저 팀 경기를 이닝/결정 포인트 단위로 진행
# 타석 판정은 dynasty_game._plate_appearance 재사용
#
# 상태(state JSON):
#   inning, half('top'/'bot'), h_score, a_score, outs,
#   bases[3](player_id or null), h_order, a_order,
#   h_pitcher_id, a_pitcher_id, h_pit_outs, a_pit_outs,
#   h_used_cp, a_used_cp, log[], acc{}, pending(결정 대기 상황)
# =========================================

import json
import random
from dynasty_utils import get_supabase
from dynasty_game import _plate_appearance, _load_all, _ensure
from dynasty_stats import flush_stats


# =========================================
# 라이브 경기 시작 (없으면 생성)
# return: live_game row
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
        "h_pitcher": None,   # 경기 전 선발 선택으로 채움
        "a_pitcher": None,
        "h_pit_outs": 0,
        "a_pit_outs": 0,
        "h_used_cp": False,
        "a_used_cp": False,
        "log": [],
        "acc": {},
        "pending": "pregame",  # pregame → at_bat 진행 → decision 대기
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
# 로스터/보정 로드 (라이브용 래핑)
# =========================================
def load_context(save_id, state):
    sb = get_supabase()
    teams, rosters, mods = _load_all(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    home = rosters.get(state["home_id"])
    away = rosters.get(state["away_id"])

    # player_id → player dict 색인
    players = {}
    for team in (home, away):
        if not team:
            continue
        for p in team["batters"] + team["sps"] + team["rps"]:
            players[p["id"]] = p
        if team["cp"]:
            players[team["cp"]["id"]] = team["cp"]

    return {
        "team_map": team_map,
        "home": home,
        "away": away,
        "home_mod": mods.get(state["home_id"], {}),
        "away_mod": mods.get(state["away_id"], {}),
        "players": players,
    }


# =========================================
# 유저 팀 판별
# =========================================
def user_side(state, ctx):
    for side, tid in (("home", state["home_id"]), ("away", state["away_id"])):
        t = ctx["team_map"].get(tid)
        if t and t["is_user"]:
            return side
    return None


# =========================================
# 현재 공격/수비 정보
# =========================================
def offense_defense(state):
    if state["half"] == "top":
        return "away", "home"   # 초: 원정 공격
    return "home", "away"


# =========================================
# 결정 대기 상황 판정
# 유저 팀 공격 + 주자 있음 + 2아웃 이하 + 접전(3점차 이내) → 작전 선택
# 유저 팀 수비 + 이닝 시작 → 투수 상태 확인
# =========================================
def needs_decision(state, ctx):
    us = user_side(state, ctx)
    if us is None:
        return None

    off, def_ = offense_defense(state)

    score_diff = abs(state["h_score"] - state["a_score"])

    if off == us:
        if any(state["bases"]) and state["outs"] < 2 and score_diff <= 3:
            return "offense"
    else:
        # 수비: 이닝 첫 타석 전에만 투수 결정
        if state["outs"] == 0 and not any(state["bases"]):
            return "pitching"

    return None

# dynasty_live.py - Part2

# =========================================
# 한 타석 진행 (자동 판정)
# action: None(강공) | "bunt" | "steal"
# return: 사건 텍스트
# =========================================
def play_at_bat(state, ctx, action=None):
    off, def_ = offense_defense(state)
    off_team = ctx[off]
    def_team = ctx[def_]

    order_key = "h_order" if off == "home" else "a_order"
    batter = off_team["batters"][state[order_key] % len(off_team["batters"])]

    pitcher_key = "h_pitcher" if def_ == "home" else "a_pitcher"
    pitcher = ctx["players"][state[pitcher_key]]

    pit_outs_key = "h_pit_outs" if def_ == "home" else "a_pit_outs"
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21)
    fatigue = min(0.25, max(0.0, (state[pit_outs_key] - max_outs * 0.7) / 60))

    off_id = state["home_id"] if off == "home" else state["away_id"]
    def_id = state["home_id"] if def_ == "home" else state["away_id"]

    mod = ctx["home_mod"] if off == "home" else ctx["away_mod"]
    bat_mod = mod.get("sim", 0.0) + (0.02 + ctx["home_mod"].get("home_adv", 0.0) if off == "home" else 0.0)

    acc = state["acc"]
    _ensure_acc(acc, batter, off_id)
    _ensure_acc(acc, pitcher, def_id)

    log_prefix = f"{state['inning']}회{'초' if state['half']=='top' else '말'}"

    # ---------- 도루 지시 ----------
    if action == "steal" and state["bases"][0] and not state["bases"][1]:
        runner = ctx["players"][state["bases"][0]]
        spd = runner["speed"] or 40
        success = random.random() < min(0.9, 0.45 + (spd - 50) * 0.008)
        if success:
            state["bases"][1] = state["bases"][0]
            state["bases"][0] = None
            acc[runner["id"]]["sb"] += 1
            return f"{log_prefix} 💨 {runner['name']} 도루 성공!"
        else:
            state["bases"][0] = None
            state["outs"] += 1
            return f"{log_prefix} ❌ {runner['name']} 도루 실패 (아웃)"

    # ---------- 번트 ----------
    if action == "bunt" and any(state["bases"]) and state["outs"] < 2:
        state[order_key] += 1
        # 성공률: 컨택 기반 + 승부사 감독 보정
        succ = 0.72 + ((batter["contact"] or 50) - 50) * 0.002
        if success_bunt := (random.random() < succ):
            # 주자 일괄 한 베이스 진루, 타자 아웃
            runs = 0
            if state["bases"][2]:
                runs += 1
                acc[batter["id"]]["rbi"] += 1
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

    # ---------- 일반 타석 ----------
    state[order_key] += 1
    result = _plate_appearance(batter, pitcher, fatigue, bat_mod)

    if result == "K":
        state["outs"] += 1
        acc[pitcher["id"]]["so"] += 1
        return f"{log_prefix} {batter['name']} 삼진"

    if result == "OUT":
        state["outs"] += 1
        if state["outs"] < 3 and state["bases"][2] and random.random() < 0.2:
            runner = ctx["players"][state["bases"][2]]
            state["bases"][2] = None
            acc[batter["id"]]["rbi"] += 1
            _add_runs(state, off, 1)
            return f"{log_prefix} {batter['name']} 희생타 → {runner['name']} 득점"
        return f"{log_prefix} {batter['name']} 범타"

    if result == "BB":
        runs = 0
        if state["bases"][0]:
            if state["bases"][1]:
                if state["bases"][2]:
                    runs += 1
                    acc[batter["id"]]["rbi"] += 1
                state["bases"][2] = state["bases"][1]
            state["bases"][1] = state["bases"][0]
        state["bases"][0] = batter["id"]
        _add_runs(state, off, runs)
        txt = f"{log_prefix} {batter['name']} 볼넷"
        if runs:
            txt += " (밀어내기 +1)"
        return txt

    # 안타류
    advance = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}[result]
    acc[batter["id"]]["hits"] += 1
    if result == "HR":
        acc[batter["id"]]["hr"] += 1

    runs = 0
    for base_idx in (2, 1, 0):
        rid = state["bases"][base_idx]
        if rid is None:
            continue
        new_idx = base_idx + advance
        if result == "1B" and base_idx == 1 and random.random() < 0.6:
            new_idx = 4
        state["bases"][base_idx] = None
        if new_idx >= 3:
            runs += 1
            acc[batter["id"]]["rbi"] += 1
        else:
            state["bases"][new_idx] = rid

    if advance >= 4:
        runs += 1
        acc[batter["id"]]["rbi"] += 1
    else:
        state["bases"][advance - 1] = batter["id"]

    _add_runs(state, off, runs)

    kind = {"1B": "안타", "2B": "2루타", "3B": "3루타", "HR": "🎆 홈런"}[result]
    txt = f"{log_prefix} {batter['name']} {kind}"
    if runs:
        txt += f" (+{runs}점)"
    return txt


def _add_runs(state, off, runs):
    if runs <= 0:
        return
    if off == "home":
        state["h_score"] += runs
    else:
        state["a_score"] += runs


def _ensure_acc(acc, p, team_id):
    key = str(p["id"])
    if key not in acc:
        acc[key] = {
            "team_id": team_id, "games": 0, "hits": 0, "hr": 0,
            "rbi": 0, "sb": 0, "wins": 0, "losses": 0, "saves": 0, "so": 0,
        }
    return acc[key]

# =========================================
# 이닝/경기 전환 처리
# return: "continue" | "game_over"
# =========================================
def advance_if_needed(state, ctx):
    pit_outs_key = "h_pit_outs" if state["half"] == "top" else "a_pit_outs"

    if state["outs"] >= 3:
        state[pit_outs_key] += 3
        state["outs"] = 0
        state["bases"] = [None, None, None]

        if state["half"] == "top":
            # 9회 말 홈 리드 → 경기 종료
            if state["inning"] >= 9 and state["h_score"] > state["a_score"]:
                return "game_over"
            state["half"] = "bot"
        else:
            if state["inning"] >= 9 and state["h_score"] != state["a_score"]:
                return "game_over"
            if state["inning"] >= 12:
                return "game_over"  # 무승부
            state["inning"] += 1
            state["half"] = "top"

    return "continue"


# =========================================
# AI 투수 자동 운용 (유저가 수비 아닐 때 / 자동 진행 시)
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

    # 9회+ 세이브 상황 → 마무리
    if state["inning"] >= 9 and 0 < lead <= 3 and team["cp"] and not state[used_cp_key]:
        state[pitcher_key] = team["cp"]["id"]
        state[pit_outs_key] = 0
        state[used_cp_key] = True
        return

    # 체력 소진 → 불펜
    stamina = pitcher["stamina"] or 50
    max_outs = int(12 + stamina * 0.21)
    if state[pit_outs_key] >= max_outs and team["rps"]:
        idx = min(len(team["rps"]) - 1, (state[pit_outs_key] - max_outs) // 6)
        state[pitcher_key] = team["rps"][idx]["id"]

  # dynasty_live.py - Part3

# =========================================
# 경기 종료 처리: 승패/세이브 판정 → 스케줄/팀/기록 반영 → live 종료
# =========================================
def finish_live_game(save_id, live_row, state, ctx):
    sb = get_supabase()

    hs, as_ = state["h_score"], state["a_score"]
    home_id, away_id = state["home_id"], state["away_id"]

    # ----- 승/패/세이브 -----
    acc = state["acc"]
    if hs != as_:
        if hs > as_:
            w_side, w_id = "home", home_id
            l_side, l_id = "away", away_id
        else:
            w_side, w_id = "away", away_id
            l_side, l_id = "home", home_id

        w_team = ctx[w_side]
        l_team = ctx[l_side]

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

    # ----- 출장 기록 (타자 전원 + 선발) -----
    for side, tid in (("home", home_id), ("away", away_id)):
        team = ctx[side]
        for p in team["batters"]:
            _ensure_acc(acc, p, tid)["games"] += 1
        if team["sps"]:
            sp = team["sps"][state["week"] % len(team["sps"])]
            _ensure_acc(acc, sp, tid)["games"] += 1

    # ----- 스케줄 반영 -----
    sb.table("dynasty_schedule").update(
        {"home_score": hs, "away_score": as_, "played": True}
    ).eq("id", live_row["schedule_id"]).execute()

    # ----- 팀 승패 반영 -----
    for tid, my, opp in ((home_id, hs, as_), (away_id, as_, hs)):
        t = ctx["team_map"][tid]
        if my > opp:
            t["wins"] += 1
        elif opp > my:
            t["losses"] += 1
        else:
            t["ties"] += 1
        sb.table("dynasty_team").update(
            {"wins": t["wins"], "losses": t["losses"], "ties": t["ties"]}
        ).eq("id", tid).execute()

    # ----- 개인 기록 반영 (str 키 → int 변환) -----
    int_acc = {}
    for k, v in acc.items():
        try:
            int_acc[int(k)] = v
        except (TypeError, ValueError):
            continue
    flush_stats(save_id, state["season"], int_acc)

    # ----- live 종료 -----
    state["pending"] = "finished"
    sb.table("dynasty_live_game").update(
        {"state": state, "finished": True}
    ).eq("id", live_row["id"]).execute()


# =========================================
# 진행 컨트롤러: 다음 결정 포인트(또는 종료)까지 자동 진행
# user_action: None | "bunt" | "steal" | "swing"
#              | "pitch_keep" | "pitch_rp" | "pitch_cp"
# =========================================
def progress(save_id, live_id, user_action=None):
    sb = get_supabase()

    live_row = (
        sb.table("dynasty_live_game")
        .select("*")
        .eq("id", live_id)
        .execute()
        .data[0]
    )
    if live_row["finished"]:
        return live_row

    state = live_row["state"]
    ctx = load_context(save_id, state)
    us = user_side(state, ctx)

    # ----- 경기 전: 선발 확정 -----
    if state["pending"] == "pregame":
        auto_manage_pitcher(state, ctx, "home")
        auto_manage_pitcher(state, ctx, "away")
        state["log"].append("▶ 플레이볼!")
        state["pending"] = None

    # ----- 유저 투수 결정 반영 -----
    if user_action in ("pitch_keep", "pitch_rp", "pitch_cp") and us:
        team = ctx[us]
        pitcher_key = "h_pitcher" if us == "home" else "a_pitcher"
        pit_outs_key = "h_pit_outs" if us == "home" else "a_pit_outs"
        used_cp_key = "h_used_cp" if us == "home" else "a_used_cp"

        if user_action == "pitch_rp" and team["rps"]:
            cur = state[pitcher_key]
            nxt = next((p for p in team["rps"] if p["id"] != cur), None)
            if nxt:
                state[pitcher_key] = nxt["id"]
                state[pit_outs_key] = 0
                state["log"].append(f"🔄 투수 교체: {nxt['name']}")
        elif user_action == "pitch_cp" and team["cp"] and not state[used_cp_key]:
            state[pitcher_key] = team["cp"]["id"]
            state[pit_outs_key] = 0
            state[used_cp_key] = True
            state["log"].append(f"🧯 마무리 등판: {team['cp']['name']}")
        state["pending"] = None

    # ----- 유저 공격 작전 → 해당 타석 1회 실행 -----
    if user_action in ("bunt", "steal", "swing") and us:
        action = None if user_action == "swing" else user_action
        txt = play_at_bat(state, ctx, action)
        state["log"].append(txt)
        state["pending"] = None
        if advance_if_needed(state, ctx) == "game_over":
            finish_live_game(save_id, live_row, state, ctx)
            return _reload(sb, live_id)

    # ----- 자동 진행 루프: 다음 결정 포인트까지 -----
    guard = 0
    while guard < 200:
        guard += 1

        # 상대(AI) 투수 자동 운용
        off, def_ = offense_defense(state)
        def_side_is_user = (us == def_)
        if not def_side_is_user:
            auto_manage_pitcher(state, ctx, def_)
        elif state["h_pitcher" if def_ == "home" else "a_pitcher"] is None:
            auto_manage_pitcher(state, ctx, def_)

        # 결정 포인트 체크
        decision = needs_decision(state, ctx)
        if decision:
            state["pending"] = decision
            break

        txt = play_at_bat(state, ctx, None)
        state["log"].append(txt)

        if advance_if_needed(state, ctx) == "game_over":
            finish_live_game(save_id, live_row, state, ctx)
            return _reload(sb, live_id)

    # 로그 최근 60줄 유지
    state["log"] = state["log"][-60:]

    sb.table("dynasty_live_game").update({"state": state}).eq("id", live_id).execute()
    return _reload(sb, live_id)


def _reload(sb, live_id):
    return (
        sb.table("dynasty_live_game")
        .select("*")
        .eq("id", live_id)
        .execute()
        .data[0]
    )
