from flask import Flask, render_template, session, redirect, request
import random
import json

app = Flask(__name__)
app.secret_key = "144-0-secret"


ERAS = {
    "1980s": [
        "삼성", "롯데", "해태", "OB",
        "MBC", "삼미", "청보", "빙그레"
    ],

    "1990s": [
        "삼성", "롯데", "해태", "OB",
        "LG", "빙그레", "한화",
        "태평양", "쌍방울"
    ],

    "2000s": [
        "삼성", "롯데", "KIA", "두산",
        "LG", "한화", "SK", "현대"
    ],

    "2010s": [
        "삼성", "롯데", "KIA", "두산",
        "LG", "한화", "SK",
        "넥센", "NC", "KT"
    ],

    "2020s": [
        "삼성", "롯데", "KIA", "두산",
        "LG", "한화", "SSG",
        "키움", "NC", "KT"
    ]
}


LINEUP_POSITIONS = [
    "SP1",
    "SP2",
    "SP3",

    "RP1",
    "RP2",
    "RP3",

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


with open("players.json", encoding="utf-8") as f:
    PLAYERS = json.load(f)


def lineup_complete():

    lineup = session["lineup"]

    return all(
        lineup[pos] is not None
        for pos in LINEUP_POSITIONS
    )


def get_available_players():

    drafted = []

    for value in session["lineup"].values():
        if value:
            drafted.append(value)

    return [
        p for p in PLAYERS
        if p["era"] == session["era"]
        and p["team"] == session["team"]
        and p["name"] not in drafted
    ]


def generate_candidates():

    pool = get_available_players()

    if len(pool) <= 3:
        return pool

    return random.sample(pool, 3)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/start")
def start():

    era = random.choice(list(ERAS.keys()))
    team = random.choice(ERAS[era])

    session["era"] = era
    session["team"] = team

    session["era_reroll"] = 1
    session["team_reroll"] = 1

    lineup = {}

    for pos in LINEUP_POSITIONS:
        lineup[pos] = None

    session["lineup"] = lineup

    return redirect("/draft")


@app.route("/draft")
def draft():

    if lineup_complete():
        return redirect("/result")

    return render_template(
        "draft.html",
        era=session["era"],
        team=session["team"],
        lineup=session["lineup"],
        candidates=generate_candidates(),
        era_reroll=session["era_reroll"],
        team_reroll=session["team_reroll"]
    )


@app.route("/player/<name>")
def choose_player(name):

    player = next(
        p for p in PLAYERS
        if p["name"] == name
    )

    possible_positions = []

    lineup = session["lineup"]

    for pos in player["positions"]:

        if pos == "SP":
            for slot in ["SP1", "SP2", "SP3"]:
                if lineup[slot] is None:
                    possible_positions.append(slot)

        elif pos == "RP":
            for slot in ["RP1", "RP2", "RP3"]:
                if lineup[slot] is None:
                    possible_positions.append(slot)

        else:
            if lineup[pos] is None:
                possible_positions.append(pos)

    session["selected_player"] = name

    return render_template(
        "position_select.html",
        player=player,
        positions=possible_positions
    )


@app.route("/assign/<position>")
def assign(position):

    lineup = session["lineup"]

    lineup[position] = session["selected_player"]

    session["lineup"] = lineup

    return redirect("/draft")


@app.route("/reroll-era")
def reroll_era():

    if session["era_reroll"] <= 0:
        return redirect("/draft")

    era = random.choice(list(ERAS.keys()))
    team = random.choice(ERAS[era])

    session["era"] = era
    session["team"] = team

    session["era_reroll"] -= 1

    return redirect("/draft")


@app.route("/reroll-team")
def reroll_team():

    if session["team_reroll"] <= 0:
        return redirect("/draft")

    era = session["era"]

    session["team"] = random.choice(
        ERAS[era]
    )

    session["team_reroll"] -= 1

    return redirect("/draft")


@app.route("/result")
def result():

    return render_template(
        "result.html",
        lineup=session["lineup"]
    )


if __name__ == "__main__":
    app.run(debug=True)
