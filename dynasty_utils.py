# dynasty_utils.py
# =========================================
# KBO Dynasty - 공용 유틸
# Supabase 클라이언트 / AI 팀 풀 / 순위 계산 / 전력 계산
# =========================================

import os
from supabase import create_client

_supabase_client = None


# =========================================
# Supabase 클라이언트 (싱글톤)
# =========================================
def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        _supabase_client = create_client(url, key)
    return _supabase_client


# =========================================
# AI 팀 풀
# =========================================
AI_TEAM_POOL = [
    {"team_name": "서울 타이거즈", "logo": "🐯", "color": "#c0392b", "stadium": "서울 종합구장"},
    {"team_name": "부산 갈매기", "logo": "🕊️", "color": "#2980b9", "stadium": "부산 해안구장"},
    {"team_name": "인천 드래곤즈", "logo": "🐉", "color": "#8e44ad", "stadium": "인천 베이파크"},
    {"team_name": "대구 라이온스", "logo": "🦁", "color": "#16a085", "stadium": "대구 센트럴파크"},
    {"team_name": "광주 이글스", "logo": "🦅", "color": "#d35400", "stadium": "광주 챔피언스필드"},
    {"team_name": "대전 호크스", "logo": "🪶", "color": "#7f8c8d", "stadium": "대전 이글파크"},
    {"team_name": "수원 유니콘스", "logo": "🦄", "color": "#e91e63", "stadium": "수원 드림구장"},
    {"team_name": "창원 마린스", "logo": "⚓", "color": "#34495e", "stadium": "창원 마린파크"},
    {"team_name": "고양 베어스", "logo": "🐻", "color": "#795548", "stadium": "고양 포레스트필드"},
    {"team_name": "전주 피닉스", "logo": "🔥", "color": "#f39c12", "stadium": "전주 피닉스파크"},
    {"team_name": "울산 웨일즈", "logo": "🐋", "color": "#00838f", "stadium": "울산 오션구장"},
    {"team_name": "청주 썬더스", "logo": "⚡", "color": "#fbc02d", "stadium": "청주 썬더돔"},
]


# =========================================
# 순위 계산
# 승률 기준 정렬 + 게임차(GB)
# =========================================
def get_standings(teams):
    ranked = []

    for t in teams:
        wins = t["wins"]
        losses = t["losses"]
        ties = t["ties"]
        decided = wins + losses
        pct = wins / decided if decided > 0 else 0.0

        row = dict(t)
        row["pct"] = pct
        ranked.append(row)

    ranked.sort(key=lambda x: (-x["pct"], -x["wins"], x["losses"]))

    if ranked:
        top = ranked[0]
        for r in ranked:
            gb = ((top["wins"] - r["wins"]) + (r["losses"] - top["losses"])) / 2
            r["gb"] = "-" if gb <= 0 else ("%.1f" % gb).rstrip("0").rstrip(".")

    return ranked


# =========================================
# 팀 전력 간이 계산 (로스터 overall 평균)
# =========================================
def calc_team_power(sb, save_id, team_id):
    rows = (
        sb.table("dynasty_roster")
        .select("dynasty_player(overall)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .execute()
        .data
    )

    overalls = [
        r["dynasty_player"]["overall"]
        for r in rows
        if r["dynasty_player"]
    ]

    if not overalls:
        return 50.0

    overalls.sort(reverse=True)
    core = overalls[: min(20, len(overalls))]

    return sum(core) / len(core)
