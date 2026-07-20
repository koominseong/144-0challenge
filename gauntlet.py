# gauntlet.py - Part1
# =========================================
# KBO 가을야구 업셋 런 (로그라이크)
# 랜덤 연도+팀(5위 시드) → WC→준PO→PO→KS, 상대는 라운드마다 랜덤(점점 강함)
# 라운드 간 예산으로 전체 풀에서 최대 2명 영입
# =========================================

import os
import json
import glob
import random

from scout import find_data_dir  # 동일 탐색 재활용
from dynasty_import import (
    _merge_records, _is_pitcher, _batter_stats, _pitcher_stats,
    _calc_overall, _positions_str,
)

BASE_BUDGET = 500
MAX_SIGNINGS_PER_ROUND = 2

# 라운드 정의: (코드, 이름, 상대 시드, 시리즈 승수, 내 어드밴티지 승)
STAGES = [
    ("WC",   "와일드카드",   4, 2, 0),   # 상대가 1승 어드밴티지 (내가 2승 필요, 상대 1승)
    ("SPO",  "준플레이오프", 3, 3, 0),
    ("PO",   "플레이오프",   2, 3, 0),
    ("KS",   "한국시리즈",   1, 4, 0),
]

# 상대 전력 필터: 시드별 팀 WAR 총합 백분위 (강한 시드일수록 상위 표본)
SEED_WAR_PCT = {4: (0.35, 0.75), 3: (0.55, 0.85), 2: (0.70, 0.95), 1: (0.85, 1.00)}


# =========================================
# 데이터 로드: (연도, 팀) 목록과 팀 로스터
# =========================================
def list_year_teams():
    """[(year, team_filename_prefix, path)] 전체"""
    data_dir = find_data_dir()
    if not data_dir:
        return []
    out = []
    for f in glob.glob(os.path.join(data_dir, "*.json")):
        base = os.path.basename(f).replace(".json", "")
        if "_" not in base:
            continue
        team, year = base.rsplit("_", 1)
        if year.isdigit():
            out.append((year, team, f))
    return out


def load_team_players(path):
    try:
        with open(path, encoding="utf-8") as fp:
            rows = json.load(fp)
    except Exception:
        return []
    return rows if isinstance(rows, list) else []


# =========================================
# 원본 레코드 → 게임 선수 dict (dynasty_import 변환 재활용)
# id는 런 내부 일련번호
# =========================================
def build_player(rec, pid, rng):
    merged = _merge_records([rec])
    is_p = _is_pitcher(merged)
    stats = _pitcher_stats(merged, rng) if is_p else _batter_stats(merged, rng)
    overall = _calc_overall(stats, is_p)
    return {
        "id": pid,
        "name": merged["name"],
        "team_kr": rec.get("team_kr") or merged["team"],
        "year": rec.get("Year"),
        "positions": _positions_str(merged, is_p),
        "overall": overall,
        "war": round(float(rec.get("war") or 0), 2),
        "contact": stats["contact"], "power": stats["power"], "eye": stats["eye"],
        "speed": stats["speed"], "defense": stats["defense"], "arm": stats["arm"],
        "stuff": stats["stuff"], "control": stats["control"], "stamina": stats["stamina"],
        "is_pitcher": is_p,
        "price": max(60, int(80 + (float(rec.get("war") or 0)) * 90)),
    }


def build_team(path, rng, id_start=0, min_size=28):
    recs = [r for r in load_team_players(path)
            if isinstance(r, dict) and r.get("name")
            and ((r.get("PA") or 0) >= 10 or (r.get("IP") or 0) >= 5)]
    players = []
    pid = id_start
    seen = set()
    for r in recs:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        players.append(build_player(r, pid, rng))
        pid += 1
    return players, pid


def team_war(path):
    return sum(float(r.get("war") or 0) for r in load_team_players(path)
               if isinstance(r, dict))


# =========================================
# 런 생성: 내 팀 완전 랜덤 + 4개 라운드 상대 예약 (시드 강도별)
# =========================================
def create_run():
    yt = list_year_teams()
    if not yt:
        return None

    rng = random.Random()

    # 내 팀: 완전 랜덤 (인원 충분한 팀만)
    random.shuffle(yt)
    my = None
    for year, team, path in yt:
        if len(load_team_players(path)) >= 20:
            my = (year, team, path)
            break
    if not my:
        return None

    # 전체 팀 WAR 순위 (상대 추출용)
    ranked = sorted(
        ((year, team, path, team_war(path)) for (year, team, path) in yt
         if len(load_team_players(path)) >= 20),
        key=lambda x: x[3],
    )
    n = len(ranked)

    def pick_opponent(seed, exclude):
        lo, hi = SEED_WAR_PCT[seed]
        band = ranked[int(n * lo): max(int(n * lo) + 1, int(n * hi))]
        band = [b for b in band if (b[0], b[1]) not in exclude]
        return random.choice(band) if band else random.choice(ranked)

    exclude = {(my[0], my[1])}
    opponents = []
    for code, name, seed, wins_needed, _adv in STAGES:
        opp = pick_opponent(seed, exclude)
        exclude.add((opp[0], opp[1]))
        opponents.append({
            "stage": code, "stage_name": name, "seed": seed,
            "year": opp[0], "team": opp[1], "path_key": f"{opp[1]}_{opp[0]}",
            "label": f"{opp[0]} {opp[2] and ''}{_team_label(opp[1], opp[2])}",
            "war": round(opp[3], 1),
            "wins_needed": wins_needed,
        })

    # 내 로스터 생성
    players, next_id = build_team(my[2], rng)
    my_label = f"{my[0]} {_team_label(my[1], my[2])}"

    # 감독 후보 3명 (dynasty_staff 풀 재활용)
    from dynasty_staff import MANAGER_POOL, STYLE_DESC
    mgr_cands = random.sample(MANAGER_POOL, 3)
    managers = [{"name": m[0], "grade": m[1], "style": m[2],
                 "style_desc": STYLE_DESC.get(m[2], "")} for m in mgr_cands]

    state = {
        "my_label": my_label,
        "my_year": my[0], "my_team": my[1],
        "players": players,           # 전체 명단 (엔트리 밖 포함)
        "next_pid": next_id,
        "entry": [],                  # 28인 pid 목록 (편성 화면에서 확정)
        "lineup": [],                 # 타순 9 pid
        "rotation": [],               # 선발 pid 목록 (경기별 사용)
        "closer": None,
        "manager": None,
        "manager_cands": managers,
        "stage_idx": 0,               # 현재 라운드 (STAGES 인덱스)
        "opponents": opponents,
        "series": None,               # 진행 중 시리즈 상태
        "budget": BASE_BUDGET,
        "spent": 0,
        "signings": [],
        "history": [],                # 라운드별 결과 요약
        "phase": "manager_select",    # manager_select → entry → market/series...
        "done": False,
        "result": None,
    }
    return state


def _team_label(team_en, path_or_war):
    """파일명 영문 팀명 → 첫 레코드의 team_kr 시도, 실패 시 영문"""
    if isinstance(path_or_war, str) and os.path.isfile(path_or_war):
        rows = load_team_players(path_or_war)
        if rows and rows[0].get("team_kr"):
            return rows[0]["team_kr"]
    return team_en


# =========================================
# 엔트리 자동 추천: OVR순 타자 15 + 투수 13
# 타순/로테/마무리 추천 포함
# =========================================
def suggest_entry(state):
    players = state["players"]
    bats = sorted([p for p in players if not p["is_pitcher"]],
                  key=lambda p: -p["overall"])
    pits = sorted([p for p in players if p["is_pitcher"]],
                  key=lambda p: -p["overall"])

    entry_b = bats[:15]
    entry_p = pits[:13]
    entry = [p["id"] for p in entry_b + entry_p]

    lineup = [p["id"] for p in entry_b[:9]]
    starters = sorted(entry_p, key=lambda p: -(p["stamina"] + p["overall"]))[:4]
    rotation = [p["id"] for p in starters]
    relievers = [p for p in entry_p if p["id"] not in rotation]
    closer = max(relievers, key=lambda p: p["overall"])["id"] if relievers else None

    return {"entry": entry, "lineup": lineup, "rotation": rotation, "closer": closer}

# gauntlet.py - Part2
# =========================================
# DB 적재: 런 = 숨겨진 dynasty_save
# 내 팀 + 상대 팀(라운드마다 교체) / 경기 = dynasty_schedule row → dynasty_live 직결
# =========================================

from dynasty_utils import get_supabase
from dynasty_lineup import auto_generate_lineup


def _player_row(save_id, p):
    return {
        "save_id": save_id, "name": p["name"],
        "positions": p["positions"], "overall": p["overall"],
        "potential": p["overall"], "war": p["war"],
        "appear_season": 1, "drafted": True, "retired": False,
        "contact": p["contact"], "power": p["power"], "eye": p["eye"],
        "speed": p["speed"], "defense": p["defense"], "arm": p["arm"],
        "stuff": p["stuff"], "control": p["control"], "stamina": p["stamina"],
    }


# =========================================
# 런 DB 초기화: save + 팀 2개 + 내 선수 insert
# state를 받아 DB id들을 채워 반환
# =========================================
def init_run_db(state):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .insert({
            "team_name": state["my_label"], "logo": "🍂", "color": "#6d4c41",
            "stadium": "가을구장", "season": 1, "week": 0,
            "finished": False, "is_gauntlet": True,
        })
        .execute().data[0]
    )
    save_id = save["id"]

    my_team = (
        sb.table("dynasty_team")
        .insert({
            "save_id": save_id, "team_name": state["my_label"],
            "logo": "🍂", "color": "#6d4c41", "stadium": "가을구장",
            "is_user": True, "wins": 0, "losses": 0, "ties": 0,
            "budget": 0, "fans": 50000,
        })
        .execute().data[0]
    )
    opp_team = (
        sb.table("dynasty_team")
        .insert({
            "save_id": save_id, "team_name": "상대 미정",
            "logo": "⚾", "color": "#37474f", "stadium": "상대구장",
            "is_user": False, "wins": 0, "losses": 0, "ties": 0,
            "budget": 0, "fans": 50000,
        })
        .execute().data[0]
    )

    # 내 선수 insert → DB id 매핑
    rows = [_player_row(save_id, p) for p in state["players"]]
    inserted = []
    for i in range(0, len(rows), 100):
        inserted += sb.table("dynasty_player").insert(rows[i:i + 100]).execute().data
    for p, dbrow in zip(state["players"], inserted):
        p["db_id"] = dbrow["id"]

    state["save_id"] = save_id
    state["my_team_id"] = my_team["id"]
    state["opp_team_id"] = opp_team["id"]
    return state


# =========================================
# 엔트리 확정 → dynasty_roster 구성
# entry_pids: 28인 / lineup_pids: 타순9 / rotation_pids / closer_pid
# =========================================
def apply_entry(state, entry_pids, lineup_pids, rotation_pids, closer_pid):
    sb = get_supabase()
    save_id = state["save_id"]
    tid = state["my_team_id"]
    pmap = {p["id"]: p for p in state["players"]}

    # 기존 내 로스터 제거 (재편성 대응)
    sb.table("dynasty_roster").delete().eq("save_id", save_id).eq("team_id", tid).execute()

    rows = []
    entry_set = set(entry_pids)
    lineup_set = set(lineup_pids)
    rot_set = set(rotation_pids)

    for depth, pid in enumerate(lineup_pids):
        rows.append({"save_id": save_id, "team_id": tid,
                     "player_id": pmap[pid]["db_id"], "role": "START", "depth": depth})
    for depth, pid in enumerate(rotation_pids):
        rows.append({"save_id": save_id, "team_id": tid,
                     "player_id": pmap[pid]["db_id"], "role": "SP", "depth": depth})
    if closer_pid:
        rows.append({"save_id": save_id, "team_id": tid,
                     "player_id": pmap[closer_pid]["db_id"], "role": "CP", "depth": 0})
    for pid in entry_pids:
        if pid in lineup_set or pid in rot_set or pid == closer_pid:
            continue
        p = pmap[pid]
        role = "RP" if p["is_pitcher"] else "BENCH"
        rows.append({"save_id": save_id, "team_id": tid,
                     "player_id": p["db_id"], "role": role, "depth": 50})
    # 엔트리 밖 = MINOR
    for p in state["players"]:
        if p["id"] not in entry_set:
            rows.append({"save_id": save_id, "team_id": tid,
                         "player_id": p["db_id"], "role": "MINOR", "depth": 99})

    for i in range(0, len(rows), 100):
        sb.table("dynasty_roster").insert(rows[i:i + 100]).execute()

    state["entry"] = entry_pids
    state["lineup"] = lineup_pids
    state["rotation"] = rotation_pids
    state["closer"] = closer_pid
    return state


# =========================================
# 스테이지 시작: 상대 로스터 적재 + 시리즈 상태 + 1차전 스케줄
# =========================================
def start_stage(state):
    sb = get_supabase()
    save_id = state["save_id"]
    opp_tid = state["opp_team_id"]
    stage = STAGES[state["stage_idx"]]
    opp = state["opponents"][state["stage_idx"]]

    # 이전 상대 선수/로스터 제거
    old = (sb.table("dynasty_roster").select("player_id")
           .eq("save_id", save_id).eq("team_id", opp_tid).execute().data)
    sb.table("dynasty_roster").delete().eq("save_id", save_id).eq("team_id", opp_tid).execute()
    if old:
        ids = [r["player_id"] for r in old]
        for i in range(0, len(ids), 100):
            sb.table("dynasty_player").delete().in_("id", ids[i:i + 100]).execute()

    # 팀 정보 갱신
    sb.table("dynasty_team").update({
        "team_name": f"{opp['year']} {opp.get('label') or opp['team']}",
        "logo": "🔥", "wins": 0, "losses": 0, "ties": 0,
    }).eq("id", opp_tid).execute()
    sb.table("dynasty_team").update({"wins": 0, "losses": 0, "ties": 0}).eq("id", state["my_team_id"]).execute()

    # 상대 선수 로드/insert
    data_dir = find_data_dir()
    path = os.path.join(data_dir, f"{opp['path_key']}.json")
    rng = random.Random()
    opp_players, _ = build_team(path, rng, id_start=100000)
    rows = [_player_row(save_id, p) for p in opp_players]
    inserted = []
    for i in range(0, len(rows), 100):
        inserted += sb.table("dynasty_player").insert(rows[i:i + 100]).execute().data
    for p, dbrow in zip(opp_players, inserted):
        p["db_id"] = dbrow["id"]

    # 상대 로스터: 자동 편성 (suggest와 같은 규칙)
    bats = sorted([p for p in opp_players if not p["is_pitcher"]], key=lambda p: -p["overall"])
    pits = sorted([p for p in opp_players if p["is_pitcher"]], key=lambda p: -p["overall"])
    rrows = []
    for depth, p in enumerate(bats[:9]):
        rrows.append({"save_id": save_id, "team_id": opp_tid,
                      "player_id": p["db_id"], "role": "START", "depth": depth})
    sps = sorted(pits, key=lambda p: -(p["stamina"] + p["overall"]))[:4]
    sp_ids = {p["id"] for p in sps}
    for depth, p in enumerate(sps):
        rrows.append({"save_id": save_id, "team_id": opp_tid,
                      "player_id": p["db_id"], "role": "SP", "depth": depth})
    rels = [p for p in pits if p["id"] not in sp_ids]
    if rels:
        cp = max(rels, key=lambda p: p["overall"])
        rrows.append({"save_id": save_id, "team_id": opp_tid,
                      "player_id": cp["db_id"], "role": "CP", "depth": 0})
        for p in rels:
            if p["id"] != cp["id"]:
                rrows.append({"save_id": save_id, "team_id": opp_tid,
                              "player_id": p["db_id"], "role": "RP", "depth": 50})
    for p in bats[9:]:
        rrows.append({"save_id": save_id, "team_id": opp_tid,
                      "player_id": p["db_id"], "role": "BENCH", "depth": 60})
    for i in range(0, len(rrows), 100):
        sb.table("dynasty_roster").insert(rrows[i:i + 100]).execute()

    # 시리즈 상태
    code, name, seed, wins_needed, _ = stage
    state["series"] = {
        "stage": code, "stage_name": name,
        "opp_label": f"{opp['year']} {opp.get('label') or opp['team']}",
        "wins_needed": wins_needed,
        "opp_wins_needed": wins_needed if code != "WC" else 1,  # WC: 상대 1승이면 탈락
        "my_wins": 0, "opp_wins": 0,
        "game_no": 0, "current_schedule_id": None,
        "log": [],
    }
    return next_game(state)


# =========================================
# 다음 경기 스케줄 생성 → live 진입용 schedule_id 반환
# 홈/원정: 하위 시드(나)는 1·2차전 원정 규칙 단순화 — 홀수 경기 상대 홈
# =========================================
def next_game(state):
    sb = get_supabase()
    sr = state["series"]
    sr["game_no"] += 1
    home_is_opp = (sr["game_no"] % 2 == 1)
    g = (
        sb.table("dynasty_schedule")
        .insert({
            "save_id": state["save_id"], "season": 1, "week": sr["game_no"],
            "home_team": state["opp_team_id"] if home_is_opp else state["my_team_id"],
            "away_team": state["my_team_id"] if home_is_opp else state["opp_team_id"],
            "played": False,
        })
        .execute().data[0]
    )
    sr["current_schedule_id"] = g["id"]
    return state

# gauntlet.py - Part3
# =========================================
# 경기 결과 회수 / 시리즈 판정 / 예산 정산 / 마켓 / 런 종료
# =========================================


# =========================================
# 경기 결과 회수: live 종료 후 복귀 시 호출
# return: "playing"(미종료) | "series_go"(다음 경기) | "stage_clear" | "eliminated"
# =========================================
def collect_game(state):
    sb = get_supabase()
    sr = state["series"]
    if not sr or not sr.get("current_schedule_id"):
        return "playing"

    g = (
        sb.table("dynasty_schedule").select("*")
        .eq("id", sr["current_schedule_id"]).execute().data
    )
    if not g or not g[0]["played"]:
        return "playing"
    g = g[0]

    my_id = state["my_team_id"]
    my_score = g["home_score"] if g["home_team"] == my_id else g["away_score"]
    opp_score = g["away_score"] if g["home_team"] == my_id else g["home_score"]

    # 무승부는 재경기 취급 (기록만 남기고 승수 미가산)
    if my_score == opp_score:
        sr["log"].append(f"{sr['game_no']}차전 {my_score}:{opp_score} 무승부 (재경기)")
        sr["current_schedule_id"] = None
        return "series_go"

    won = my_score > opp_score
    if won:
        sr["my_wins"] += 1
    else:
        sr["opp_wins"] += 1
    sr["log"].append(
        f"{sr['game_no']}차전 {'승' if won else '패'} ({my_score}:{opp_score})"
    )

    # 업적 회수 (예산 보너스용) — 이번 경기 live state의 feats
    try:
        live = (
            sb.table("dynasty_live_game").select("state")
            .eq("save_id", state["save_id"])
            .eq("schedule_id", g["id"])
            .execute().data
        )
        if live:
            feats = live[0]["state"].get("feats") or []
            sr.setdefault("feats", []).extend(feats)
    except Exception:
        pass

    sr["current_schedule_id"] = None

    if sr["my_wins"] >= sr["wins_needed"]:
        return "stage_clear"
    if sr["opp_wins"] >= sr["opp_wins_needed"]:
        return "eliminated"
    return "series_go"


# =========================================
# 스테이지 클리어: 예산 정산 → 마켓 단계로
# =========================================
def settle_stage(state):
    sr = state["series"]
    stage_code = sr["stage"]
    opp = state["opponents"][state["stage_idx"]]

    bonus = 100  # 시리즈 승리 기본
    detail = [("시리즈 승리", 100)]

    if sr["opp_wins"] == 0:
        bonus += 50
        detail.append(("스윕", 50))

    # 업셋 강도: 상대 시드 (4위 +0 ~ 1위 +90)
    upset = (4 - opp["seed"]) * 30
    if upset:
        bonus += upset
        detail.append((f"업셋 보정 ({opp['seed']}위 격파)", upset))

    feats = sr.get("feats", [])
    feat_bonus = min(100, len(feats) * 20)
    if feat_bonus:
        bonus += feat_bonus
        detail.append((f"업적 {len(feats)}건", feat_bonus))

    state["budget"] += bonus
    state["history"].append({
        "stage": sr["stage_name"], "opp": sr["opp_label"],
        "score": f"{sr['my_wins']}승 {sr['opp_wins']}패",
        "bonus": bonus, "bonus_detail": detail,
        "log": sr["log"],
    })

    state["stage_idx"] += 1
    if state["stage_idx"] >= len(STAGES):
        state["done"] = True
        state["result"] = "CLEAR"
        state["phase"] = "finished"
    else:
        state["series"] = None
        state["phase"] = "market"
    return state


def eliminate(state):
    sr = state["series"]
    state["history"].append({
        "stage": sr["stage_name"], "opp": sr["opp_label"],
        "score": f"{sr['my_wins']}승 {sr['opp_wins']}패", "bonus": 0,
        "bonus_detail": [], "log": sr["log"],
    })
    state["done"] = True
    state["result"] = f"{sr['stage_name']} 탈락"
    state["phase"] = "finished"
    return state


# =========================================
# 마켓: 전체 연도 풀에서 검색 + 영입 (라운드당 최대 2명)
# =========================================
def market_pool(state, query="", pos_filter="", limit=40):
    """이름/팀 검색. 무검색이면 랜덤 셔플 표본"""
    yt = list_year_teams()
    rng = random.Random()
    random.shuffle(yt)

    out = []
    seen = {(p["name"], p["year"]) for p in state["players"]}
    for year, team, path in yt:
        if len(out) >= limit * 3:
            break
        for r in load_team_players(path):
            if not isinstance(r, dict) or not r.get("name"):
                continue
            if (r.get("PA") or 0) < 30 and (r.get("IP") or 0) < 15:
                continue
            if query and query not in r["name"] and query not in str(r.get("team_kr") or ""):
                continue
            if (r["name"], r.get("Year")) in seen:
                continue
            p = build_player(r, -1, rng)
            if pos_filter == "P" and not p["is_pitcher"]:
                continue
            if pos_filter == "B" and p["is_pitcher"]:
                continue
            out.append(p)
    out.sort(key=lambda p: -p["war"])
    return out[:limit]


def sign_player(state, market_player, drop_pid):
    """영입 + 엔트리에서 drop_pid와 교체. market_player는 market_pool 결과의 dict"""
    sb = get_supabase()

    signed_this_round = state.get("signed_this_round", 0)
    if signed_this_round >= MAX_SIGNINGS_PER_ROUND:
        return False, f"이번 라운드 영입 한도({MAX_SIGNINGS_PER_ROUND}명)를 채웠습니다."

    price = market_player["price"]
    if state["budget"] < price:
        return False, f"예산 부족 (가격 {price} / 보유 {state['budget']})"

    if drop_pid not in state["entry"]:
        return False, "엔트리에서 제외할 선수를 선택하세요."

    # 새 pid 부여 + DB insert
    new_pid = state["next_pid"]
    state["next_pid"] += 1
    market_player = dict(market_player)
    market_player["id"] = new_pid

    row = _player_row(state["save_id"], market_player)
    dbrow = sb.table("dynasty_player").insert(row).execute().data[0]
    market_player["db_id"] = dbrow["id"]

    state["players"].append(market_player)
    state["budget"] -= price
    state["spent"] += price
    state["signed_this_round"] = signed_this_round + 1
    state["signings"].append({
        "name": market_player["name"], "year": market_player["year"],
        "team": market_player["team_kr"], "price": price,
        "stage": STAGES[state["stage_idx"]][1],
    })

    # 엔트리 교체 (라인업/로테/마무리에 있었으면 대응 교체)
    entry = [new_pid if pid == drop_pid else pid for pid in state["entry"]]
    lineup = [new_pid if pid == drop_pid else pid for pid in state["lineup"]]
    rotation = [new_pid if pid == drop_pid else pid for pid in state["rotation"]]
    closer = new_pid if state["closer"] == drop_pid else state["closer"]

    apply_entry(state, entry, lineup, rotation, closer)
    return True, f"{market_player['year']} {market_player['name']} 영입! (-{price})"


def proceed_to_stage(state):
    """마켓 종료 → 다음 스테이지 시작"""
    state["signed_this_round"] = 0
    state["phase"] = "series"
    return start_stage(state)


# =========================================
# 런 종료 기록
# =========================================
def record_run(state):
    sb = get_supabase()
    total_w = sum(int(h["score"].split("승")[0]) for h in state["history"]) if state["history"] else 0
    total_l = sum(int(h["score"].split("승 ")[1].replace("패", "")) for h in state["history"]) if state["history"] else 0
    try:
        sb.table("gauntlet_record").insert({
            "team_label": state["my_label"],
            "result": state["result"],
            "wins": total_w, "losses": total_l,
            "budget_spent": state["spent"],
            "signings": state["signings"],
        }).execute()
    except Exception as ex:
        print(f"[gauntlet] 기록 저장 skip: {ex}")

    # 숨김 save 정리 (선수/로스터/스케줄/라이브 삭제)
    sid = state.get("save_id")
    if sid:
        try:
            for tbl in ("dynasty_live_game", "dynasty_schedule", "dynasty_roster",
                        "dynasty_player", "dynasty_team", "dynasty_save"):
                key = "id" if tbl == "dynasty_save" else "save_id"
                sb.table(tbl).delete().eq(key, sid).execute()
        except Exception as ex:
            print(f"[gauntlet] save 정리 skip: {ex}")
