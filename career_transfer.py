import random

from career_world import (
    get_league,
    get_team,
    get_leagues,
    get_teams,
    can_transfer
)


def league_strength(league):

    if not league:
        return 0

    return league.get(
        "strength",
        50
    )


def transfer_score(
    player,
    destination
):

    league = get_league(
        destination["league_id"]
    )

    if not league:
        return -999

    score = 0

    score += (
        player.ovr
        -
        league_strength(league)
    )

    score += (
        player.reputation
        * 0.25
    )

    score += random.randint(
        -8,
        8
    )

    return score


def possible_transfers(player):

    results = []

    for league in get_leagues():

        if not can_transfer(
            player,
            league["league_id"]
        ):
            continue

        for team in get_teams():

            if team["league_id"] != league["league_id"]:
                continue

            score = transfer_score(
                player,
                team
            )

            if score >= 0:

                results.append({

                    "team_id":
                        team["team_id"],

                    "league_id":
                        league["league_id"],

                    "score":
                        score

                })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


def transfer_probability(
    player,
    destination
):

    league = get_league(
        destination["league_id"]
    )

    if not league:
        return 0

    strength = league_strength(
        league
    )

    probability = (

        0.15

        +

        (
            player.ovr
            -
            strength
        )
        * 0.025

        +

        player.reputation
        * 0.002

    )

    return max(
        0.02,
        min(
            0.90,
            probability
        )
    )


def offer_transfer(
    player,
    destination_team_id
):

    team = get_team(
        destination_team_id
    )

    if not team:
        return False

    probability = transfer_probability(
        player,
        team
    )

    success = (
        random.random()
        <
        probability
    )

    if not success:
        return False

    old_team = player.team_id
    old_league = player.league_id

    player.team_id = team[
        "team_id"
    ]

    player.league_id = team[
        "league_id"
    ]

    transfer_data = {

        "season":
            player.season,

        "from_team":
            old_team,

        "to_team":
            player.team_id,

        "from_league":
            old_league,

        "to_league":
            player.league_id

    }

    player.transfers.append(
        transfer_data
    )

    return transfer_data


def generate_transfer_offers(
    player
):

    candidates = (
        possible_transfers(
            player
        )
    )

    offers = []

    for candidate in candidates[:10]:

        team = get_team(
            candidate["team_id"]
        )

        if not team:
            continue

        if random.random() < 0.35:

            offers.append({

                "team_id":
                    team["team_id"],

                "team_name":
                    team["name"],

                "league_id":
                    team["league_id"],

                "score":
                    candidate["score"]

            })

    return offers
