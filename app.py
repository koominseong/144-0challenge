from flask import Flask, render_template, request, session, redirect
import os
import json
import random

app = Flask(__name__)
app.secret_key = "kbo1440"

def get_team_names():

    era = session.get("era", "2010s")

    if era == "2000s":
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
            "Heroes": "현대 유니콘스"
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

    # 2020s / all_time 기본
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

    era = session.get("era")

    if era == "all_time":
        era = random.choice(["2010s", "2020s"])

    path = os.path.join(
        "Data",
        era,
        f"{team}.json"
    )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
 
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start/<era>")
def start(era):

    session.clear()

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

    session["team_reroll"] = 1

    return redirect("/next")


@app.route("/next")
def next_team():

    if "era" not in session:
        return redirect("/")

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

    # 👉 여기서 바로 team.html 말고 loading으로
    return render_template(
        "loading.html",
        final_team=team,
        team_name=team_names[team]
        era=session["era"]
    )

@app.route("/team_view")
def team_view():

    players = load_team(session["current_team"])

    return render_template(
        "team.html",
        team_name=get_team_names()[session["current_team"]],
        team_key=session["current_team"],
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
        return "이미 배치한 선수"

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

    # 이번 라운드 배치 수 증가
    session["assigned_this_round"] += 1

    session["lineup"] = lineup

    if player_id not in used_players:
        used_players.append(player_id)

    session["used_players"] = used_players

    session.modified = True

    # 게임 종료 체크
    filled = len(lineup["SP"]) + len(lineup["RP"])

    for pos in [
        "C", "1B", "2B", "3B", "SS",
        "LF", "CF", "RF", "DH"
    ]:
        if lineup[pos]:
            filled += 1

    if filled >= 15:
        return redirect("/result")

    # 이번 팀에서 3명 다 배치했으면 다음 팀
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
        "C","1B","2B","3B","SS",
        "LF","CF","RF","DH"
    ]:
        if lineup[pos]:
            total_war += lineup[pos]["war"]

    if total_war >= 90:
        grade = "S"

    elif total_war >= 80:
        grade = "A"

    elif total_war >= 70:
        grade = "B"

    elif total_war >= 60:
        grade = "C"

    else:
        grade = "D"

    return render_template(
        "result.html",
        lineup=lineup,
        total_war=round(total_war, 1),
        grade=grade
    )


if __name__ == "__main__":
    app.run(debug=True)
