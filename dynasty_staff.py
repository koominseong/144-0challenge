# dynasty_staff.py
# =========================================
# KBO Dynasty - Phase 3: 감독/코치
# 실존 KBO 역대 감독/코치 풀 + 성격(스타일) 시너지
#
# 감독 스타일:
#   승부사: 팀 평균 7년차 이상(베테랑 팀)이면 전력 +2.5%, 아니면 +0.5%
#   육성가: 4년차 이하 선수 오프시즌 성장 +1 (전력 보정 없음)
#   지장:   조건 없이 전력 +1.5%
#   덕장:   시즌 종료 팬 증가율 +3%p
#   데이터: 전력 +1.0% + 접전(동점) 승부 유리
#
# 등급: S/A/B/C → 전력 기본 보정 +3/+2/+1/+0 %
# 코치: 타격(HITTING)/투수(PITCHING), 등급별 해당 포지션 성장 +0~2
# 연봉: 매 시즌 예산에서 자동 차감
# =========================================

import random
from dynasty_utils import get_supabase

# ---- 실존 감독 풀 (이름, 등급, 스타일) ----
MANAGER_POOL = [
    ("김응용", "S", "승부사"), ("김성근", "S", "지장"),
    ("김인식", "S", "덕장"),   ("김영덕", "A", "승부사"),
    ("강병철", "A", "덕장"),   ("이광환", "A", "데이터"),
    ("김재박", "A", "지장"),   ("백인천", "B", "승부사"),
    ("선동열", "A", "지장"),   ("김경문", "A", "승부사"),
    ("조범현", "B", "데이터"), ("류중일", "A", "덕장"),
    ("염경엽", "B", "데이터"), ("김태형", "S", "승부사"),
    ("이만수", "B", "육성가"), ("한용덕", "B", "육성가"),
    ("허문회", "C", "데이터"), ("박영길", "C", "승부사"),
    ("유백만", "C", "육성가"), ("정동진", "C", "덕장"),
]

# ---- 실존 코치 풀 (이름, 역할, 등급) ----
COACH_POOL = [
    ("장효조", "HITTING", "S"), ("김용희", "HITTING", "A"),
    ("이정훈", "HITTING", "A"), ("박흥식", "HITTING", "B"),
    ("김무관", "HITTING", "B"), ("장종훈", "HITTING", "A"),
    ("김한수", "HITTING", "B"), ("박정태", "HITTING", "B"),
    ("최동원", "PITCHING", "S"), ("김시진", "PITCHING", "A"),
    ("이상군", "PITCHING", "B"), ("한희민", "PITCHING", "B"),
    ("양상문", "PITCHING", "A"), ("정민철", "PITCHING", "A"),
    ("조계현", "PITCHING", "B"), ("이강철", "PITCHING", "A"),
]

GRADE_SALARY = {"S": 80, "A": 55, "B": 35, "C": 20}
GRADE_SIM = {"S": 0.03, "A": 0.02, "B": 0.01, "C": 0.0}
GRADE_GROWTH = {"S": 2, "A": 1, "B": 1, "C": 0}

STYLE_DESC = {
    "승부사": "베테랑 팀(평균 7년차↑) 전력 +2.5%",
    "육성가": "4년차 이하 선수 성장 +1",
    "지장": "전력 +1.5%",
    "덕장": "시즌 팬 증가율 +3%p",
    "데이터": "전력 +1% · 접전 승부 유리",
}


# =========================================
# 스태프 시장 초기화 (세이브당 1회, 없으면 생성)
# =========================================
def init_staff_market(save_id):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_staff")
        .select("id", count="exact")
        .eq("save_id", save_id)
        .execute()
        .count
    )
    if existing and existing > 0:
        return 0

    rows = []
    for name, grade, style in MANAGER_POOL:
        rows.append(
            {
                "save_id": save_id, "team_id": None,
                "name": name, "role": "MANAGER",
                "grade": grade, "style": style,
                "salary": GRADE_SALARY[grade], "hired_season": None,
            }
        )
    for name, role, grade in COACH_POOL:
        rows.append(
            {
                "save_id": save_id, "team_id": None,
                "name": name, "role": role,
                "grade": grade, "style": None,
                "salary": GRADE_SALARY[grade], "hired_season": None,
            }
        )

    sb.table("dynasty_staff").insert(rows).execute()
    print(f"[dynasty_staff] 시장 초기화={len(rows)}명")
    return len(rows)


# =========================================
# 팀별 스태프 효과 계산
# return: {team_id: {"sim": float, "bat_growth": int,
#          "pit_growth": int, "young_growth": int,
#          "fan_bonus": float, "clutch": bool}}
# =========================================
def get_staff_effects(save_id):
    sb = get_supabase()

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .not_.is_("team_id", "null")
        .execute()
        .data
    )

    # 승부사 판정용: 팀 평균 연차
    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]
    season = save["season"]

    roster = (
        sb.table("dynasty_roster")
        .select("team_id, dynasty_player(appear_season)")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    years_by_team = {}
    for r in roster:
        p = r["dynasty_player"]
        if p:
            years_by_team.setdefault(r["team_id"], []).append(
                season - p["appear_season"] + 1
            )

    effects = {}
    for s in staff:
        tid = s["team_id"]
        e = effects.setdefault(
            tid,
            {"sim": 0.0, "bat_growth": 0, "pit_growth": 0,
             "young_growth": 0, "fan_bonus": 0.0, "clutch": False},
        )

        if s["role"] == "MANAGER":
            e["sim"] += GRADE_SIM[s["grade"]]
            style = s["style"]
            if style == "지장":
                e["sim"] += 0.015
            elif style == "데이터":
                e["sim"] += 0.01
                e["clutch"] = True
            elif style == "덕장":
                e["fan_bonus"] += 0.03
            elif style == "육성가":
                e["young_growth"] += 1
            elif style == "승부사":
                ys = years_by_team.get(tid, [])
                avg = sum(ys) / len(ys) if ys else 0
                e["sim"] += 0.025 if avg >= 7 else 0.005
        elif s["role"] == "HITTING":
            e["bat_growth"] += GRADE_GROWTH[s["grade"]]
        elif s["role"] == "PITCHING":
            e["pit_growth"] += GRADE_GROWTH[s["grade"]]

    return effects


# =========================================
# 스태프 연봉 지급 (grant_season_budget 이후 호출)
# 예산 부족 팀은 스태프 자동 해임
# =========================================
def pay_staff_salaries(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    team_map = {t["id"]: t for t in teams}

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .not_.is_("team_id", "null")
        .order("salary", desc=True)
        .execute()
        .data
    )

    budgets = {t["id"]: (t.get("budget") or 0) for t in teams}
    fired = []

    for s in staff:
        tid = s["team_id"]
        if budgets.get(tid, 0) >= s["salary"]:
            budgets[tid] -= s["salary"]
        else:
            fired.append(s["id"])

    if fired:
        for i in range(0, len(fired), 50):
            sb.table("dynasty_staff").update(
                {"team_id": None, "hired_season": None}
            ).in_("id", fired[i : i + 50]).execute()

    rows = []
    for t in teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budgets[t["id"]]
        rows.append(row)
    sb.table("dynasty_team").upsert(rows).execute()

    print(f"[dynasty_staff] 연봉 지급 완료, 해임={len(fired)}명")


# =========================================
# 스태프 고용 (유저)
# =========================================
def hire_staff(save_id, team_id, staff_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    s = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .eq("id", staff_id)
        .execute()
        .data
    )
    if not s:
        return False, "해당 인물을 찾을 수 없습니다."
    s = s[0]

    if s["team_id"] is not None:
        return False, f"{s['name']}은(는) 이미 다른 팀 소속입니다."

    # 같은 역할 기존 인원 확인
    current = (
        sb.table("dynasty_staff")
        .select("id, name")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .eq("role", s["role"])
        .execute()
        .data
    )

    team = sb.table("dynasty_team").select("*").eq("id", team_id).execute().data[0]
    budget = team.get("budget") or 0

    if budget < s["salary"]:
        return False, f"예산 부족 (연봉 {s['salary']} / 보유 {budget})"

    # 기존 인원 방출
    if current:
        sb.table("dynasty_staff").update(
            {"team_id": None, "hired_season": None}
        ).eq("id", current[0]["id"]).execute()

    sb.table("dynasty_staff").update(
        {"team_id": team_id, "hired_season": save["season"]}
    ).eq("id", staff_id).execute()

    sb.table("dynasty_team").update(
        {"budget": budget - s["salary"]}
    ).eq("id", team_id).execute()

    return True, f"{s['name']} 영입! (연봉 {s['salary']} 즉시 지급, 이후 매 시즌 자동 차감)"


# =========================================
# AI 자동 고용 (오프시즌 호출)
# 빈 자리가 있는 AI 팀이 시장에서 감당 가능한 최고 등급 영입
# =========================================
def ai_hire_staff(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    teams = (
        sb.table("dynasty_team")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    ai_teams = [t for t in teams if not t["is_user"]]

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .execute()
        .data
    )

    market = [s for s in staff if s["team_id"] is None]
    hired_count = 0
    budgets = {t["id"]: (t.get("budget") or 0) for t in ai_teams}

    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    market.sort(key=lambda s: grade_order[s["grade"]])

    for t in ai_teams:
        have = {s["role"] for s in staff if s["team_id"] == t["id"]}
        for role in ("MANAGER", "HITTING", "PITCHING"):
            if role in have:
                continue
            # 예산의 15% 이내 연봉만
            cap = budgets[t["id"]] * 0.15
            candidates = [
                s for s in market
                if s["role"] == role and s["salary"] <= cap
            ]
            if not candidates:
                continue
            pick = candidates[0]
            market.remove(pick)

            sb.table("dynasty_staff").update(
                {"team_id": t["id"], "hired_season": save["season"]}
            ).eq("id", pick["id"]).execute()

            budgets[t["id"]] -= pick["salary"]
            hired_count += 1

    rows = []
    for t in ai_teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budgets[t["id"]]
        rows.append(row)
    if rows:
        sb.table("dynasty_team").upsert(rows).execute()

    print(f"[dynasty_staff] AI 고용={hired_count}명")
    return hired_count
