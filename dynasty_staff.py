# dynasty_staff.py - 전체 교체본 Part1
# =========================================
# KBO Dynasty - 감독/코칭스태프 (확장판)
# 역할: MANAGER / HITTING / PITCHING / DEFENSE / BULLPEN / BASERUN / BATTERY
# + 인물별 고유 특성(trait) / 감독-코치 시너지 / 방출(fire_staff)
# 실존 KBO 역대 감독·코치 기반
# =========================================

import random
from dynasty_utils import get_supabase

# ---- 감독 풀 (이름, 등급, 스타일) ----
MANAGER_POOL = [
    ("김응용", "S", "승부사"), ("김성근", "S", "지장"),
    ("김인식", "S", "덕장"),   ("김태형", "S", "승부사"),
    ("이강철", "S", "지장"),
    ("김영덕", "A", "승부사"), ("강병철", "A", "덕장"),
    ("이광환", "A", "데이터"), ("김재박", "A", "지장"),
    ("선동열", "A", "지장"),   ("김경문", "A", "승부사"),
    ("류중일", "A", "덕장"),   ("제리 로이스터", "A", "승부사"),
    ("트레이 힐만", "A", "데이터"), ("김원형", "A", "지장"),
    ("백인천", "B", "승부사"), ("조범현", "B", "데이터"),
    ("염경엽", "A", "데이터"), ("이만수", "B", "육성가"),
    ("한용덕", "B", "육성가"), ("김기태", "B", "덕장"),
    ("이승엽", "C", "승부사"), ("박진만", "B", "지장"),
    ("최원호", "B", "육성가"), ("이순철", "B", "승부사"),
    ("카를로스 수베로", "B", "데이터"),
    ("허문회", "C", "데이터"), ("박영길", "C", "승부사"),
    ("유백만", "C", "육성가"), ("정동진", "C", "덕장"),
    ("홍원기", "C", "육성가"), ("강인권", "C", "덕장"),
    ("김진욱", "C", "육성가"), ("래리 서튼", "C", "덕장"),
    ("류지현", "C", "지장"),
]

# ---- 코치 풀 (이름, 역할, 등급, 특성) ----
COACH_POOL = [
    # 타격코치
    ("장효조", "HITTING", "S", "타격의 달인"),
    ("김용희", "HITTING", "A", "장타 혁명"),
    ("이정훈", "HITTING", "A", "정교한 타격"),
    ("장종훈", "HITTING", "A", "장타 혁명"),
    ("이병규", "HITTING", "A", "정교한 타격"),
    ("정경배", "HITTING", "A", "선구안 전도사"),
    ("박흥식", "HITTING", "B", "선구안 전도사"),
    ("김무관", "HITTING", "B", "정교한 타격"),
    ("김한수", "HITTING", "B", "장타 혁명"),
    ("박정태", "HITTING", "B", "정교한 타격"),
    ("박용택", "HITTING", "B", "타격의 달인"),
    ("홍성흔", "HITTING", "B", "장타 혁명"),
    ("김재현", "HITTING", "C", "선구안 전도사"),
    ("강동우", "HITTING", "C", "정교한 타격"),
    # 투수코치
    ("최동원", "PITCHING", "S", "에이스 메이커"),
    ("선우대식", "PITCHING", "C", "제구 마스터"),
    ("김시진", "PITCHING", "A", "제구 마스터"),
    ("양상문", "PITCHING", "A", "에이스 메이커"),
    ("정민철", "PITCHING", "A", "강철 어깨"),
    ("송진우", "PITCHING", "A", "강철 어깨"),
    ("정민태", "PITCHING", "A", "에이스 메이커"),
    ("손혁", "PITCHING", "B", "제구 마스터"),
    ("이상군", "PITCHING", "B", "강철 어깨"),
    ("한희민", "PITCHING", "B", "제구 마스터"),
    ("조계현", "PITCHING", "B", "에이스 메이커"),
    ("이강철(코치)", "PITCHING", "B", "제구 마스터"),  # 감독과 동명이인 방지용, 화면에선 '이강철(코치)'로 표시해도 됨
    ("배영수", "PITCHING", "B", "강철 어깨"),
    ("구대성", "PITCHING", "B", "에이스 메이커"),
    ("오봉옥", "PITCHING", "C", "제구 마스터"),
    # 수비코치
    ("김민재", "DEFENSE", "A", "그물 수비"),
    ("류지현(코치)", "DEFENSE", "A", "시프트 설계자"),
    ("김민호", "DEFENSE", "B", "그물 수비"),
    ("손시헌", "DEFENSE", "B", "시프트 설계자"),
    ("박진만(코치)", "DEFENSE", "B", "그물 수비"),
    ("박기혁", "DEFENSE", "C", "그물 수비"),
    # 불펜코치
    ("정우람", "BULLPEN", "A", "필승조 조련"),
    ("권오준", "BULLPEN", "B", "마당쇠 육성"),
    ("정재훈", "BULLPEN", "B", "필승조 조련"),
    ("강영식", "BULLPEN", "C", "마당쇠 육성"),
    # 주루코치
    ("전준호", "BASERUN", "A", "그린라이트"),
    ("이종욱", "BASERUN", "B", "폭주 기관차"),
    ("정수성", "BASERUN", "B", "그린라이트"),
    ("이대형", "BASERUN", "C", "폭주 기관차"),
    # 배터리코치
    ("진갑용", "BATTERY", "A", "도루 저지 특화"),
    ("조인성", "BATTERY", "A", "볼배합 아티스트"),
    ("김동수", "BATTERY", "B", "볼배합 아티스트"),
    ("강성우", "BATTERY", "C", "도루 저지 특화"),
]

ALL_ROLES = ["MANAGER", "HITTING", "PITCHING", "DEFENSE", "BULLPEN", "BASERUN", "BATTERY"]

GRADE_SALARY = {"S": 80, "A": 55, "B": 35, "C": 20}
GRADE_SIM = {"S": 0.03, "A": 0.02, "B": 0.01, "C": 0.0}
GRADE_GROWTH = {"S": 2, "A": 1, "B": 1, "C": 0}
GRADE_MULT = {"S": 2.0, "A": 1.5, "B": 1.0, "C": 0.5}   # 신규 코치 효과 배율

STYLE_DESC = {
    "승부사": "베테랑 팀(평균 7년차↑) 전력 +2.5%",
    "육성가": "4년차 이하 선수 성장 +1",
    "지장": "전력 +1.5%",
    "덕장": "시즌 팬 증가율 +3%p",
    "데이터": "전력 +1% · 접전 승부 유리",
}

# ---- 고유 특성 효과 (등급 배율 GRADE_MULT 적용) ----
TRAIT_DESC = {
    "타격의 달인":   "팀 타격 +0.6%",
    "장타 혁명":     "타자 성장 시 파워 추가 +1",
    "정교한 타격":   "번트 성공률 +6%p",
    "선구안 전도사": "팀 출루 소폭 상승",
    "에이스 메이커": "선발 투구 지속력 +2아웃",
    "제구 마스터":   "팀 삼진 유도 +0.8%p",
    "강철 어깨":     "선발 피로 저하 완화",
    "그물 수비":     "호수비 확률 상승 (수비력 +3)",
    "시프트 설계자": "시프트 성공 +5%p / 역효과 -3%p",
    "필승조 조련":   "불펜 등판 시 능력 +2",
    "마당쇠 육성":   "불펜 투구 지속력 +3아웃",
    "그린라이트":    "도루 성공률 +5%p",
    "폭주 기관차":   "추가 진루(3루 도전) 성공 +7%p",
}

# ---- 감독-코치 시너지 (감독 스타일 × 코치 역할) ----
SYNERGY = {
    ("승부사", "BULLPEN"): ("벼랑끝 필승조", "불펜코치 효과 2배"),
    ("지장", "DEFENSE"): ("수비의 완성", "수비코치 효과 2배"),
    ("데이터", "BATTERY"): ("볼배합 데이터화", "배터리코치 효과 2배"),
    ("육성가", "HITTING"): ("타격 육성 시스템", "타자 성장 추가 +1"),
    ("육성가", "PITCHING"): ("투수 육성 시스템", "투수 성장 추가 +1"),
    ("덕장", "BASERUN"): ("신바람 야구", "주루 효과 1.5배 · 팬 +1%p"),
}

ROLE_KR = {
    "MANAGER": "감독", "HITTING": "타격코치", "PITCHING": "투수코치",
    "DEFENSE": "수비코치", "BULLPEN": "불펜코치",
    "BASERUN": "주루코치", "BATTERY": "배터리코치",
}


# =========================================
# 스태프 시장 초기화 + 신규 인물 증분 추가
# (기존 세이브도 새 풀 인원이 자동 유입되도록 이름 기준 diff)
# =========================================
def init_staff_market(save_id):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_staff")
        .select("name")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    have = {s["name"] for s in existing}

    rows = []
    for name, grade, style in MANAGER_POOL:
        if name in have:
            continue
        rows.append(
            {"save_id": save_id, "team_id": None, "name": name,
             "role": "MANAGER", "grade": grade, "style": style,
             "trait": None, "salary": GRADE_SALARY[grade], "hired_season": None}
        )
    for name, role, grade, trait in COACH_POOL:
        if name in have:
            continue
        rows.append(
            {"save_id": save_id, "team_id": None, "name": name,
             "role": role, "grade": grade, "style": None,
             "trait": trait, "salary": GRADE_SALARY[grade], "hired_season": None}
        )

    if rows:
        sb.table("dynasty_staff").insert(rows).execute()
        print(f"[dynasty_staff] 신규 인물 추가={len(rows)}명")
    return len(rows)

# dynasty_staff.py - 전체 교체본 Part2

# =========================================
# 팀별 스태프 효과 계산 (특성 + 시너지 포함)
# return: {team_id: effects dict}
# effects 키:
#   sim, bat_growth, pit_growth, young_growth, fan_bonus, clutch   (기존)
#   bat_mod        : 라이브 타격 보정 (타격의 달인/선구안)
#   bunt_bonus     : 번트 성공률 가산
#   power_growth   : 타자 성장 시 파워 추가
#   so_bonus       : 삼진 유도 가산
#   sp_outs        : 선발 지속력 (+아웃)
#   sp_fatigue_cut : 선발 피로 완화 (0~1 배율 감소)
#   def_bonus      : 수비력 가산 (호수비)
#   shift_plus     : 시프트 성공 가산
#   shift_backfire_cut : 시프트 역효과 감소
#   rp_boost       : 불펜 등판 능력 가산
#   rp_outs        : 불펜 지속력 (+아웃)
#   steal_bonus    : 도루 성공 가산
#   send_bonus     : 추가 진루 성공 가산
#   opp_steal_cut  : 상대 도루 성공 감소
#   synergies      : [(이름, 설명)] 발동 중인 시너지
# =========================================
def _empty_effects():
    return {
        "sim": 0.0, "bat_growth": 0, "pit_growth": 0, "young_growth": 0,
        "fan_bonus": 0.0, "clutch": False,
        "bat_mod": 0.0, "bunt_bonus": 0.0, "power_growth": 0,
        "so_bonus": 0.0, "sp_outs": 0, "sp_fatigue_cut": 0.0,
        "def_bonus": 0, "shift_plus": 0.0, "shift_backfire_cut": 0.0,
        "rp_boost": 0, "rp_outs": 0,
        "steal_bonus": 0.0, "send_bonus": 0.0, "opp_steal_cut": 0.0,
        "synergies": [],
    }


# 특성 → (효과키, 기준값)  ※ GRADE_MULT 배율 적용
TRAIT_EFFECT = {
    "타격의 달인":   ("bat_mod", 0.006),
    "장타 혁명":     ("power_growth", 1),
    "정교한 타격":   ("bunt_bonus", 0.06),
    "선구안 전도사": ("bat_mod", 0.004),
    "에이스 메이커": ("sp_outs", 2),
    "제구 마스터":   ("so_bonus", 0.008),
    "강철 어깨":     ("sp_fatigue_cut", 0.4),
    "그물 수비":     ("def_bonus", 3),
    "시프트 설계자": ("shift_plus", 0.05),
    "필승조 조련":   ("rp_boost", 2),
    "마당쇠 육성":   ("rp_outs", 3),
    "그린라이트":    ("steal_bonus", 0.05),
    "폭주 기관차":   ("send_bonus", 0.07),
}


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

    # 팀별 감독 스타일 (시너지 판정용)
    manager_style = {}
    for s in staff:
        if s["role"] == "MANAGER":
            manager_style[s["team_id"]] = s["style"]

    effects = {}
    for s in staff:
        tid = s["team_id"]
        e = effects.setdefault(tid, _empty_effects())
        grade = s["grade"]
        mult = GRADE_MULT[grade]

        # ----- 감독 -----
        if s["role"] == "MANAGER":
            e["sim"] += GRADE_SIM[grade]
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
            continue

        # ----- 코치 공통: 시너지 배율 -----
        style = manager_style.get(tid)
        syn = SYNERGY.get((style, s["role"])) if style else None
        syn_mult = 1.0
        if syn:
            if s["role"] in ("BULLPEN", "DEFENSE", "BATTERY"):
                syn_mult = 2.0
            elif s["role"] == "BASERUN":
                syn_mult = 1.5
                e["fan_bonus"] += 0.01
            e["synergies"].append(syn)

        # ----- 역할 기본 효과 -----
        if s["role"] == "HITTING":
            e["bat_growth"] += GRADE_GROWTH[grade] + (1 if syn else 0)
        elif s["role"] == "PITCHING":
            e["pit_growth"] += GRADE_GROWTH[grade] + (1 if syn else 0)
        elif s["role"] == "DEFENSE":
            e["def_bonus"] += round(2 * mult * syn_mult)
            e["shift_backfire_cut"] += 0.01 * mult * syn_mult
        elif s["role"] == "BULLPEN":
            e["rp_outs"] += round(2 * mult * syn_mult)
            e["rp_boost"] += round(1 * mult * syn_mult)
        elif s["role"] == "BASERUN":
            e["steal_bonus"] += 0.03 * mult * syn_mult
            e["send_bonus"] += 0.03 * mult * syn_mult
        elif s["role"] == "BATTERY":
            e["opp_steal_cut"] += 0.04 * mult * syn_mult
            e["so_bonus"] += 0.004 * mult * syn_mult

        # ----- 고유 특성 -----
        trait = s.get("trait")
        if trait in TRAIT_EFFECT:
            key, base = TRAIT_EFFECT[trait]
            val = base * mult * syn_mult
            if isinstance(base, int):
                e[key] += round(val)
            else:
                e[key] += val

    return effects


# =========================================
# 스태프 방출 (유저) — 연봉 환불 없음
# =========================================
def fire_staff(save_id, team_id, staff_id):
    sb = get_supabase()

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

    if s["team_id"] != team_id:
        return False, "내 팀 소속이 아닙니다."

    sb.table("dynasty_staff").update(
        {"team_id": None, "hired_season": None}
    ).eq("id", staff_id).execute()

    return True, f"{s['name']} {ROLE_KR.get(s['role'], s['role'])} 방출. (지급한 연봉은 환불되지 않음)"


# =========================================
# 스태프 연봉 지급 (기존과 동일 로직)
# =========================================
def pay_staff_salaries(save_id):
    sb = get_supabase()

    teams = (
        sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    )

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
# 고용 (유저) — 기존과 동일, 역할만 확장 자동 대응
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
# AI 자동 고용 — 핵심 3역할 우선, 여유 있으면 신규 역할도
# =========================================
def ai_hire_staff(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    teams = (
        sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    )
    ai_teams = [t for t in teams if not t["is_user"]]

    staff = (
        sb.table("dynasty_staff").select("*").eq("save_id", save_id).execute().data
    )

    market = [s for s in staff if s["team_id"] is None]
    hired_count = 0
    budgets = {t["id"]: (t.get("budget") or 0) for t in ai_teams}

    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    market.sort(key=lambda s: grade_order[s["grade"]])

    CORE = ("MANAGER", "HITTING", "PITCHING")
    EXTRA = ("BULLPEN", "DEFENSE", "BATTERY", "BASERUN")

    for t in ai_teams:
        have = {s["role"] for s in staff if s["team_id"] == t["id"]}
        for role in CORE + EXTRA:
            if role in have:
                continue
            # 핵심 역할은 예산 15%, 부가 역할은 8% 이내 연봉만
            ratio = 0.15 if role in CORE else 0.08
            cap = budgets[t["id"]] * ratio
            candidates = [
                s for s in market if s["role"] == role and s["salary"] <= cap
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
