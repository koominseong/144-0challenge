# dynasty_lineup.py
# =========================================
# KBO Dynasty - 자동 라인업 생성 (1군 28 / 2군 체제)
# 1군 = START 9 + SP 5 + CP 1 + RP 6 + BENCH 7 = 28명
# 나머지 = MINOR (2군)
# =========================================

from dynasty_utils import get_supabase

POSITION_ORDER = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]

FIRST_TEAM_SIZE = 28
BENCH_SIZE = 7


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

    if len(batters) < 9:
        extra = [p for p in pitchers if p not in batters]
        extra.sort(key=lambda x: -x["overall"])
        need = 9 - len(batters)
        batters += extra[:need]
        moved = set(b["roster_id"] for b in batters)
        pitchers = [p for p in pitchers if p["roster_id"] not in moved]

    assignments = {}
    used = set()

    # ---------- 주전 야수 9 ----------
    depth = 1
    for pos in POSITION_ORDER:
        candidates = [
            b for b in batters
            if b["roster_id"] not in used and pos in b["positions"]
        ]
        if not candidates:
            candidates = [b for b in batters if b["roster_id"] not in used]
        if not candidates:
            break
        candidates.sort(key=lambda x: -x["overall"])
        pick = candidates[0]
        used.add(pick["roster_id"])
        assignments[pick["roster_id"]] = ("START", depth)
        depth += 1

    # ---------- 투수: 선발 5 / 마무리 1 / 불펜 6 ----------
    pitchers.sort(key=lambda x: -x["overall"])
    p_avail = [p for p in pitchers if p["roster_id"] not in used]

    for i in range(min(5, len(p_avail))):
        pk = p_avail[i]
        used.add(pk["roster_id"])
        assignments[pk["roster_id"]] = ("SP", i + 1)

    rem = [p for p in p_avail if p["roster_id"] not in used]
    if rem:
        cp = rem[0]
        used.add(cp["roster_id"])
        assignments[cp["roster_id"]] = ("CP", 1)
        rem = rem[1:]

    for i in range(min(6, len(rem))):
        rp = rem[i]
        used.add(rp["roster_id"])
        assignments[rp["roster_id"]] = ("RP", i + 1)

    # ---------- 벤치 7 (남은 선수 중 OVR 순) ----------
    remaining = [p for p in players if p["roster_id"] not in used]
    remaining.sort(key=lambda x: -x["overall"])

    bench_depth = 1
    for p in remaining[:BENCH_SIZE]:
        used.add(p["roster_id"])
        assignments[p["roster_id"]] = ("BENCH", bench_depth)
        bench_depth += 1

    # ---------- 나머지 전원 2군 ----------
    minor_depth = 1
    for p in remaining[BENCH_SIZE:]:
        assignments[p["roster_id"]] = ("MINOR", minor_depth)
        minor_depth += 1

    # ---------- DB 일괄 반영 ----------
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

    for i in range(0, len(upsert_rows), 100):
        sb.table("dynasty_roster").upsert(upsert_rows[i : i + 100]).execute()
