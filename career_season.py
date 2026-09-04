import random


def simulate_batter(player):

    games = random.randint(
        45,
        144
    )

    contact = player.contact
    power = player.power
    eye = player.eye
    speed = player.speed

    avg = (
        0.160
        +
        contact * 0.002
        +
        eye * 0.0004
        +
        random.uniform(
            -0.025,
            0.025
        )
    )

    avg = round(
        max(
            0.150,
            min(
                0.380,
                avg
            )
        ),
        3
    )

    hr = int(
        power
        *
        random.uniform(
            0.15,
            0.55
        )
    )

    rbi = int(
        hr * random.uniform(
            1.5,
            3.0
        )
        +
        games * random.uniform(
            0.15,
            0.45
        )
    )

    runs = int(
        games
        *
        random.uniform(
            0.25,
            0.65
        )
    )

    sb = int(
        speed
        *
        random.uniform(
            0.03,
            0.35
        )
    )

    return {

        "G": games,
        "AVG": avg,
        "HR": hr,
        "RBI": rbi,
        "R": runs,
        "SB": sb

    }


def simulate_pitcher(player):

    games = random.randint(
        20,
        70
    )

    command = player.command
    breaking = player.breaking
    velocity = player.velocity

    era = (

        7.0

        - command * 0.040

        - breaking * 0.018

        - velocity * 0.012

        + random.uniform(
            -0.6,
            0.6
        )

    )

    era = round(
        max(
            1.20,
            min(
                8.00,
                era
            )
        ),
        2
    )

    wins = max(
        0,
        int(
            player.ovr
            *
            random.uniform(
                0.03,
                0.16
            )
        )
    )

    so = int(

        velocity
        * random.uniform(
            0.8,
            2.0
        )

        +

        breaking
        * random.uniform(
            0.5,
            1.4
        )

    )

    saves = 0

    if player.position in [
        "RP",
        "CP",
        "마무리"
    ]:

        saves = random.randint(
            0,
            min(
                45,
                games
            )
        )

    return {

        "G": games,
        "W": wins,
        "ERA": era,
        "SO": so,
        "SV": saves

    }


def simulate_team_result(
    player
):

    strength = (

        player.ovr

        +

        random.randint(
            -12,
            12
        )

    )

    if strength >= 90:

        return "champion"

    if strength >= 78:

        return "playoffs"

    if strength >= 65:

        return "wildcard"

    return "missed"


def simulate_season(
    player
):

    if player.retired:
        return None

    player.season += 1

    # --------------------------------
    # 부상
    # --------------------------------

    injury = (
        random.random()
        <
        0.04
    )

    player.injured = injury

    # --------------------------------
    # 성적
    # --------------------------------

    pitcher_positions = [

        "SP",
        "RP",
        "CP",
        "투수",
        "선발",
        "불펜",
        "마무리"

    ]

    if player.position in pitcher_positions:

        stats = simulate_pitcher(
            player
        )

    else:

        stats = simulate_batter(
            player
        )

    # --------------------------------
    # 부상 경기수 감소
    # --------------------------------

    if injury:

        stats["G"] = max(

            1,

            stats["G"]
            -
            random.randint(
                10,
                60
            )

        )

    # --------------------------------
    # 성장
    # --------------------------------

    development = player.development()

    # --------------------------------
    # 팀 성적
    # --------------------------------

    team_result = simulate_team_result(
        player
    )

    # --------------------------------
    # 시즌 데이터
    # --------------------------------

    season_data = {

        "season":
            player.season,

        "age":
            player.age,

        "league_id":
            player.league_id,

        "team_id":
            player.team_id,

        "ovr":
            player.ovr,

        "stats":
            stats,

        "development":
            development,

        "injured":
            injury,

        "team_result":
            team_result,

        "awards": []

    }

    # --------------------------------
    # 포스트시즌
    # --------------------------------

    if team_result == "champion":

        player.add_trophy(
            "League Championship"
        )

        season_data[
            "awards"
        ].append(
            "League Championship"
        )

    # --------------------------------
    # 개인상
    # --------------------------------

    if "AVG" in stats:

        if stats["AVG"] >= .320:

            player.add_award(
                "Batting Title"
            )

            season_data[
                "awards"
            ].append(
                "Batting Title"
            )

        if stats["HR"] >= 35:

            player.add_award(
                "Home Run Leader"
            )

            season_data[
                "awards"
            ].append(
                "Home Run Leader"
            )

    else:

        if stats["ERA"] <= 2.80:

            player.add_award(
                "ERA Leader"
            )

            season_data[
                "awards"
            ].append(
                "ERA Leader"
            )

        if stats["SO"] >= 170:

            player.add_award(
                "Strikeout Leader"
            )

            season_data[
                "awards"
            ].append(
                "Strikeout Leader"
            )

    # --------------------------------
    # 기록 저장
    # --------------------------------

    player.seasons.append(
        season_data
    )

    player.age += 1

    return season_data
