from flask import Flask, render_template, request, session, redirect
import os
import json
import random
from datetime import datetime
from supabase import create_client


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("URL =", SUPABASE_URL)
print("KEY EXISTS =", bool(SUPABASE_KEY))

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

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
    
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start/<era>")
def start(era):

    session.clear()

    session["allow_next"] = True

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

    TRAITS = [
        {
            "id": "offense",
            "name": "공격 야구",
            "icon": "💥"
        },
        {
            "id": "defense",
            "name": "수비 야구",
            "icon": "🛡️"
        },
        {
            "id": "mountain",
            "name": "마운드 왕국",
            "icon": "⚾"
        },
        {
            "id": "closer",
            "name": "철벽 마무리",
            "icon": "🔒"
        },
        {
            "id": "smallball",
            "name": "스몰볼",
            "icon": "🎯"
        },
        {
            "id": "slugger",
            "name": "홈런 군단",
            "icon": "🔥"
        },
        {
            "id": "superstar",
            "name": "슈퍼스타 군단",
            "icon": "🌟"
        },
        {
            "id": "balanced",
            "name": "밸런스형",
            "icon": "⚙️"
        },
        {
            "id": "core",
            "name": "수비 코어",
            "icon": "🧱"
        },
        {
            "id": "bullpen",
            "name": "불펜 의존",
            "icon": "🚨"
        }
    ]

    session["trait_choices"] = random.sample(
        TRAITS,
        3
    )

    return redirect("/trait")

@app.route("/trait")
def trait():

    return render_template(
        "trait.html",
        traits=session["trait_choices"]
    )

@app.route("/select_trait/<trait_id>")
def select_trait(trait_id):

    session["selected_trait"] = trait_id

    return redirect("/next")

@app.route("/next")
def next_team():

    if not session.get("allow_next", False):
        return redirect("/team_view")

    session["allow_next"] = False

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

    session["allow_next"] = False

    if "current_team" not in session:
        return redirect("/")

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

    if session["assigned_this_round"] > 0:
        session["error"] = "선수를 배치한 후에는 리롤할 수 없습니다."
        return redirect("/team_view")

    if session["team_reroll"] <= 0:
        return redirect("/next")

    session["team_reroll"] -= 1

    session["used_teams"].remove(
        session["current_team"]
    )

    session["allow_next"] = True

    return redirect("/next")

@app.route("/assign_player", methods=["POST"])
def assign_player():

    player_id = request.form["player_id"]
    position = request.form["position"]

    used_players = session["used_players"]

    if player_id in used_players:
        session["error"] = "이미 배치한 선수입니다."
        return redirect("/team_view")

    player["era"] = session["actual_era"]

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

    # DH는 모든 야수 가능
    if position == "DH":
        if "SP" in player["positions"] or "RP" in player["positions"]:
            session["error"] = "투수는 DH에 배치할 수 없습니다."
            return redirect("/team_view")

    # DH 외에는 원래 포지션만 가능
    else:
        if position not in player["positions"]:
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
        return redirect("/result_loading")

    if session["assigned_this_round"] >= 3:
        session["assigned_this_round"] = 0
        session["allow_next"] = True
        return redirect("/next")

    return redirect("/team_view")
    
@app.route("/result")
def result():

    if "lineup" not in session:
        return redirect("/")

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

    wins = round(total_war * 1.2)

    bonus = 0

    trait = session.get("selected_trait","none")

    # 공격 야구
    if trait == "offense":

        hitter_war = 0

        for pos in [
            "C", "1B", "2B", "3B",
            "SS", "LF", "CF", "RF", "DH"
        ]:
            hitter_war += lineup[pos]["war"]

        if hitter_war >= 80:
            bonus += 3

    # 수비 야구
    elif trait == "defense":

        total = (
            lineup["SS"]["war"]
            + lineup["2B"]["war"]
            + lineup["CF"]["war"]
        )

        if total <= 15:
            bonus += 4

    # 마운드 왕국
    elif trait == "mountain":

        pitching = 0

        for p in lineup["SP"]:
            pitching += p["war"]

        for p in lineup["RP"]:
            pitching += p["war"]

        if pitching >= 40:
            bonus += 2

    # 철벽 마무리
    elif trait == "closer":

        rp = sum(
            p["war"]
            for p in lineup["RP"]
        )

        if rp <= 13:
            bonus += 3

    # 스몰볼
    elif trait == "smallball":

        total = (
            lineup["1B"]["war"]
            + lineup["3B"]["war"]
            + lineup["LF"]["war"]
            + lineup["RF"]["war"]
        )

        if total <= 25:
            bonus += 3

    # 홈런 군단
    elif trait == "slugger":

        total = (
            lineup["1B"]["war"]
            + lineup["3B"]["war"]
            + lineup["LF"]["war"]
            + lineup["RF"]["war"]
        )

        if total >= 37:
            bonus += 3

    # 슈퍼스타 군단
    elif trait == "superstar":

        count = 0

        for p in lineup["SP"]:
            if p["war"] >= 9:
                count += 1

        for p in lineup["RP"]:
            if p["war"] >= 9:
                count += 1

        for pos in [
            "C", "1B", "2B", "3B",
            "SS", "LF", "CF", "RF", "DH"
        ]:
            if lineup[pos]["war"] >= 9:
                count += 1

        if count >= 3:
            bonus += 5

    # 밸런스형
    elif trait == "balanced":

        ok = True

        for p in lineup["SP"]:
            if p["war"] < 6.5:
                ok = False

        for p in lineup["RP"]:
            if p["war"] < 6.5:
                ok = False

        for pos in [
            "C", "1B", "2B", "3B",
            "SS", "LF", "CF", "RF", "DH"
        ]:
            if lineup[pos]["war"] < 6.5:
                ok = False

        if ok:
            bonus += 4

    # 수비 코어
    elif trait == "core":

        total = (
            lineup["C"]["war"]
            + lineup["SS"]["war"]
            + lineup["CF"]["war"]
        )

        if total <= 15:
            bonus += 4

    # 불펜 의존
    elif trait == "bullpen":

        sp = sum(
            p["war"]
            for p in lineup["SP"]
        )

        rp = sum(
            p["war"]
            for p in lineup["RP"]
        )

        if rp + 10 > sp:
            bonus += 4

    # 시대 통일
    elif session["era"] == "all_time":

        eras = []

        for p in lineup["SP"]:
            eras.append(p["era"])

        for p in lineup["RP"]:
            eras.append(p["era"])

        for pos in [
            "C","1B","2B","3B",
            "SS","LF","CF","RF","DH"
        ]:    
            eras.append(
                lineup[pos]["era"]
            )

        if len(set(eras)) == 1:
            bonus += 10

    wins += bonus

    if wins > 144:
        wins = 144

    losses = 144 - wins

    record = f"{wins}-{losses}"

    if wins >= 140:
        grade = "SS"

    elif wins >= 130:
        grade = "S"

    elif wins >= 120:
        grade = "A"

    elif wins >= 110:
        grade = "B"

    elif wins >= 90:
        grade = "C"

    else:
        grade = "D"

    session["final_wins"] = wins
    session["final_losses"] = losses
    session["final_grade"] = grade
    session["trait_bonus"] = bonus

    return render_template(
        "result.html",
        lineup=lineup,
        wins=wins,
        losses=losses,
        record=record,
        grade=grade,
        bonus=bonus,
        trait=trait
    )
@app.route("/result_loading")
def result_loading():

    if "lineup" not in session:
        return redirect("/")

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

    wins = round(total_war * 1.2)

    if wins > 144:
        wins = 144

    return render_template(
        "result_loading.html",
        wins=wins
    )

def save_record(name, wins, losses, grade):

    supabase.table("records").insert({

        "name": name,
        "wins": wins,
        "losses": losses,
        "grade": grade,
        "date": datetime.now().strftime("%Y-%m-%d")

    }).execute()

@app.route("/save_record", methods=["POST"])
def save_record_route():

    if "final_wins" not in session:
        return redirect("/")

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

        response = (
            supabase
            .table("records")
            .select("*")
            .order("wins", desc=True)
            .limit(100)
            .execute()
        )

        records = response.data

        print(
            "LOADED RECORDS:",
            len(records)
        )

    except Exception as e:

        print(
            "RANKING ERROR:",
            e
        )

        records = []

    return render_template(
        "ranking.html",
        records=records
    )
    
if __name__ == "__main__":
    app.run(debug=True)
