from flask import Flask, render_template, request, session, redirect, url_for
import json
import os
import random

app = Flask(__name__)
app.secret_key = "kbo1440"

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

TEAMS_2010 = [
    "doosan",
    "lg",
    "samsung",
    "sk",
    "kia",
    "heroes",
    "kt",
    "hanwha",
    "lotte",
    "nc"
]


def load_team(team):
    path = f"data/2010_{team}.json"

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def random_team():
    available = [
        t for t in TEAMS_2010
        if t not in session["used_teams"]
    ]

    if not available:
        return None

    return random.choice(available)


@app.route("/")
def home():

    session.clear()

    session["lineup"] = {}

    session["used_teams"] = []

    session["team_reroll"] = 1
    session["era_reroll"] = 1

    return redirect("/next")


@app.route("/next")
def next_team():

    team = random_team()

    if team is None:
        return redirect("/result")

    session["current_team"] = team

    session["used_teams"].append(team)

    players = load_team(team)

    return render_template(
        "team.html",
        team=team.upper(),
        players=players,
        lineup=session["lineup"],
        team_reroll=session["team_reroll"],
        era_reroll=session["era_reroll"]
    )


@app.route("/select", methods=["POST"])
def select():

    selected_ids = request.form.getlist("players")

    if len(selected_ids) != 3:
        return "반드시 3명 선택"

    session["selected_players"] = selected_ids

    return redirect("/assign")


@app.route("/assign")
def assign():

    team = session["current_team"]

    players = load_team(team)

    selected = [
        p for p in players
        if p["id"] in session["selected_players"]
    ]

    return render_template(
        "assign.html",
        players=selected,
        lineup=session["lineup"]
    )


@app.route("/assign_player", methods=["POST"])
def assign_player():

    player_id = request.form["player_id"]
    position = request.form["position"]

    team = session["current_team"]

    players = load_team(team)

    player = next(
        p for p in players
        if p["id"] == player_id
    )

    lineup = session["lineup"]

    if position in lineup:
        return "이미 사용중"

    if position not in player["positions"]:
        return "불가능한 포지션"

    lineup[position] = player

    session["lineup"] = lineup

    return redirect("/assign")


@app.route("/team_reroll")
def team_reroll():

    if session["team_reroll"] <= 0:
        return redirect("/next")

    session["team_reroll"] -= 1

    return redirect("/next")


@app.route("/result")
def result():

    lineup = session["lineup"]

    total_war = 0

    for player in lineup.values():
        total_war += player["war"]

    return render_template(
        "result.html",
        lineup=lineup,
        total_war=round(total_war, 1)
    )


if __name__ == "__main__":
    app.run(debug=True)
