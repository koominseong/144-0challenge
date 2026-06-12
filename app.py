from flask import Flask, render_template, request, session, redirect
import os
import json
import random

app = Flask(__name__)
app.secret_key = "kbo1440"

TEAM_NAMES = {
    "bears": "두산 베어스",
    "twins": "LG 트윈스",
    "lions": "삼성 라이온즈",
    "tigers": "KIA 타이거즈",
    "eagles": "한화 이글스",
    "wyverns": "SK 와이번스",
    "giants": "롯데 자이언츠",
    "wiz": "KT 위즈",
    "dinos": "NC 다이노스",
    "heroes": "넥센 히어로즈"
}

POSITIONS = [
    "SP", "SP", "SP",
    "RP", "RP", "RP",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "LF",
    "CF",
    "RF",
    "DH"
]


def load_team(team):
    path = os.path.join(
        "data",
        "2010s",
        f"{team}.json"
    )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def start():

    session.clear()

    session["used_teams"] = []

    session["lineup"] = {
    "SP": [],
    "RP": [],
    "C": None,
    "1B": None,
    "2B": None,
    "3B": None,
    "SS": None,
    "LF": None,
    "CF": None,
    "RF": None,
    "DH": None
     }

    session["used_players"] = []

    session["team_reroll"] = 1

    return redirect("/next")


@app.route("/next")
def next_team():

    available = [
        team
        for team in TEAM_NAMES.keys()
        if team not in session["used_teams"]
    ]

    if not available:
        return redirect("/result")

    team = random.choice(available)

    session["current_team"] = team

    session["used_teams"].append(team)

    players = load_team(team)

    return render_template(
        "team.html",
        team_name=TEAM_NAMES[team],
        team_key=team,
        players=players,
        lineup=session["lineup"],
        rerolls=session["team_reroll"]
    )


@app.route("/team_reroll")
def team_reroll():

    if session["team_reroll"] <= 0:
        return redirect("/next")

    session["team_reroll"] -= 1

    session["used_teams"].remove(
        session["current_team"]
    )

    return redirect("/next")


@app.route("/select", methods=["POST"])
def select_players():

    selected = request.form.getlist("players")

    if len(selected) != 3:
        return "반드시 3명 선택해야 함"

    used_players = session.get("used_players", [])

    for player_id in selected:
        if player_id in used_players:
            return "이미 사용한 선수입니다"

    session["selected_players"] = selected

    return redirect("/assign")


@app.route("/assign")
def assign():

    players = load_team(
        session["current_team"]
    )

    selected_players = [
        p
        for p in players
        if p["id"] in session["selected_players"]
    ]

    return render_template(
        "assign.html",
        players=selected_players,
        lineup=session["lineup"]
    )


@app.route("/assign_player", methods=["POST"])
def assign_player():

    player_id = request.form["player_id"]
    position = request.form["position"]

    players = load_team(session["current_team"])

    player = next(
        p for p in players
        if p["id"] == player_id
    )

    lineup = session["lineup"]

    if position not in player["positions"]:
        return "배치 불가"

    if position == "SP":

        if len(lineup["SP"]) >= 3:
            return "SP 가득 참"

        lineup["SP"].append(player)

    elif position == "RP":

        if len(lineup["RP"]) >= 3:
            return "RP 가득 참"

        lineup["RP"].append(player)

    else:

        if lineup[position] is not None:
            return "이미 사용 중인 포지션"

        lineup[position] = player

    session["lineup"] = lineup

    used_players = session["used_players"]

    if player_id not in used_players:
        used_players.append(player_id)

    session["used_players"] = used_players

    session.modified = True

    filled = (
        len(lineup["SP"])
        + len(lineup["RP"])
    )

    for pos in [
        "C","1B","2B","3B","SS",
        "LF","CF","RF","DH"
    ]:
        if lineup[pos]:
            filled += 1

    if filled >= 15:
        return redirect("/result")

    return redirect("/assign")


@app.route("/result")
def result():

    lineup = session["lineup"]

    total_war = 0

    for player in lineup["SP"]:
        total_war += player["war"]

    for player in lineup["RP"]:
        total_war += player["war"]

    for pos in [
        "C","1B","2B","3B","SS",
        "LF","CF","RF","DH"
    ]:
        if lineup[pos]:
            total_war += lineup[pos]["war"]

    return render_template(
        "result.html",
        lineup=lineup,
        total_war=round(total_war, 1)
    )


if __name__ == "__main__":
    app.run(debug=True)
