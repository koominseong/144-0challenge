# dynasty_game.py - Part1
# =========================================
# KBO Dynasty - 경기 시뮬레이션 엔진 (통합 최종본)
# 모드 선택: sim_mode = 'detail'(타석 단위) | 'fast'(전력 기반 자동)
# 사전 준비: ALTER TABLE dynasty_save ADD COLUMN IF NOT EXISTS sim_mode text DEFAULT 'detail';
# Part1 / Part2 / Part3 을 이어 붙이면 완성된다.
# =========================================

import random
from dynasty_utils import get_supabase
from dynasty_stats import flush_stats


# =========================================
# 시뮬 모드 조회
# =========================================
def _get_sim_mode(sb, save_id):
    save = (
        sb.table("dynasty_save")
        .select("sim_mode")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    return save.get("sim_mode") or "detail"


# =========================================
# 한 주 경기 전체 시뮬레이션 (진입점)
# =========================================
def simulate_week(save_id, season, week):
    sb = get_supabase()

    mode = _get_sim_mode(sb, save_id)

    games = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .eq("week", week)
        .eq("played", False)
        .execute()
        .data
    )
    if not games:
        return

    teams, rosters, mods = _load_all(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    acc = {}
    game_upserts = []

    if mode == "fast":
        powers = {tid: _calc_power(rosters.get(tid), mods.get(tid, {})) for tid in team_map}
        for g in games:
            hs, as_ = _fast_game(powers[g["home_team"]], powers[g["away_team"]])
            game_upserts.append(_game_row(g, season, hs, as_))
            _apply_result(team_map[g["home_team"]], team_map[g["away_team"]], hs, as_)
            _fast_record(acc, rosters, g["home_team"], g["away_team"], hs, as_, week)
    else:
        for g in games:
            hs, as_ = _play_game(
                rosters.get(g["home_team"]), rosters.get(g["away_team"]),
                mods.get(g["home_team"], {}), mods.get(g["away_team"], {}),
                week, acc, g["home_team"], g["away_team"],
            )
            game_upserts.append(_game_row(g, season, hs, as_))
            _apply_result(team_map[g["home_team"]], team_map[g["away_team"]], hs, as_)

    sb.table("dynasty_schedule").upsert(game_upserts).execute()
    _upsert_teams(sb, teams)
    flush_stats(save_id, season, acc)


# =========================================
# 남은 시즌 전체 일괄 (진입점)
# =========================================
def simulate_rest_of_season(save_id, season, from_week):
    sb = get_supabase()

    mode = _get_sim_mode(sb, save_id)

    games = (
        sb.table("dynasty_schedule")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .gte("week", from_week)
        .eq("played", False)
        .execute()
        .data
    )
    if not games:
        return

    teams, rosters, mods = _load_all(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    acc = {}
    game_upserts = []
    games.sort(key=lambda g: g["week"])

    if mode == "fast":
        powers = {tid: _calc_power(rosters.get(tid), mods.get(tid, {})) for tid in team_map}
        for g in games:
            hs, as_ = _fast_game(powers[g["home_team"]], powers[g["away_team"]])
            game_upserts.append(_game_row(g, season, hs, as_))
            _apply_result(team_map[g["home_team"]], team_map[g["away_team"]], hs, as_)
            _fast_record(acc, rosters, g["home_team"], g["away_team"], hs, as_, g["week"])
    else:
        for g in games:
            hs, as_ = _play_game(
                rosters.get(g["home_team"]), rosters.get(g["away_team"]),
                mods.get(g["home_team"], {}), mods.get(g["away_team"], {}),
                g["week"], acc, g["home_team"], g["away_team"],
            )
            game_upserts.append(_game_row(g, season, hs, as_))
            _apply_result(team_map[g["home_team"]], team_map[g["away_team"]], hs, as_)

    for i in range(0, len(game_upserts), 100):
        sb.table("dynasty_schedule").upsert(game_upserts[i : i + 100]).execute()
    _upsert_teams(sb, teams)
    flush_stats(save_id, season, acc)


# =========================================
# 데이터 로드: 팀 / 1군 로스터 / 보정치
# =========================================
def _load_all(sb, save_id):
    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    rows = (
        sb.table("dynasty_roster")
        .select("team_id, role, depth, dynasty_player(*)")
        .eq("save_id", save_id)
        .in_("role", ["START", "SP", "CP", "RP"])
        .execute()
        .data
    )

    rosters = {}
    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        team = rosters.setdefault(
            r["team_id"], {"batters": [], "sps": [], "rps": [], "cp": None}
        )
        if r["role"] == "START":
            team["batters"].append((r["depth"], p))
        elif r["role"] == "SP":
            team["sps"].append((r["depth"], p))
        elif r["role"] == "RP":
            team["rps"].append((r["depth"], p))
        elif r["role"] == "CP":
            team["cp"] = p

    for t in rosters.values():
        t["batters"] = [p for _, p in sorted(t["batters"], key=lambda x: x[0])]
        t["sps"] = [p for _, p in sorted(t["sps"], key=lambda x: x[0])]
        t["rps"] = [p for _, p in sorted(t["rps"], key=lambda x: x[0])]

    mods = {t["id"]: {"sim": 0.0, "home_adv": 0.0, "clutch": False} for t in teams}
    try:
        from dynasty_staff import get_staff_effects
        for tid, e in get_staff_effects(save_id).items():
            if tid in mods:
                mods[tid]["sim"] = e.get("sim", 0.0)
                mods[tid]["clutch"] = e.get("clutch", False)
    except Exception as ex:
        print(f"[dynasty_game] 스태프 효과 skip: {ex}")
    try:
        from dynasty_facility import get_facility_effects
        for tid, e in get_facility_effects(save_id).items():
            if tid in mods:
                mods[tid]["home_adv"] = e.get("home_adv", 0.0)
    except Exception as ex:
        print(f"[dynasty_game] 시설 효과 skip: {ex}")

    return teams, rosters, mods


# =========================================
# 공용 헬퍼
# =========================================
def _game_row(g, season, hs, as_):
    return {
        "id": g["id"], "save_id": g["save_id"], "season": season,
        "week": g["week"], "home_team": g["home_team"], "away_team": g["away_team"],
        "home_score": hs, "away_score": as_, "played": True,
    }


def _apply_result(home, away, hs, as_):
    if hs > as_:
        home["wins"] += 1
        away["losses"] += 1
    elif as_ > hs:
        away["wins"] += 1
        home["losses"] += 1
    else:
        home["ties"] += 1
        away["ties"] += 1


def _upsert_teams(sb, teams):
    rows = []
    for t in teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        rows.append(row)
    sb.table("dynasty_team").upsert(rows).execute()


def _ensure(acc, p, team_id):
    if p["id"] not in acc:
        acc[p["id"]] = {
            "team_id": team_id, "games": 0, "hits": 0, "hr": 0,
            "rbi": 0, "sb": 0, "wins": 0, "losses": 0, "saves": 0, "so": 0,
        }
    return acc[p["id"]]

# dynasty_game.py - Part2
# =========================================
# 정밀 모드: 타석 단위 엔진
# =========================================

# =========================================
# 타석 판정
# 타자(contact/power/eye) vs 투수(stuff/control) + 피로도
# return: "K" | "BB" | "OUT" | "1B" | "2B" | "3B" | "HR"
# =========================================
def _plate_appearance(batter, pitcher, fatigue, bat_mod=0.0):
    contact = (batter["contact"] or 40) * (1 + bat_mod)
    power = batter["power"] or 40
    eye = batter["eye"] or 40
    stuff = (pitcher["stuff"] or 40) * (1 - fatigue)
    control = (pitcher["control"] or 40) * (1 - fatigue)

    # 삼진: 구위 vs 컨택
    k_prob = 0.16 + (stuff - contact) * 0.0028
    k_prob = max(0.05, min(0.42, k_prob))
    r = random.random()
    if r < k_prob:
        return "K"
    r -= k_prob

    # 볼넷: 선구 vs 제구
    bb_prob = 0.085 + (eye - control) * 0.0022
    bb_prob = max(0.03, min(0.22, bb_prob))
    if r < bb_prob:
        return "BB"
    r -= bb_prob

    # 인플레이 안타율: 컨택 vs 구위
    hit_prob = 0.225 + (contact - stuff) * 0.0025
    hit_prob = max(0.12, min(0.38, hit_prob))
    if r >= hit_prob:
        return "OUT"

    # 안타 종류: 파워 기반
    hr_share = max(0.02, min(0.25, 0.03 + (power - 50) * 0.004))
    r2 = random.random()
    if r2 < hr_share:
        return "HR"
    if r2 < hr_share + 0.05:
        return "3B" if (batter["speed"] or 40) >= 65 else "2B"
    if r2 < hr_share + 0.25:
        return "2B"
    return "1B"


# =========================================
# 이닝 진행 (한 팀 공격)
# state: {"order": 타순 인덱스}
# return: 득점
# =========================================
def _play_inning(batters, pitcher, fatigue, state, acc, team_id, bat_mod):
    outs = 0
    bases = [None, None, None]  # 1루, 2루, 3루
    runs = 0

    while outs < 3:
        batter = batters[state["order"] % len(batters)]
        state["order"] += 1

        result = _plate_appearance(batter, pitcher, fatigue, bat_mod)
        bs = acc.get(batter["id"])

        if result == "K":
            outs += 1
            ps = acc.get(pitcher["id"])
            if ps:
                ps["so"] += 1

        elif result == "OUT":
            outs += 1
            # 진루타: 3루 주자 20% 득점
            if outs < 3 and bases[2] and random.random() < 0.2:
                runs += 1
                if bs:
                    bs["rbi"] += 1
                bases[2] = None

        elif result == "BB":
            # 강제 진루 (밀어내기 포함)
            if bases[0]:
                if bases[1]:
                    if bases[2]:
                        runs += 1
                        if bs:
                            bs["rbi"] += 1
                    bases[2] = bases[1]
                bases[1] = bases[0]
            bases[0] = batter

        else:
            advance = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}[result]
            if bs:
                bs["hits"] += 1
                if result == "HR":
                    bs["hr"] += 1

            # 주자 진루 (3루부터)
            for base_idx in (2, 1, 0):
                runner = bases[base_idx]
                if runner is None:
                    continue
                new_idx = base_idx + advance
                # 1루타에 2루 주자 홈 쇄도 60%
                if result == "1B" and base_idx == 1 and random.random() < 0.6:
                    new_idx = 4
                bases[base_idx] = None
                if new_idx >= 3:
                    runs += 1
                    if bs:
                        bs["rbi"] += 1
                else:
                    bases[new_idx] = runner

            # 타자 진루
            if advance >= 4:
                runs += 1
                if bs:
                    bs["rbi"] += 1
            else:
                bases[advance - 1] = batter

        # 도루 시도: 1루 주자, 2루 비어있음, 빠른 발
        if bases[0] and not bases[1]:
            spd = bases[0]["speed"] or 40
            if spd >= 62 and random.random() < (spd - 55) / 250:
                if random.random() < 0.72:
                    runner = bases[0]
                    bases[1] = runner
                    bases[0] = None
                    rs = acc.get(runner["id"])
                    if rs:
                        rs["sb"] += 1
                else:
                    bases[0] = None
                    outs += 1

    return runs


# =========================================
# 경기 본체 (9이닝 + 연장 12회, 이후 무승부)
# =========================================
def _play_game(home, away, home_mod, away_mod, week, acc, home_id, away_id):
    # 로스터 없는 팀 방어
    if not home or not home["batters"] or not away or not away["batters"]:
        return random.randint(0, 5), random.randint(0, 5)

    home_bat_mod = home_mod.get("sim", 0.0) + 0.02 + home_mod.get("home_adv", 0.0)
    away_bat_mod = away_mod.get("sim", 0.0)

    # 선발 로테이션
    h_sp = home["sps"][week % len(home["sps"])] if home["sps"] else home["batters"][0]
    a_sp = away["sps"][week % len(away["sps"])] if away["sps"] else away["batters"][0]

    # 출장 기록
    for p in home["batters"]:
        _ensure(acc, p, home_id)["games"] += 1
    _ensure(acc, h_sp, home_id)["games"] += 1
    for p in away["batters"]:
        _ensure(acc, p, away_id)["games"] += 1
    _ensure(acc, a_sp, away_id)["games"] += 1

    h_state = {"order": 0}
    a_state = {"order": 0}
    h_score = a_score = 0

    h_pit = {"p": h_sp, "outs": 0, "used_cp": False}
    a_pit = {"p": a_sp, "outs": 0, "used_cp": False}

    def current_pitcher(pit, team, team_id_, lead, inning):
        """피로/상황에 따라 투수 교체. return (투수, 피로도)"""
        stamina = pit["p"]["stamina"] or 50
        max_outs = int(12 + stamina * 0.21)  # 체력 50 → 약 7.5이닝

        # 9회 세이브 상황(1~3점 리드) → 마무리
        if inning >= 9 and 0 < lead <= 3 and team["cp"] and not pit["used_cp"]:
            pit["p"] = team["cp"]
            pit["outs"] = 0
            pit["used_cp"] = True
            _ensure(acc, pit["p"], team_id_)
            return pit["p"], 0.0

        # 선발 소진 → 불펜 순차 투입
        if pit["outs"] >= max_outs and team["rps"]:
            idx = min(len(team["rps"]) - 1, (pit["outs"] - max_outs) // 6)
            new_p = team["rps"][idx]
            if new_p["id"] != pit["p"]["id"]:
                pit["p"] = new_p
                _ensure(acc, new_p, team_id_)

        fatigue = max(0.0, (pit["outs"] - max_outs * 0.7) / 60)
        return pit["p"], min(0.25, fatigue)

    inning = 1
    while True:
        # 초: 원정 공격 (홈 투수)
        p, fat = current_pitcher(h_pit, home, home_id, h_score - a_score, inning)
        _ensure(acc, p, home_id)
        a_score += _play_inning(away["batters"], p, fat, a_state, acc, away_id, away_bat_mod)
        h_pit["outs"] += 3

        # 말: 홈 공격 (9회 말 리드 시 생략)
        if not (inning >= 9 and h_score > a_score):
            p, fat = current_pitcher(a_pit, away, away_id, a_score - h_score, inning)
            _ensure(acc, p, away_id)
            h_score += _play_inning(home["batters"], p, fat, h_state, acc, home_id, home_bat_mod)
            a_pit["outs"] += 3

        if inning >= 9 and h_score != a_score:
            break
        if inning >= 12:
            break  # 무승부
        inning += 1

    # ----- 승/패/세이브 판정 -----
    if h_score != a_score:
        if h_score > a_score:
            w_team, w_id, w_pit, w_sp = home, home_id, h_pit, h_sp
            l_team, l_id, l_pit, l_sp = away, away_id, a_pit, a_sp
        else:
            w_team, w_id, w_pit, w_sp = away, away_id, a_pit, a_sp
            l_team, l_id, l_pit, l_sp = home, home_id, h_pit, h_sp

        w_pitcher = w_sp if random.random() < 0.65 else w_pit["p"]
        _ensure(acc, w_pitcher, w_id)["wins"] += 1

        l_pitcher = l_sp if random.random() < 0.7 else l_pit["p"]
        _ensure(acc, l_pitcher, l_id)["losses"] += 1

        # 세이브: 마무리 등판 + 3점차 이내 승리
        if w_pit["used_cp"] and abs(h_score - a_score) <= 3 and w_team["cp"]:
            _ensure(acc, w_team["cp"], w_id)["saves"] += 1

    return h_score, a_score

# dynasty_game.py - Part3
# =========================================
# 빠른 모드: 전력 기반 자동 시뮬 + 근사 기록 생성
# =========================================

# =========================================
# 팀 전력 계산 (빠른 모드용)
# =========================================
def _calc_power(roster, mod):
    if not roster or not roster["batters"]:
        return {"bat": 50.0, "pit": 50.0, "home_adv": 0.0}

    bat = sum(p["overall"] for p in roster["batters"]) / len(roster["batters"])

    sp = [p["overall"] for p in roster["sps"]]
    bp = [p["overall"] for p in roster["rps"]]
    if roster["cp"]:
        bp.append(roster["cp"]["overall"])

    sp_avg = sum(sp) / len(sp) if sp else 50.0
    bp_avg = sum(bp) / len(bp) if bp else 50.0

    boost = 1 + mod.get("sim", 0.0)
    return {
        "bat": bat * boost,
        "pit": (sp_avg * 0.6 + bp_avg * 0.4) * boost,
        "home_adv": mod.get("home_adv", 0.0),
    }


# =========================================
# 빠른 경기 (기대 득점 → 랜덤)
# =========================================
def _fast_game(hp, ap):
    def exp_runs(bat, pit):
        return max(1.2, min(9.0, 4.5 + (bat - pit) * 0.09))

    he = exp_runs(hp["bat"], ap["pit"]) * (1.05 + hp.get("home_adv", 0.0))
    ae = exp_runs(ap["bat"], hp["pit"])

    def roll(e):
        runs = 0
        rem = e
        while rem > 0:
            if random.random() < min(rem, 1.0) * 0.75:
                runs += 1
            rem -= 1.0
        if random.random() < 0.12:
            runs += random.randint(1, 4)
        return runs

    hs, as_ = roll(he), roll(ae)
    if hs == as_ and random.random() < 0.85:
        if random.random() < he / (he + ae):
            hs += 1
        else:
            as_ += 1
    return hs, as_


# =========================================
# 빠른 모드 근사 기록 생성
# =========================================
def _fast_record(acc, rosters, home_id, away_id, hs, as_, week):
    for tid, runs, opp_runs in ((home_id, hs, as_), (away_id, as_, hs)):
        team = rosters.get(tid)
        if not team or not team["batters"]:
            continue

        batters = team["batters"]
        weights = [max(20, p["contact"] or 50) for p in batters]

        for p in batters:
            _ensure(acc, p, tid)["games"] += 1

        for _ in range(max(2, int(runs * 1.8))):
            p = random.choices(batters, weights=weights)[0]
            acc[p["id"]]["hits"] += 1

        for _ in range(runs):
            if random.random() < 0.22:
                pw = [max(10, (p["power"] or 50) - 30) ** 2 for p in batters]
                p = random.choices(batters, weights=pw)[0]
                acc[p["id"]]["hr"] += 1
            p = random.choices(batters, weights=weights)[0]
            acc[p["id"]]["rbi"] += 1

        for p in batters:
            spd = p["speed"] or 40
            if spd >= 60 and random.random() < (spd - 55) / 200:
                acc[p["id"]]["sb"] += 1

        sp = team["sps"][week % len(team["sps"])] if team["sps"] else None
        if sp:
            s = _ensure(acc, sp, tid)
            s["games"] += 1
            s["so"] += max(1, int(random.gauss(3 + (sp["stuff"] or 50) / 15, 1.5)))
            if runs > opp_runs and random.random() < 0.65:
                s["wins"] += 1
            elif runs < opp_runs and random.random() < 0.7:
                s["losses"] += 1

        if (
            team["cp"] and runs > opp_runs
            and abs(runs - opp_runs) <= 3 and random.random() < 0.75
        ):
            c = _ensure(acc, team["cp"], tid)
            c["games"] += 1
            c["saves"] += 1
