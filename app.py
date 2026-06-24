from flask import Flask, render_template, request, session, redirect
import os
import json
import random
from datetime import datetime
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise Exception("SECRET_KEY missing")

BEIJING_2008 = {
    "오승환",
    "장원삼",
    "김광현",
    "정대현",
    "한기주",
    "윤석민",
    "권혁",
    "봉중근",
    "송승준",
    "류현진",

    "진갑용",
    "강민호",

    "고영민",
    "박진만",
    "정근우",
    "이대호",
    "김민재",
    "김동주",
    "이승엽",

    "이용규",
    "이택근",
    "이진영",
    "이종욱",
    "김현수"
}

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

ALLOWED_ERAS = ["all_time"]

@app.route("/start")
def start():

    era = "all_time"

    if era not in ALLOWED_ERAS:
        return redirect("/")

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
        return redirect("/team_view")

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
            "desc":"2차 특성 선택 전 선수 1명 교체(구현 중)"
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
            "desc":"선수 1명 능력치 소폭 증가"
        },

        {
            "id":"transfer_god",
            "name":"이적의 신",
            "desc":"6라운드 진행, 3명 방출"
        },

        {
            "id":"fungo",
            "name":"지옥의 펑고",
            "desc":"내야수 1명 내야 포지션 변경 가능(구현 중)"
        },

        {
            "id":"recorder",
            "name":"신들린 기록원",
            "desc":"2라운드 능력치 TOP3 공개"
        },

        {
            "id":"future_scout",
            "name":"미래를 보는 스카우트",
            "desc":"다음 팀 미리 공개"
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
        {
            "id":"million_miracle",
            "name":"천만의 기적",
            "icon":"💰",
            "desc":"2024~2025 시즌 선수 5명 이상 배치 (+4승)"
        },
    
        {
            "id":"beijing2008",
            "name":"2008",
            "icon":"🥇",
            "desc":"베이징 올림픽 엔트리 선수 13명 이상 (+6승)"
        },
    
        {
            "id":"k_baseball",
            "name":"K-Baseball",
            "icon":"🇰🇷",
            "desc":"전 선수 한국인 (+3승)"
        },
    
        {
            "id":"hell_defense",
            "name":"수비는 지옥이다",
            "icon":"😱",
            "desc":"SP 3명 SO 합 450 이하 (+4승)"
        },
    
        {
            "id":"bullpen",
            "name":"불펜 의존",
            "icon":"🚨",
            "desc":"RP WAR 합 +10 > SP WAR 합 (+4승)"
        },
    
        {
            "id":"dynasty",
            "name":"왕조 구축",
            "icon":"👑",
            "desc":"전 선수 같은 년대 (+6승)"
        },
    
        {
            "id":"balanced",
            "name":"밸런스형",
            "icon":"⚖️",
            "desc":"전 선수 WAR 6.5 이상 (+4승)"
        },
    
        {
            "id":"hr_era",
            "name":"홈런의 시대",
            "icon":"💥",
            "desc":"타자 홈런 합 200개 이상 (+3승)"
        },
    
        {
            "id":"small_hr",
            "name":"딱총 야구",
            "icon":"🎯",
            "desc":"타자 홈런 합 120개 이하 (+5승)"
        },
    
        {
            "id":"new_jokka",
            "name":"New-JOKKA",
            "icon":"🔥",
            "desc":"RP 평균 ERA 1.50 이하 (+3승)"
        },
    
        {
            "id":"new_kill",
            "name":"New-KILL 라인",
            "icon":"⚔️",
            "desc":"SP 평균 ERA 2.50 이하 (+3승)"
        },
    
        {
            "id":"avg_win",
            "name":"타율=승리",
            "icon":"📈",
            "desc":"타율 0.300 이상 타자 7명 이상 (+3승)"
        },
    
        {
            "id":"def_core",
            "name":"수비 코어",
            "icon":"🧱",
            "desc":"C+2B+SS+CF WAR 합 25 이하 (+4승)"
        },
    
        {
            "id":"captain",
            "name":"주장의 품격",
            "icon":"🎖️",
            "desc":"주장 선수 7명 이상 (+3승)"
        },
    
        {
            "id":"leader",
            "name":"구심점 야구",
            "icon":"⭐",
            "desc":"주장 선수 정확히 1명 (+5승)"
        },
    
        {
            "id":"ops18",
            "name":"18의 향연",
            "icon":"📊",
            "desc":"OPS 0.900 이상 타자 8명 이상 (+3승)"
        },
    
        {
            "id":"foreign",
            "name":"외인은 전설이다",
            "icon":"🌎",
            "desc":"외국인 선수 7명 이상 (+4승)"
        },
    
        {
            "id":"dirtyball",
            "name":"더러운 볼",
            "icon":"🌀",
            "desc":"SP+RP SO 합 777 이상 (+4승)"
        },
    
        {
            "id":"timetravel",
            "name":"시대를 뛰어넘은 야구",
            "icon":"⏳",
            "desc":"전 선수 서로 다른 연도 (+3승)"
        },
    
        {
            "id":"superstar",
            "name":"스타 플레이어",
            "icon":"🌟",
            "desc":"WAR 9.0 이상 선수 3명 이상 (+2승)"
        },
    
        {
            "id":"one_man",
            "name":"원맨팀",
            "icon":"🎭",
            "desc":"WAR 1위와 2위 차이 1.5 이상 (+3승)"
        },
    
        {
            "id":"doyoung",
            "name":"도영맘",
            "icon":"🐯",
            "desc":"김도영을 유격수로 배치 (+4승)"
        },
    
        {
            "id":"power_ss",
            "name":"거포 유격수",
            "icon":"🚀",
            "desc":"유격수 OPS 0.900 이상 (+3승)"
        },
    
        {
            "id":"power_cf",
            "name":"거포 중견수",
            "icon":"🏹",
            "desc":"중견수 OPS 0.900 이상 (+3승)"
        },
    
        {
            "id":"nohit_sp",
            "name":"무실점 선발",
            "icon":"🛡️",
            "desc":"SP 평균 ERA 1.50 이하 (+4승)"
        },
    
        {
            "id":"nohit_rp",
            "name":"무실점 불펜",
            "icon":"🔒",
            "desc":"RP 평균 ERA 0.90 이하 (+4승)"
        },
    
        {
            "id":"tablesetter",
            "name":"테이블 세터",
            "icon":"🏃",
            "desc":"2B+SS+CF AVG 평균 0.320 이상 (+3승)"
        },
    
        {
            "id":"acekingdom",
            "name":"에이스 왕국",
            "icon":"👑",
            "desc":"SP WAR 합 25 이상 (+3승)"
        },
    
        {
            "id":"ks_dna",
            "name":"한국시리즈 DNA",
            "icon":"🏆",
            "desc":"주장 5명 이상 + WAR 8 이상 선수 5명 이상 (+4승)"
        },
    
        {
            "id":"gold_generation",
            "name":"황금 세대",
            "icon":"✨",
            "desc":"같은 연도 선수 5명 이상 (+3승)"
        }
    ]

    traits_pool = TRAITS.copy()

    if not session.get("trait_choices"):
        session["trait_choices"] = random.sample(
            traits_pool,
            session.get("trait_count", 3)
        )

    return render_template(
        "trait_team.html",
        trait=session["trait_choices"]
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

    session["allow_next"] = True

    session.modified = True

    return redirect("/next")
    
@app.route("/next")
def next_team():

    if not session.get("allow_next", False):
        return redirect("/team_view")

    session["allow_next"] = False

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
                ["2000s", "2010s", "2020s"]
            )

    else:

        session["actual_era"] = session["era"]

    team_names = get_team_names()

    if session.get("transfer_mode"):

        for player_id in session["released_players"]:

            if player_id in session["used_players"]:
                session["used_players"].remove(player_id)

        session["released_players"] = []

    available = []

    for team in team_names.keys():

        unique_id = (
            f"{session['actual_era']}|{team}"
        )

        if unique_id not in session["used_teams"]:
            available.append(team)

    current_team = session.get("current_team")

    if current_team in available:
        available.remove(current_team)

    if not available:
        return redirect("/result")

    if (
        session.get("selected_behavior") == "fa_god"
        and session["round_count"] == 2
        and not session["fa_used"]
    ):
        return redirect("/fa_select")

    if session.get("selected_behavior") == "future_scout":

        preview = session.get("next_team_preview")

        if preview and preview in available:

            team = preview

        else:

            team = random.choice(available)

        remain = [
            t for t in available
            if t != team
        ]

        if remain:
            session["next_team_preview"] = random.choice(remain)
        else:
            session["next_team_preview"] = None

    else:

        team = random.choice(available)

    session["current_team"] = team

    session["used_teams"].append(
        f"{session['actual_era']}|{team}"
    )

    session.modified = True

    return render_template(
        "loading.html",
        team_name=team_names[team],
        era=session["era"],
        actual_era=session.get("actual_era")
    )
    
@app.route("/fa_select")
def fa_select():

    if session.get("selected_behavior") != "fa_god":
        return redirect("/team_view")
        
    if session.get("fa_used"):
        return redirect("/team_view")

    if (
        session.get("selected_behavior")
        != "fa_god"
    ):
        return redirect("/team_view")

    teams = []

    for era in ["2000s", "2010s", "2020s"]:

        era_path = os.path.join(
            "Data",
            era
        )

        if not os.path.exists(era_path):
            continue

        for team_file in os.listdir(era_path):

            if not team_file.endswith(".json"):
                continue

            team_key = team_file[:-5]

            try:

                old_era = session.get("actual_era")

                session["actual_era"] = era

                display_name = get_team_names().get(
                    team_key,
                    team_key
                )

                if old_era:
                    session["actual_era"] = old_era

            except:

                display_name = team_key

            teams.append({
                "id": f"{era}|{team_key}",
                "display": display_name,
                "era": era,
                "file": f"{era}/{team_file}"
            })

    teams.sort(
        key=lambda x: (
            x["era"],
            x["display"]
        )
    )

    return render_template(
        "fa_select.html",
        teams=teams
    )


@app.route("/fa_pick/<path:team_id>")
def fa_pick(team_id):

    if session.get("fa_used"):
        return redirect("/team_view")

    try:

        era, team = team_id.split("|")

    except:

        return redirect("/fa_select")

    session["fa_used"] = True

    session["actual_era"] = era

    session["current_team"] = team

    used = session.get(
        "used_teams",
        []
    )

    unique_id = f"{era}|{team}"

    if unique_id not in used:
        used.append(unique_id)

    session["used_teams"] = used

    return render_template(
        "loading.html",
        team_name=get_team_names().get(
            team,
            team
        ),
        era=session["era"],
        actual_era=era
    )
    
@app.route("/fix_era/<era>")
def fix_era(era):

    if session.get("selected_behavior") != "time_paradox":
        return redirect("/team_view")

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

    if session.get("transfer_used"):
        return redirect("/team_view")

    if (
        session.get("selected_behavior")
        != "transfer_god"
    ):
        return redirect("/team_view")
        
    players = []

    lineup = session["lineup"]

    for p in lineup["SP"]:
        players.append(p)

    for p in lineup["RP"]:
        players.append(p)

    for pos in [
        "C","1B","2B","3B",
        "SS","LF","CF","RF","DH"
    ]:
        if lineup[pos]:
            players.append(lineup[pos])

    return render_template(
        "transfer_release.html",
        players=players,
        released_count=len(
            session["released_players"]
        )
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

    current_key = (
        f"{session.get('actual_era')}|"
        f"{session.get('current_team')}"
    )

    if current_key in session["used_teams"]:
        session["used_teams"].remove(current_key)

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
        if session["round_count"] == 0:
            limit = 4
        elif session["round_count"] == 4:
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

    wins = round(total_war * 1.19)

    bonus = 0

    all_players = []
    all_players.extend(lineup["SP"])
    all_players.extend(lineup["RP"])
        
    for pos in [
        "C","1B","2B","3B",
        "SS","LF","CF","RF","DH"
    ]:
        all_players.append(lineup[pos])

    trait = session.get("selected_trait","none")

    # 천만의 기적
    if trait == "miracle":

        cnt = sum(
            1 for p in all_players
            if p["Year"] in [2024, 2025]
        )

        if cnt >= 5:
            bonus += 4
    
    elif trait == "beijing2008":
        
        cnt = sum(
            1 for p in all_players
            if p["name"] in BEIJING_2008
        )
    
        if cnt >= 13:
            bonus += 6

    # K-Baseball
    elif trait == "kbaseball":

        if all(
            p.get("Korean", False)
            for p in all_players
        ):
            bonus += 3
    
    
    # 수비는 지옥이다
    elif trait == "defense_hell":
    
        if sum(
            p.get("SO",0)
            for p in lineup["SP"]
        ) <= 450:
            bonus += 4
    
    
    # 불펜 의존
    elif trait == "bullpen_depend":
    
        sp = sum(p["war"] for p in lineup["SP"])
        rp = sum(p["war"] for p in lineup["RP"])
    
        if rp + 10 > sp:
            bonus += 4
    
    
    # 왕조 구축
    elif trait == "dynasty":
    
        decades = set()
    
        for p in all_players:
            decades.add(
                (p["Year"] // 10) * 10
            )
    
        if len(decades) == 1:
            bonus += 6
    
    
    # 밸런스형
    elif trait == "balanced":
    
        if all(
            p["war"] >= 6.5
            for p in all_players
        ):
            bonus += 4
    
    
    # 홈런의 시대
    elif trait == "homerun_era":
    
        hitters = [
            lineup[pos]
            for pos in [
                "C","1B","2B","3B",
                "SS","LF","CF","RF","DH"
            ]
        ]
    
        if sum(
            p.get("HR",0)
            for p in hitters
        ) >= 200:
            bonus += 3
    
    
    # 딱총 야구
    elif trait == "smallball":
    
        hitters = [
            lineup[pos]
            for pos in [
                "C","1B","2B","3B",
                "SS","LF","CF","RF","DH"
            ]
        ]
    
        if sum(
            p.get("HR",0)
            for p in hitters
        ) <= 120:
            bonus += 5
    
    
    # New-JOKKA
    elif trait == "new_jokka":
    
        eras = [
            p["ERA"]
            for p in lineup["RP"]
            if p.get("ERA") is not None
        ]
    
        if eras and sum(eras)/len(eras) <= 1.5:
            bonus += 3
    
    
    # New-KILL
    elif trait == "new_kill":
    
        eras = [
            p["ERA"]
            for p in lineup["SP"]
            if p.get("ERA") is not None
        ]
    
        if eras and sum(eras)/len(eras) <= 2.5:
            bonus += 3
    
    
    # 스타 플레이어
    elif trait == "starplayer":
    
        cnt = sum(
            1 for p in all_players
            if p["war"] >= 9
        )
    
        if cnt >= 3:
            bonus += 2
    
    
    # 원맨팀
    elif trait == "oneman":
    
        wars = sorted(
            [p["war"] for p in all_players],
            reverse=True
        )
    
        if wars[0] - wars[1] >= 1.5:
            bonus += 3

    # 타율=승리
    elif trait == "avg_win":
    
        hitters = [
            lineup[pos]
            for pos in [
                "C","1B","2B","3B",
                "SS","LF","CF","RF","DH"
            ]
        ]
    
        cnt = sum(
            1 for p in hitters
            if p.get("AVG",0) >= 0.300
        )
    
        if cnt >= 7:
            bonus += 3
    
    
    # 수비 코어
    elif trait == "def_core":
    
        total = (
            lineup["C"]["war"]
            + lineup["2B"]["war"]
            + lineup["SS"]["war"]
            + lineup["CF"]["war"]
        )
    
        if total <= 25:
            bonus += 4
    
    
    # 주장의 품격
    elif trait == "captain":
    
        cnt = sum(
            1 for p in all_players
            if p.get("Captain")
        )
    
        if cnt >= 7:
            bonus += 3
    
    
    # 구심점 야구
    elif trait == "leader":
    
        cnt = sum(
            1 for p in all_players
            if p.get("Captain")
        )
    
        if cnt == 1:
            bonus += 5
    
    
    # 18의 향연
    elif trait == "ops18":
    
        hitters = [
            lineup[pos]
            for pos in [
                "C","1B","2B","3B",
                "SS","LF","CF","RF","DH"
            ]
        ]
    
        cnt = sum(
            1 for p in hitters
            if p.get("ops",0) >= 0.9
        )
    
        if cnt >= 8:
            bonus += 3
    
    
    # 외인은 전설이다
    elif trait == "foreign":
    
        cnt = sum(
            1 for p in all_players
            if not p.get("Korean",True)
        )
    
        if cnt >= 7:
            bonus += 4
    
    
    # 더러운 볼
    elif trait == "dirtyball":
    
        total_so = 0
    
        for p in lineup["SP"]:
            total_so += p.get("SO",0)
    
        for p in lineup["RP"]:
            total_so += p.get("SO",0)
    
        if total_so >= 777:
            bonus += 3
    
    
    # 시대를 뛰어넘은 야구
    elif trait == "timetravel":
    
        years = [
            p["Year"]
            for p in all_players
        ]
    
        if len(set(years)) == len(years):
            bonus += 3
    
    
    # 도영맘
    elif trait == "doyoung":
    
        if (
            lineup["SS"]
            and lineup["SS"]["name"] == "김도영"
        ):
            bonus += 4
    
    
    # 거포 유격수
    elif trait == "power_ss":
    
        if lineup["SS"].get("ops",0) >= 0.9:
            bonus += 3
    
    
    # 거포 중견수
    elif trait == "power_cf":
    
        if lineup["CF"].get("ops",0) >= 0.9:
            bonus += 3
    
    
    # 무실점 선발
    elif trait == "nohit_sp":
    
        eras = [
            p["ERA"]
            for p in lineup["SP"]
            if p.get("ERA") is not None
        ]
    
        if eras and sum(eras)/len(eras) <= 1.5:
            bonus += 4
    
    
    # 무실점 불펜
    elif trait == "nohit_rp":
    
        eras = [
            p["ERA"]
            for p in lineup["RP"]
            if p.get("ERA") is not None
        ]
    
        if eras and sum(eras)/len(eras) <= 0.9:
            bonus += 4
    
    
    # 테이블 세터
    elif trait == "tablesetter":
    
        avg = (
            lineup["2B"].get("AVG",0)
            + lineup["SS"].get("AVG",0)
            + lineup["CF"].get("AVG",0)
        ) / 3
    
        if avg >= 0.320:
            bonus += 3
    
    
    # 에이스 왕국
    elif trait == "acekingdom":
    
        sp_war = sum(
            p["war"]
            for p in lineup["SP"]
        )
    
        if sp_war >= 25:
            bonus += 3
    
    
    # 한국시리즈 DNA
    elif trait == "ks_dna":
    
        captain_cnt = sum(
            1 for p in all_players
            if p.get("Captain")
        )
    
        star_cnt = sum(
            1 for p in all_players
            if p["war"] >= 8
        )
    
        if (
            captain_cnt >= 5
            and star_cnt >= 5
        ):
            bonus += 4
    
    
    # 황금 세대
    elif trait == "gold_generation":
    
        year_count = {}
    
        for p in all_players:
    
            y = p["Year"]
    
            year_count[y] = (
                year_count.get(y,0)
                + 1
            )
    
        if max(
            year_count.values()
        ) >= 5:
            bonus += 3

    
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

    wins = round(total_war * 1.19)

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
