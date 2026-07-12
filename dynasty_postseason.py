# dynasty_postseason.py
# =========================================
# KBO Dynasty - Phase 7: 포스트시즌
# WC(3판, 4위 1승 선취) → SEMI(5판) → PO(5판) → KS(7판)
# 시드: 정규시즌 1~5위. 상위 시드 = team_a (홈 어드밴티지)
# =========================================

from dynasty_utils import get_supabase, get_standings
from dynasty_game import _load_teams_and_powers, _simulate_game

ROUND_ORDER = ["WC", "SEMI", "PO", "KS"]
ROUND_KR = {"WC": "와일드카드", "SEMI": "준플레이오프", "PO": "플레이오프", "KS": "한국시리즈"}
ROUND_WINS = {"WC": 2, "SEMI": 3, "PO": 3, "KS": 4}  # 시리즈 승리 필요 승수


# =========================================
# 포스트시즌 시작 (없으면 WC 생성)
# =========================================
def ensure_postseason(save_id, season):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_postseason")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .eq("season", season)
        .execute()
        .count
    )
    if existing and existing > 0:
        return

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    standings = get_standings(teams)
    seeds = [t["id"] for t in standings[:5]]  # 1~5위

    # WC: 4위(team_a, 1승 선취) vs 5위
    sb.table("dynasty_postseason").insert(
        {
            "save_id": save_id, "season": season, "round": "WC",
            "team_a": seeds[3], "team_b": seeds[4],
            "wins_a": 1, "wins_b": 0, "finished": False,
        }
    ).execute()

    print(f"[dynasty_postseason] S{season} 포스트시즌 시작")


# =========================================
# 전체 시리즈 조회
# =========================================
def get_series_list(save_id, season):
    sb = get_supabase()
    rows = (
        sb.table("dynasty_postseason")
        .select("*")
        .eq("save_id", save_id)
        .eq("season", season)
        .execute()
        .data
    )
    rows.sort(key=lambda r: ROUND_ORDER.index(r["round"]))
    return rows


# =========================================
# 다음 경기 1개 진행
# return: (결과 dict | None, 완료 여부)
# =========================================
def play_next_game(save_id, season):
    sb = get_supabase()

    series_list = get_series_list(save_id, season)
    current = next((s for s in series_list if not s["finished"]), None)

    if current is None:
        return None, True

    teams, powers = _load_teams_and_powers(sb, save_id)
    team_map = {t["id"]: t for t in teams}

    a_id, b_id = current["team_a"], current["team_b"]
    pa = powers.get(a_id, {"bat": 50.0, "pit": 50.0})
    pb = powers.get(b_id, {"bat": 50.0, "pit": 50.0})

    # 홈 어드밴티지: 상위 시드(team_a) 기준, 무승부 재경기
    while True:
        sa, sb_score = _simulate_game(pa, pb)
        if sa != sb_score:
            break

    wins_a = current["wins_a"] + (1 if sa > sb_score else 0)
    wins_b = current["wins_b"] + (1 if sb_score > sa else 0)

    need = ROUND_WINS[current["round"]]
    finished = wins_a >= need or wins_b >= need
    winner = a_id if wins_a >= need else (b_id if wins_b >= need else None)

    sb.table("dynasty_postseason").update(
        {"wins_a": wins_a, "wins_b": wins_b,
         "finished": finished, "winner": winner}
    ).eq("id", current["id"]).execute()

    # 시리즈 종료 → 다음 라운드 생성 or KS 우승 확정
    if finished:
        _advance(sb, save_id, season, current["round"], winner, team_map)

    result = {
        "round": current["round"],
        "round_kr": ROUND_KR[current["round"]],
        "team_a": team_map[a_id],
        "team_b": team_map[b_id],
        "score_a": sa,
        "score_b": sb_score,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "finished": finished,
        "winner": team_map[winner] if winner else None,
    }
    return result, False


def _advance(sb, save_id, season, finished_round, winner_id, team_map):
    teams = list(team_map.values())
    standings = get_standings(teams)
    seeds = [t["id"] for t in standings[:5]]

    idx = ROUND_ORDER.index(finished_round)

    if finished_round == "KS":
        sb.table("dynasty_save").update(
            {"ks_champion": winner_id}
        ).eq("id", save_id).execute()

        w = team_map[winner_id]
        try:
            from dynasty_event import log_event
            log_event(save_id, season, 99, "champion", "🏆",
                      f"Season {season} 한국시리즈 우승: {w['team_name']}!")
        except Exception:
            pass
        print(f"[dynasty_postseason] KS 우승: {w['team_name']}")
        return

    next_round = ROUND_ORDER[idx + 1]
    # 상대: SEMI→3위, PO→2위, KS→1위 (항상 상위 시드가 team_a)
    opponent = {"SEMI": seeds[2], "PO": seeds[1], "KS": seeds[0]}[next_round]

    sb.table("dynasty_postseason").insert(
        {
            "save_id": save_id, "season": season, "round": next_round,
            "team_a": opponent, "team_b": winner_id,
            "wins_a": 0, "wins_b": 0, "finished": False,
        }
    ).execute()

    print(f"[dynasty_postseason] {ROUND_KR[next_round]} 시작")


def is_postseason_done(save_id, season):
    series = get_series_list(save_id, season)
    ks = next((s for s in series if s["round"] == "KS"), None)
    return ks is not None and ks["finished"]
