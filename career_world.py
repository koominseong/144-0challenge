import json
import os


CAREER_DATA_DIR = os.path.join(
    "Data",
    "Career"
)


def load_json(filename):

    path = os.path.join(
        CAREER_DATA_DIR,
        filename
    )

    if not os.path.exists(path):
        return []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def get_countries():

    return load_json(
        "career_countries.json"
    )


def get_leagues():

    return load_json(
        "career_leagues.json"
    )


def get_teams():

    return load_json(
        "career_teams.json"
    )


def get_competitions():

    return load_json(
        "career_competitions.json"
    )


def get_events():

    return load_json(
        "career_events.json"
    )


def get_country(country_id):

    for country in get_countries():

        if country["country_id"] == country_id:
            return country

    return None


def get_league(league_id):

    for league in get_leagues():

        if league["league_id"] == league_id:
            return league

    return None


def get_team(team_id):

    for team in get_teams():

        if team["team_id"] == team_id:
            return team

    return None


def teams_by_league(league_id):

    return [

        team

        for team in get_teams()

        if team["league_id"] == league_id

    ]


def leagues_by_country(country_id):

    return [

        league

        for league in get_leagues()

        if league["country_id"] == country_id

    ]


def leagues_by_level(level):

    return [

        league

        for league in get_leagues()

        if league["level"] == level

    ]


def can_transfer(
    player,
    destination_league
):

    current = get_league(
        player.league_id
    )

    destination = get_league(
        destination_league
    )

    if not current or not destination:
        return False

    # 같은 리그
    if current["league_id"] == destination["league_id"]:
        return True

    # 상위 리그 이동
    level_difference = (
        destination["level"]
        -
        current["level"]
    )

    # OVR에 따른 기본 제한
    if level_difference < 0:

        required_ovr = (
            55
            +
            abs(level_difference) * 8
        )

        if player.ovr < required_ovr:
            return False

    return True
