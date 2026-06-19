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

    session["selected_behavior"] = None
    session["behavior_choices"] = []
    session["next_team_preview"] = None
    session["trait_count"] = 3
    session["fixed_era_used"] = False
    session["round_count"] = 0
    session["fa_used"] = False
    session["trade_used"] = False
    session["fungo_used"] = False
    session["cheerleader_used"] = False
    session["boost_player"] = None
    session["fixed_era_used"] = False
    session["fixed_era"] = None
    session["released_players"] = []
    session["first_round_bonus"] = False
    session["transfer_mode"] = False
    session["released_players"] = []
    session["transfer_used"] = False

    return redirect("/behavior_trait")

@app.route("/behavior_trait")
def behavior_trait():

    if session.get("selected_behavior"):
        return redirect("/next")

    BEHAVIORS = [

        {
            "id":"owner",
            "name":"돈많은 구단주",
            "desc":"리롤 횟수 +2"
        },

        {
            "id":"fa_god",
            "name":"FA의 신",
            "desc":"3번째 팀을 원하는 팀으로 변경"
        },

        {
            "id":"trade_hunter",
            "name":"트레이드 헌터",
            "desc":"2차 특성 선택 전 선수 1명 교체"
        },

        {
            "id":"pitching_dynasty",
            "name":"선발 왕조",
            "desc":"RP 한 칸 → SP"
        },

        {
            "id":"recruit_master",
            "name":"영입 마스터",
            "desc":"첫 팀 4명 선택"
        },

        {
            "id":"cheerleader",
            "name":"응원단장",
            "desc":"선수 1명 WAR 1.1배"
        },

        {
            "id":"transfer_god",
            "name":"이적의 신",
            "desc":"6라운드 진행"
        },

        {
            "id":"fungo",
            "name":"지옥의 펑고",
            "desc":"내야수 포지션 변경 가능"
        },

        {
            "id":"recorder",
            "name":"신들린 기록원",
            "desc":"1라운드 WAR TOP3 공개"
        },

        {
            "id":"future_scout",
            "name":"미래를 보는 스카우트",
            "desc":"다음 팀 공개"
        },

        {
            "id":"genius_manager",
            "name":"천재 감독",
            "desc":"2차 특성 선택 시 5개 제시"
        },

        {
            "id":"time_paradox",
            "name":"타임 패러독스",
            "desc":"올타임에서 원하는 시대 1회 고정"
        }
    ]

    if not session["behavior_choices"]:
        session["behavior_choices"] = random.sample(
            BEHAVIORS,
            3
        )

    return render_template(
        "behavior_trait.html",
        traits=session["behavior_choices"]
    )

@app.route("/select_behavior/<behavior_id>")
def select_behavior(behavior_id):

    valid_ids = [
        t["id"]
        for t in session["behavior_choices"]
    ]

    if behavior_id not in valid_ids:
        return redirect("/behavior_trait")

    session["selected_behavior"] = behavior_id

    if behavior_id == "owner":
        session["team_reroll"] = 4

    elif behavior_id == "genius_manager":
        session["trait_count"] = 5

    elif behavior_id == "pitching_dynasty":

        lineup = session["lineup"]

        lineup["SP"] = []
        lineup["RP"] = []

        session["lineup"] = lineup

        session["sp_limit"] = 4
        session["rp_limit"] = 2

    else:

        session["sp_limit"] = 3
        session["rp_limit"] = 3

    session["behavior_choices"] = []

    return redirect("/next")

@app.route("/trait_team")
def trait_team():

    if session.get("selected_trait"):
        return redirect("/team_view")

    TRAITS = [
        {"id":"offense","name":"공격 야구","icon":"💥"},
        {"id":"defense","name":"수비 야구","icon":"🛡️"},
        {"id":"mountain","name":"마운드 왕국","icon":"⚾"},
        {"id":"closer","name":"철벽 마무리","icon":"🔒"},
        {"id":"smallball","name":"스몰볼","icon":"🎯"},
        {"id":"slugger","name":"홈런 군단","icon":"🔥"},
        {"id":"superstar","name":"슈퍼스타 군단","icon":"🌟"},
        {"id":"balanced","name":"밸런스형","icon":"⚙️"},
        {"id":"core","name":"수비 코어","icon":"🧱"},
        {"id":"bullpen","name":"불펜 의존","icon":"🚨"},
        {"id":"era_master","name":"왕조 건","icon":"🕰️"}
    ]

    traits_pool = TRAITS.copy()

    if session["era"] != "all_time":
        traits_pool = [
            t
            for t in traits_pool
            if t["id"] != "era_master"
        ]

    if not session.get("trait_choices"):
        session["trait_choices"] = random.sample(
            traits_pool,
            session.get("trait_count", 3)
        )

    return render_template(
        "trait_team.html",
        traits=session["trait_choices"]
    )

@app.route("/select_trait_team/<trait_id>")
def select_trait_team(trait_id):

    if "trait_choices" not in session:
        return redirect("/")

    valid_ids = [
        t["id"]
        for t in session["trait_choices"]
    ]

    if trait_id not in valid_ids:
        return redirect("/trait_team")

    session["selected_trait"] = trait_id

    session.pop("trait_choices", None)

    return redirect("/team_view")
    
@app.route("/next")
def next_team():

    if not session.get("allow_next", False):
        return redirect("/team_view")

    session["allow_next"] = False

    # 6명 채웠는데 아직 특성 안 골랐으면
    filled = (
        len(session["lineup"]["SP"])
        + len(session["lineup"]["RP"])
    )

    for pos in [
        "C","1B","2B","3B",
        "SS","LF","CF","RF","DH"
    ]:
        if session["lineup"][pos]:
            filled += 1

    if (
        filled >= 6
        and "selected_trait" not in session
    ):
        return redirect("/trait_team")

    if "era" not in session:
        return redirect("/")

    if session["era"] == "all_time":
        if session.get("fixed_era"):
            session["actual_era"] = session["fixed_era"]
            session["fixed_era"] = None
        else:
            session["actual_era"] = random.choice(
                ["2000s","2010s","2020s"]
            )

    else:

        session["actual_era"] = session["era"]

    team_names = get_team_names()

    if session.get("transfer_mode"):

        for player_id in session["released_players"]:

            if player_id in session["used_players"]:
                session["used_players"].remove(player_id)

        session["released_players"] = []

    available = [
        team for team in team_names.keys()
        if team not in session["used_teams"]
    ]

    if not available:
        return redirect("/result")

    team = random.choice(available)

    if (
        session.get("selected_behavior")
        == "fa_god"
        and session["round_count"] == 3
        and not session["fa_used"]
    ):
        return redirect("/fa_select")

    if session.get("selected_behavior") == "future_scout":
        remain = [
            t for t in available
            if t != team
        ]
        
        if remain:
            session["next_team_preview"] = random.choice(remain)

    session["current_team"] = team
    session["used_teams"].append(team)

    return render_template(
        "loading.html",
        team_name=team_names[team],
        era=session["era"],
        actual_era=session.get("actual_era")
    )

@app.route("/fa_select")
def fa_select():

    team_names = get_team_names()

    available = [
        t
        for t in team_names.keys()
        if t not in session["used_teams"]
    ]

    return render_template(
        "fa_select.html",
        teams=available,
        team_names=team_names
    )

@app.route("/fa_pick/<team>")
def fa_pick(team):

    session["fa_used"] = True

    session["current_team"] = team

    session["used_teams"].append(team)

    return render_template(
        "loading.html",
        team_name=get_team_names()[team],
        era=session["era"],
        actual_era=session.get("actual_era")
    )

@app.route("/fix_era/<era>")
def fix_era(era):

    if session["fixed_era_used"]:
        return redirect("/team_view")

    session["fixed_era"] = era

    session["fixed_era_used"] = True

    return redirect("/team_view")

@app.route("/boost_player/<player_id>")
def boost_player(player_id):

    if session.get("boost_player"):
        return redirect("/team_view")

    session["boost_player"] = player_id

    return redirect("/team_view")

@app.route("/transfer_release")
def transfer_release():

    return render_template(
        "transfer_release.html",
        lineup=session["lineup"]
    )

@app.route("/release_player/<player_id>")
def release_player(player_id):

    lineup = session["lineup"]

    for p in lineup["SP"][:]:
        if p["id"] == player_id:
            lineup["SP"].remove(p)

    for p in lineup["RP"][:]:
        if p["id"] == player_id:
            lineup["RP"].remove(p)

    for pos in [
        "C","1B","2B","3B",
        "SS","LF","CF","RF","DH"
    ]:
        if (
            lineup[pos]
            and lineup[pos]["id"] == player_id
        ):
            lineup[pos] = None

    session["lineup"] = lineup

    released = session["released_players"]

    if player_id not in released:
        released.append(player_id)

    session["released_players"] = released

    if len(released) >= 3:

        session["transfer_mode"] = True
        session["transfer_used"] = True
        session["allow_next"] = True

        return redirect("/next")

    return redirect("/transfer_release")

@app.route("/team_view")
def team_view():

    session["allow_next"] = False

    if "current_team" not in session:
        return redirect("/")

    players = load_team(session["current_team"])

    top3 = None
    if (
        session.get("selected_behavior")
        == "recorder"
        and session["round_count"] == 1
    ):
        top3 = sorted(
            players,
            key=lambda x:x["war"],
            reverse=True
        )[:3]

    error = session.pop("error", None)
        
    return render_template(
        "team.html",
        team_name=get_team_names()[session["current_team"]],
        team_key=session["current_team"],
        players=players,
        lineup=session["lineup"],
        rerolls=session["team_reroll"],
        error=error,
        next_team_preview=get_team_names().get(
            session.get("next_team_preview"),
            session.get("next_team_preview")
        ),
        top3=top3
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

    players = load_team(session["current_team"])

    player = next(
        p for p in players
        if p["id"] == player_id
    )
    
    player["era"] = session["actual_era"]
    
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

        if len(lineup["SP"]) >= session.get("sp_limit",3):
            session["error"] = "선발투수 자리가 가득 찼습니다."
            return redirect("/team_view")

        lineup["SP"].append(player)

    elif position == "RP":

        if len(lineup["RP"]) >= session.get("rp_limit",3):
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
        if (
            session.get("selected_behavior")
            == "transfer_god"
            and not session["transfer_used"]
        ):
            return redirect("/transfer_release")

        return redirect("/result_loading")

    limit = 3
    if (
        session.get("selected_behavior")
        == "recruit_master"
    ):
        if session["round_count"] == 1:
            limit = 4
        elif session["round_count"] == 5:
            limit = 2
    if session["assigned_this_round"] >= limit:
        session["assigned_this_round"] = 0
        session["round_count"] += 1
        session["allow_next"] = True
        return redirect("/next")

    if session.get("transfer_mode"):

        count = len(session["released_players"])

        if count >= 3:

            session["transfer_mode"] = False

            return redirect("/result_loading")
    
    return redirect("/team_view")
    
@app.route("/result")
def result():

    if "lineup" not in session:
        return redirect("/")

    lineup = session["lineup"]

    boost_player = session.get("boost_player")

    total_war = 0

    for player in lineup["SP"]:

        war = player["war"]

        if (
            boost_player
            and player["id"] == boost_player
        ):
            war *= 1.1

        total_war += war

    for player in lineup["RP"]:

        war = player["war"]

        if (
            boost_player
            and player["id"] == boost_player
        ):
            war *= 1.1

        total_war += war

    for pos in [
        "C","1B","2B","3B",
        "SS","LF","CF","RF","DH"
    ]:

        if lineup[pos]:

            war = lineup[pos]["war"]

            if (
                boost_player
                and lineup[pos]["id"] == boost_player
            ):
                war *= 1.1

            total_war += war

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
    elif trait == "era_master":

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
