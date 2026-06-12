from flask import Flask, render_template, session, redirect, request, url_for
import json
import os
import random
from typing import Dict, List, Any, Optional

app = Flask(__name__)
app.secret_key = "144-0-secret-key"

DATA_DIR = "data"
ROSTER_SIZE = 15
PICKS_PER_ROUND = 3
ROUND_LOOKUP_ATTEMPTS = 300

ERAS: Dict[str, List[str]] = {
    "1980s": ["삼성", "롯데", "해태", "OB", "MBC", "삼미", "청보", "빙그레"],
    "1990s": ["삼성", "롯데", "해태", "OB", "LG", "빙그레", "한화", "태평양", "쌍방울"],
    "2000s": ["삼성", "롯데", "KIA", "두산", "LG", "한화", "SK", "현대"],
    "2010s": ["삼성", "롯데", "KIA", "두산", "LG", "한화", "SK", "넥센", "NC", "KT"],
    "2020s": ["삼성", "롯데", "KIA", "두산", "LG", "한화", "SSG", "키움", "NC", "KT"],
}

LINEUP_SLOTS = [
    "SP1", "SP2", "SP3",
    "RP1", "RP2", "RP3",
    "C", "1B", "2B", "3B", "SS",
    "LF", "CF", "RF",
    "DH",
]


def _session_list(key: str) -> List[Any]:
    value = session.get(key)
    if isinstance(value, list):
        return value
    return []


def _session_dict(key: str, default: Optional[dict] = None) -> Dict[str, Any]:
    value = session.get(key)
    if isinstance(value, dict):
        return value
    return default if default is not None else {}


def _card_id(card: Dict[str, Any], era: str, team: str, index: int) -> str:
    if card.get("id"):
        return str(card["id"])
    year = card.get("year", "")
    name = card.get("name", "")
    return f"{era}:{team}:{year}:{name}:{index}"


def normalize_cards(raw_cards: List[Dict[str, Any]], era: str, team: str) -> List[Dict[str, Any]]:
    normalized = []
    for i, card in enumerate(raw_cards):
        c = dict(card)
        c["id"] = _card_id(c, era, team, i)
        c["era"] = c.get("era", era)
        c["team"] = c.get("team", team)
        c["positions"] = c.get("positions", [])
        normalized.append(c)
    return normalized


def load_team_players(era: str, team: str) -> List[Dict[str, Any]]:
    path = os.path.join(DATA_DIR, era, f"{team}.json")
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            return []
        return normalize_cards(raw, era, team)
    except (OSError, json.JSONDecodeError):
        return []


def get_lineup() -> Dict[str, Optional[Dict[str, Any]]]:
    lineup = _session_dict("lineup")
    if not lineup:
        lineup = {slot: None for slot in LINEUP_SLOTS}
        session["lineup"] = lineup
        session.modified = True
    return lineup


def drafted_ids() -> List[str]:
    return _session_list("drafted_ids")


def add_drafted_ids(ids: List[str]) -> None:
    current = drafted_ids()
    for _id in ids:
        if _id not in current:
            current.append(_id)
    session["drafted_ids"] = current
    session.modified = True


def lineup_complete() -> bool:
    lineup = get_lineup()
    return all(lineup.get(slot) is not None for slot in LINEUP_SLOTS)


def player_open_slots(player: Dict[str, Any], lineup: Dict[str, Any]) -> List[str]:
    slots: List[str] = []
    positions = player.get("positions", [])

    for pos in positions:
        if pos == "SP":
            for slot in ["SP1", "SP2", "SP3"]:
                if lineup.get(slot) is None and slot not in slots:
                    slots.append(slot)
        elif pos == "RP":
            for slot in ["RP1", "RP2", "RP3"]:
                if lineup.get(slot) is None and slot not in slots:
                    slots.append(slot)
        else:
            if pos in LINEUP_SLOTS and lineup.get(pos) is None and pos not in slots:
                slots.append(pos)

    return slots


def eligible_roster_for_round(era: str, team: str) -> List[Dict[str, Any]]:
    lineup = get_lineup()
    used = set(drafted_ids())
    roster = load_team_players(era, team)

    eligible = []
    for player in roster:
        if player["id"] in used:
            continue
        if not player_open_slots(player, lineup):
            continue
        eligible.append(player)
    return eligible


def create_round_state(force: bool = False) -> Dict[str, str]:
    """
    current_round가 없거나 강제로 새 라운드를 뽑아야 할 때 사용.
    새 라운드는 '선수 3명을 뽑아 3명 모두 배치 가능한' 조합이어야 함.
    """
    if not force and session.get("current_round"):
        return session["current_round"]

    for _ in range(ROUND_LOOKUP_ATTEMPTS):
        era = random.choice(list(ERAS.keys()))
        team = random.choice(ERAS[era])

        if len(eligible_roster_for_round(era, team)) >= PICKS_PER_ROUND:
            round_state = {"era": era, "team": team}
            session["current_round"] = round_state
            session.pop("selected_player_ids", None)
            session.pop("selected_slot_map", None)
            session.modified = True
            return round_state

    # 데이터가 아직 적을 때를 위한 fallback
    era = random.choice(list(ERAS.keys()))
    team = random.choice(ERAS[era])
    round_state = {"era": era, "team": team}
    session["current_round"] = round_state
    session.pop("selected_player_ids", None)
    session.pop("selected_slot_map", None)
    session.modified = True
    return round_state


def current_round_players() -> List[Dict[str, Any]]:
    round_state = session.get("current_round") or create_round_state()
    era = round_state["era"]
    team = round_state["team"]

    roster = load_team_players(era, team)
    used = set(drafted_ids())

    # 화면에는 그 시대/그 팀의 선수 전체를 보여주되,
    # 이미 뽑힌 선수는 선택 불가 상태로 넘길 수 있게 정보를 함께 제공
    for p in roster:
        p["_eligible_slots"] = player_open_slots(p, get_lineup())
        p["_already_drafted"] = p["id"] in used

    return roster


def reset_game_state() -> None:
    session["lineup"] = {slot: None for slot in LINEUP_SLOTS}
    session["drafted_ids"] = []
    session["era_reroll_used"] = False
    session["team_reroll_used"] = False
    session.pop("current_round", None)
    session.pop("selected_player_ids", None)
    session.pop("selected_slot_map", None)
    session.modified = True


def find_player_in_round(player_id: str) -> Optional[Dict[str, Any]]:
    round_state = session.get("current_round")
    if not round_state:
        return None

    roster = load_team_players(round_state["era"], round_state["team"])
    for player in roster:
        if player["id"] == player_id:
            player["_eligible_slots"] = player_open_slots(player, get_lineup())
            return player
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/start")
def start():
    reset_game_state()
    create_round_state(force=True)
    return redirect(url_for("draft"))


@app.route("/draft")
def draft():
    if lineup_complete():
        return redirect(url_for("result"))

    round_state = session.get("current_round") or create_round_state()
    roster = current_round_players()

    return render_template(
        "draft.html",
        era=round_state["era"],
        team=round_state["team"],
        players=roster,
        lineup=get_lineup(),
        drafted_count=len(drafted_ids()),
        roster_size=ROSTER_SIZE,
        picks_per_round=PICKS_PER_ROUND,
        era_reroll_used=session.get("era_reroll_used", False),
        team_reroll_used=session.get("team_reroll_used", False),
    )


@app.route("/reroll-era")
def reroll_era():
    if session.get("era_reroll_used", False):
        return redirect(url_for("draft"))

    new_era = random.choice(list(ERAS.keys()))
    new_team = random.choice(ERAS[new_era])

    session["current_round"] = {"era": new_era, "team": new_team}
    session["era_reroll_used"] = True
    session.pop("selected_player_ids", None)
    session.pop("selected_slot_map", None)
    session.modified = True

    return redirect(url_for("draft"))


@app.route("/reroll-team")
def reroll_team():
    if session.get("team_reroll_used", False):
        return redirect(url_for("draft"))

    round_state = session.get("current_round") or create_round_state()
    era = round_state["era"]
    new_team = random.choice(ERAS[era])

    session["current_round"] = {"era": era, "team": new_team}
    session["team_reroll_used"] = True
    session.pop("selected_player_ids", None)
    session.pop("selected_slot_map", None)
    session.modified = True

    return redirect(url_for("draft"))


@app.route("/choose", methods=["POST"])
def choose():
    if lineup_complete():
        return redirect(url_for("result"))

    selected_ids = request.form.getlist("player_ids")
    selected_ids = [x for x in selected_ids if x]

    if len(selected_ids) != PICKS_PER_ROUND:
        session["error"] = f"선수는 정확히 {PICKS_PER_ROUND}명 선택해야 합니다."
        return redirect(url_for("draft"))

    round_state = session.get("current_round") or create_round_state()
    roster = load_team_players(round_state["era"], round_state["team"])
    roster_by_id = {p["id"]: p for p in roster}

    picked_players = []
    for pid in selected_ids:
        player = roster_by_id.get(pid)
        if not player:
            session["error"] = "잘못된 선수 선택입니다."
            return redirect(url_for("draft"))
        if pid in drafted_ids():
            session["error"] = "이미 뽑힌 선수는 다시 선택할 수 없습니다."
            return redirect(url_for("draft"))
        if not player_open_slots(player, get_lineup()):
            session["error"] = f"{player['name']}는 현재 배치 가능한 포지션이 없습니다."
            return redirect(url_for("draft"))
        picked_players.append(player)

    session["selected_player_ids"] = selected_ids
    session.pop("selected_slot_map", None)
    session.modified = True

    # 선택 직후 포지션 배치 화면으로 이동
    return render_template(
        "position_select.html",
        era=round_state["era"],
        team=round_state["team"],
        players=picked_players,
        lineup=get_lineup(),
        error=session.pop("error", None),
    )


@app.route("/commit", methods=["POST"])
def commit():
    selected_ids = session.get("selected_player_ids", [])
    if len(selected_ids) != PICKS_PER_ROUND:
        session["error"] = "먼저 선수 3명을 선택해야 합니다."
        return redirect(url_for("draft"))

    round_state = session.get("current_round")
    if not round_state:
        session["error"] = "현재 라운드 정보가 없습니다."
        return redirect(url_for("draft"))

    roster = load_team_players(round_state["era"], round_state["team"])
    roster_by_id = {p["id"]: p for p in roster}
    lineup = get_lineup()

    chosen_positions = []
    chosen_players = []

    for pid in selected_ids:
        player = roster_by_id.get(pid)
        if not player:
            session["error"] = "선수 정보를 찾지 못했습니다."
            return redirect(url_for("draft"))

        slot = request.form.get(f"slot_{pid}", "").strip()
        if not slot:
            session["error"] = f"{player['name']}의 포지션을 선택해야 합니다."
            return redirect(url_for("draft"))

        if slot not in LINEUP_SLOTS:
            session["error"] = f"{player['name']}의 포지션이 올바르지 않습니다."
            return redirect(url_for("draft"))

        if lineup.get(slot) is not None:
            session["error"] = f"{slot} 자리는 이미 사용 중입니다."
            return redirect(url_for("draft"))

        eligible_slots = player_open_slots(player, lineup)
        if slot not in eligible_slots:
            session["error"] = f"{player['name']}는 {slot}에 배치할 수 없습니다."
            return redirect(url_for("draft"))

        if slot in chosen_positions:
            session["error"] = "같은 라운드에서 같은 포지션을 두 번 사용할 수 없습니다."
            return redirect(url_for("draft"))

        chosen_positions.append(slot)
        chosen_players.append((pid, player, slot))

    # 모두 검증된 뒤 실제 반영
    for pid, player, slot in chosen_players:
        lineup[slot] = {
            "id": player["id"],
            "name": player["name"],
            "year": player.get("year"),
            "era": player.get("era"),
            "team": player.get("team"),
            "positions": player.get("positions", []),
            "war": player.get("war"),
        }

    session["lineup"] = lineup
    add_drafted_ids([pid for pid, _, _ in chosen_players])

    # 라운드 종료 후 다음 라운드 준비
    session.pop("current_round", None)
    session.pop("selected_player_ids", None)
    session.pop("selected_slot_map", None)
    session.pop("error", None)
    session.modified = True

    if lineup_complete():
        return redirect(url_for("result"))

    create_round_state(force=True)
    return redirect(url_for("draft"))


@app.route("/result")
def result():
    if not lineup_complete():
        return redirect(url_for("draft"))

    lineup = get_lineup()

    ordered_lineup = [
        (slot, lineup.get(slot))
        for slot in LINEUP_SLOTS
    ]

    return render_template(
        "result.html",
        lineup=ordered_lineup
    )


if __name__ == "__main__":
    app.run(debug=True)
