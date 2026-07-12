# dynasty_award.py
# =========================================
# KBO Dynasty - Phase 8: 시즌 어워드
# MVP: 종합 점수(공격+투구) 1위
# 신인왕(ROY): 1년차 중 종합 점수 1위
# 골든글러브 타자(GG_BAT): 타격 점수 1위
# 골든글러브 투수(GG_PIT): 투구 점수 1위
# 홈런왕 / 다승왕 / 세이브왕
# =========================================

from dynasty_utils import get_supabase

AWARD_KR = {
    "MVP": "정규시즌 MVP",
    "ROY": "신인왕",
    "GG_BAT": "골든글러브 (타자)",
    "GG_PIT": "골든글러브 (투수)",
    "HR_KING": "홈런왕",
    "WIN_KING": "다승왕",
    "SV_KING": "세이브왕",
}


def _bat_score(r):
    return r["hits"] * 1.0 + r["hr"] * 4.0 + r["rbi"] * 1.2 + r["sb"] * 1.5


def _pit_score(r):
    return r["wins"] * 5.0 + r["saves"] * 3.5 + r["so"] * 0.3 - r["losses"] * 2.0


def _total_score(r):
    return _bat_score(r) + _pit_score(r)


# =========================================
# 시즌 어워드 선정 (next_season에서 호출, 성적 리셋 전)
# =========================================
def grant_awards(save_id):
    sb = get_supabase()

    save = (
        sb.table("dynasty_save")
        .select("season")
        .eq("id", save_id)
        .execute()
        .data[0]
    )
    season = save["season"]

    # 중복 방지
    existing = (
        sb.table("dynasty_award")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .eq("season", season)
        .execute()
        .count
    )
    if existing and existing > 0:
        return 0

    stats = (
        sb.table("dynasty_player_stats")
        .select("*, dynasty_player(name, positions, appear_season)")
        .eq("save_id", save_id)
        .eq("season", season)
        .execute()
        .data
    )
    if not stats:
        print("[dynasty_award] 기록 없음 → 시상 skip")
        return 0

    teams = (
        sb.table("dynasty_team")
        .select("id, team_name")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_names = {t["id"]: t["team_name"] for t in teams}

    winners = []

    def add(award, r, detail):
        p = r["dynasty_player"]
        winners.append(
            {
                "save_id": save_id,
                "season": season,
                "award": award,
                "player_id": r["player_id"],
                "player_name": p["name"],
                "team_id": r["team_id"],
                "team_name": team_names.get(r["team_id"], ""),
                "detail": detail,
            }
        )

    # MVP
    mvp = max(stats, key=_total_score)
    add("MVP", mvp, _summary(mvp))

    # 신인왕 (1년차)
    rookies = [
        r for r in stats
        if r["dynasty_player"]["appear_season"] == season and r["games"] > 0
    ]
    if rookies:
        roy = max(rookies, key=_total_score)
        add("ROY", roy, _summary(roy))

    # 골든글러브 타자/투수
    batters = [r for r in stats if "P" not in (r["dynasty_player"]["positions"] or "")]
    pitchers = [r for r in stats if "P" in (r["dynasty_player"]["positions"] or "")]
    if batters:
        gb = max(batters, key=_bat_score)
        add("GG_BAT", gb, _summary(gb))
    if pitchers:
        gp = max(pitchers, key=_pit_score)
        add("GG_PIT", gp, _summary(gp))

    # 타이틀 홀더
    hr_king = max(stats, key=lambda r: r["hr"])
    if hr_king["hr"] > 0:
        add("HR_KING", hr_king, f"{hr_king['hr']}홈런")

    win_king = max(stats, key=lambda r: r["wins"])
    if win_king["wins"] > 0:
        add("WIN_KING", win_king, f"{win_king['wins']}승")

    sv_king = max(stats, key=lambda r: r["saves"])
    if sv_king["saves"] > 0:
        add("SV_KING", sv_king, f"{sv_king['saves']}세이브")

    sb.table("dynasty_award").insert(winners).execute()

    # 주요상 뉴스
    try:
        from dynasty_event import log_events
        news = [
            {"season": season, "week": 99, "type": "award", "icon": "🎖",
             "message": f"S{season} {AWARD_KR[w['award']]}: {w['team_name']} {w['player_name']} ({w['detail']})"}
            for w in winners if w["award"] in ("MVP", "ROY", "HR_KING")
        ]
        log_events(save_id, news)
    except Exception:
        pass

    print(f"[dynasty_award] S{season} 시상={len(winners)}건")
    return len(winners)


def _summary(r):
    p = r["dynasty_player"]
    if "P" in (p["positions"] or ""):
        return f"{r['wins']}승 {r['losses']}패 {r['saves']}세이브 {r['so']}K"
    return f"{r['hits']}안타 {r['hr']}홈런 {r['rbi']}타점 {r['sb']}도루"


# =========================================
# 시즌별 수상자 조회 (역사 화면용)
# =========================================
def get_awards(save_id, season=None):
    sb = get_supabase()
    q = (
        sb.table("dynasty_award")
        .select("*")
        .eq("save_id", save_id)
        .order("season", desc=True)
    )
    if season is not None:
        q = q.eq("season", season)
    rows = q.execute().data
    for r in rows:
        r["award_kr"] = AWARD_KR.get(r["award"], r["award"])
    return rows
