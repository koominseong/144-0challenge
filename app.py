from flask import Flask, render_template, request, session, redirect
import os
import json
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "kbo1440"

def get_team_names():

    era = session.get("actual_era", session.get("era", "2010s"))

    if era == "2000s":
        return {
            "Bears": "두산 베어스",
            "LG": "LG 트윈스",
            "Lions": "삼성 라이온즈",
            "Tigers": "KIA 타이거즈",
            "Eagles": "한화 이글스",
            "Wyverns": "SK 와이번스",
            "Giants": "롯데 자이언츠",
            "Unicorns": "현대 유니콘스"
        }

    if era == "2010s":
        return {
            "Bears": "두산 베어스",
            "LG": "LG 트윈스",
            "Lions": "삼성 라이온즈",
            "Tigers": "KIA 타이거즈",
            "Eagles": "한화 이글스",
            "Wyverns": "SK 와이번스",
            "Giants": "롯데 자이언츠",
            "Wiz": "KT 위즈",
            "Dinos": "NC 다이노스",
            "Heroes": "넥센 히어로즈"
        }

    return {
        "Bears": "두산 베어스",
        "LG": "LG 트윈스",
        "Lions": "삼성 라이온즈",
        "Tigers": "KIA 타이거즈",
        "Eagles": "한화 이글스",
        "Landers": "SSG 랜더스",
        "Giants": "롯데 자이언츠",
        "Wiz": "KT 위즈",
        "Dinos": "NC 다이노스",
        "Heroes": "키움 히어로즈"
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

    era = session.get("actual_era", session["era"])

    path = os.path.join(
        "Data",
        era,
        f"{team}.json"
    )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_record(name, wins, losses, grade):

    record_file = "records.json"

    try:
        with open(record_file, "r", encoding="utf-8") as f:
            records = json.load(f)

    except:
        records = []

    records.append({
        "name": name,
        "wins": wins,
        "losses": losses,
        "grade": grade,
        "date": datetime.now().strftime("%Y-%m-%d")
    })

    records.sort(
        key=lambda x: x["wins"],
        reverse=True
    )

    records = records[:100]

    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(
            records,
            f,
            ensure_ascii=False,
            indent=2
        )
 
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start/<era>")
def start(era):

    session.clear()

    if era == "all_time":
        session["actual_era"] = random.choice(
            ["2000s", "2010s", "2020s"]
        )

    session["era"] = era
    
    session["assigned_this_round"] = 0

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

    session["team_reroll"] = 2

    return redirect("/next")


@app.route("/next")
def next_team():

    if "era" not in session:
        return redirect("/")

    if session["era"] == "all_time":

        session["actual_era"] = random.choice(
            ["2000s", "2010s", "2020s"]
        )

    else:

        session["actual_era"] = session["era"]

    team_names = get_team_names()

    available = [
        team for team in team_names.keys()
        if team not in session["used_teams"]
    ]

    if not available:
        return redirect("/result")

    team = random.choice(available)

    session["current_team"] = team
    session["used_teams"].append(team)

    return render_template(
        "loading.html",
        team_name=team_names[team],
        era=session["era"],
        actual_era=session.get("actual_era")
    )

@app.route("/team_view")
def team_view():

    players = load_team(session["current_team"])

    error = session.pop("error", None)

    return render_template(
        "team.html",
        team_name=get_team_names()[session["current_team"]],
        team_key=session["current_team"],
        players=players,
        lineup=session["lineup"],
        rerolls=session["team_reroll"],
        error=error
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

    used_players = session.get(
        "used_players",
        []
    )

    selected_players = [
        p
        for p in players
        if p["id"] in session["selected_players"]
        and p["id"] not in used_players
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

    used_players = session["used_players"]

    if player_id in used_players:
        session["error"] = "이미 배치한 선수입니다."
        return redirect("/team_view")

    players = load_team(session["current_team"])

    player = next(
        p for p in players
        if p["id"] == player_id
    )

    lineup = session["lineup"]

    # 같은 이름 선수 중복 방지
    existing_names = set()

    for p in lineup["SP"]:
        existing_names.add(p["name"])

    for p in lineup["RP"]:
        existing_names.add(p["name"])

    for pos in [
        "C", "1B", "2B", "3B", "SS",
        "LF", "CF", "RF", "DH"
    ]:
        if lineup[pos]:
            existing_names.add(
                lineup[pos]["name"]
            )

    if player["name"] in existing_names:
        session["error"] = "동일 이름 선수는 중복 배치할 수 없습니다."
        return redirect("/team_view")

    if position == "DH":
        if (
            "SP" in player["positions"]
            or
            "RP" in player["positions"]
        ):
            session["error"] = "투수는 DH에 배치할 수 없습니다."
            return redirect("/team_view")
        elif position not in player["positions"]:
            session["error"] = "배치 불가한 포지션입니다."
            return redirect("/team_view")

    if position == "SP":

        if len(lineup["SP"]) >= 3:
            session["error"] = "선발투수 자리가 가득 찼습니다."
            return redirect("/team_view")

        lineup["SP"].append(player)

    elif position == "RP":

        if len(lineup["RP"]) >= 3:
            session["error"] = "불펜 자리가 가득 찼습니다."
            return redirect("/team_view")
        
        lineup["RP"].append(player)

    else:

        if lineup[position] is not None:
            session["error"] = "이미 사용 중인 포지션입니다."
            return redirect("/team_view")

        lineup[position] = player

    session["assigned_this_round"] += 1

    session["lineup"] = lineup

    if player_id not in used_players:
        used_players.append(player_id)

    session["used_players"] = used_players

    session.modified = True

    filled = len(lineup["SP"]) + len(lineup["RP"])

    for pos in [
        "C", "1B", "2B", "3B", "SS",
        "LF", "CF", "RF", "DH"
    ]:
        if lineup[pos]:
            filled += 1

    if filled >= 15:
        return redirect("/result")

    if session["assigned_this_round"] >= 3:
        session["assigned_this_round"] = 0
        return redirect("/next")

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
        "C", "1B", "2B", "3B", "SS",
        "LF", "CF", "RF", "DH"
    ]:
        if lineup[pos]:
            total_war += lineup[pos]["war"]

    # 승패 환산
    wins = round(total_war * 1.25)

    if wins > 144:
        wins = 144

    losses = 144 - wins

    record = f"{wins}-{losses}"

    session["final_wins"] = wins
    session["final_losses"] = losses
    session["final_grade"] = grade

    # 등급
    if wins >= 140:
        grade = "SS"

    elif wins >= 130:
        grade = "S"

    elif wins >= 115:
        grade = "A"

    elif wins >= 100:
        grade = "B"

    elif wins >= 85:
        grade = "C"

    else:
        grade = "D"

    return render_template(
        "result.html",
        lineup=lineup,
        total_war=round(total_war, 1),
        wins=wins,
        losses=losses,
        record=record,
        grade=grade
    )

@app.route("/save_record", methods=["POST"])
def save_record_route():

    name = request.form["name"]

    save_record(
        name,
        session["final_wins"],
        session["final_losses"],
        session["final_grade"]
    )

    return redirect("/ranking")

@app.route("/ranking")
def ranking():

    try:
        with open(
            "records.json",
            "r",
            encoding="utf-8"
        ) as f:

            records = json.load(f)

    except:
        records = []

    return render_template(
        "ranking.html",
        records=records
    )

if __name__ == "__main__":
    app.run(debug=True)
