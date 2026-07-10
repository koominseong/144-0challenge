# dynasty_event.py
# =========================================
# KBO Dynasty - 이벤트 로그 (뉴스 피드)
# 트레이드 / FA 이적 / 은퇴 / 우승 등 중대 이벤트 기록
# =========================================

from dynasty_utils import get_supabase


# =========================================
# 이벤트 기록 (단건)
# =========================================
def log_event(save_id, season, week, type_, icon, message):
    sb = get_supabase()
    sb.table("dynasty_event").insert(
        {
            "save_id": save_id,
            "season": season,
            "week": week,
            "type": type_,
            "icon": icon,
            "message": message,
        }
    ).execute()


# =========================================
# 이벤트 기록 (일괄)
# events: [{season, week, type, icon, message}, ...]
# =========================================
def log_events(save_id, events):
    if not events:
        return
    sb = get_supabase()
    rows = [
        {
            "save_id": save_id,
            "season": e["season"],
            "week": e.get("week", 0),
            "type": e["type"],
            "icon": e["icon"],
            "message": e["message"],
        }
        for e in events
    ]
    for i in range(0, len(rows), 100):
        sb.table("dynasty_event").insert(rows[i : i + 100]).execute()


# =========================================
# 최근 이벤트 조회 (대시보드용)
# =========================================
def get_recent_events(save_id, limit=12):
    sb = get_supabase()
    return (
        sb.table("dynasty_event")
        .select("*")
        .eq("save_id", save_id)
        .order("id", desc=True)
        .limit(limit)
        .execute()
        .data
    )
