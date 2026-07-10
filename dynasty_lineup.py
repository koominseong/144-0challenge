# dynasty_lineup.py
# =========================================
# KBO Dynasty - 자동 라인업 생성 (일괄 upsert 버전)
# 팀당 DB 호출 2회 (조회 1 + upsert 1)
# =========================================

from dynasty_utils import get_supabase

POSITION_ORDER = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]


# =========================================
# 팀 자동 라인업 생성
# =========================================
def auto_generate_lineup(save_id, team_id):
    sb = get_supabase()

    rows = (
        sb.table("dynasty_roster")
        .select("id, player_id, dynasty_player(*)")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .execute()
        .data
    )

    players = []
    for r in rows:
        p = r["dynasty_player"]
        if not p or p["retired"]:
            continue
        players.append(
            {
                "roster_id": r["id"],
                "player_id": r["player_id"],
                "name": p["name"],
                "positions": p["positions"] or "",
                "overall": p["overall"],
            }
        )

    if not players:
        return

    pitchers = [p for p in players if "P" in p["positions"]]
    batters = [p for p in players if "P" not in p["positions"]]

    # 야수가 없으면 투수 겸업 처리
    if len(batters) < 9:
        extra = [p for p in pitchers if p not in batters]
        extra.sort(key=lambda x: -x["overall"])
        need = 9 - len(batters)
        batters += extra[:need]
        moved = set(b["roster_id"] for b in batters)
        pitchers = [p for p in pitchers if p["roster_id"] not in moved]

    assignments = {}  # roster_id -> (role, depth)

    # ---------- 야수 주전 배치 ----------
    used = set()
    depth = 1

    for pos in POSITION_ORDER:
        candidates = [
            b
            for b in batters
            if b["roster_id"] not in used and pos in b["positions"]
        ]
        if not candidates and pos == "DH":
            candidates = [b for b in batters if b["roster_id"] not in used]
        if not candidates:
            candidates = [b for b in batters if b["roster_id"] not in used]
        if not candidates:
            break

        candidates.sort(key=lambda x: -x["overall"])
        pick = candidates[0]
        used.add(pick["roster_id"])
        assignments[pick["roster_id"]] = ("START", depth)
        depth += 1

    # ---------- 투수 배치 ----------
    pitchers.sort(key=lambda x: -x["overall"])
    p_available = [p for p in pitchers if p["roster_id"] not in used]

    sp_count = min(5, len(p_available))
    for i in range(sp_count):
        pk = p_available[i]
        used.add(pk["roster_id"])
        assignments[pk["roster_id"]] = ("SP", i + 1)

    remaining_p = [p for p in p_available if p["roster_id"] not in used]

    if remaining_p:
        cp = remaining_p[0]
        used.add(cp["roster_id"])
        assignments[cp["roster_id"]] = ("CP", 1)
        remaining_p = remaining_p[1:]

    rp_count = min(6, len(remaining_p))
    for i in range(rp_count):
        rp = remaining_p[i]
        used.add(rp["roster_id"])
        assignments[rp["roster_id"]] = ("RP", i + 1)

    # ---------- 나머지 벤치 ----------
    bench_depth = 1
    for p in players:
        if p["roster_id"] in used:
            continue
        assignments[p["roster_id"]] = ("BENCH", bench_depth)
        bench_depth += 1

    # ---------- DB 일괄 반영 (upsert 1회) ----------
    id_map = {p["roster_id"]: p["player_id"] for p in players}

    upsert_rows = []
    for roster_id, (role, d) in assignments.items():
        upsert_rows.append(
            {
                "id": roster_id,
                "save_id": save_id,
                "team_id": team_id,
                "player_id": id_map[roster_id],
                "role": role,
                "depth": d,
            }
        )

    sb.table("dynasty_roster").upsert(upsert_rows).execute()
