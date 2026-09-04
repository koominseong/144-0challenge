import random

from career_world import (
    get_country,
    get_competitions
)


def eligible_competitions(
    player
):

    country = get_country(
        player.nationality
    )

    if not country:
        return []

    competitions = []

    for competition in get_competitions():

        countries = competition.get(
            "countries",
            []
        )

        if player.nationality in countries:

            competitions.append(
                competition
            )

    return competitions


def national_team_probability(
    player,
    competition
):

    minimum_ovr = competition.get(
        "minimum_ovr",
        60
    )

    if player.ovr < minimum_ovr:
        return 0

    probability = (

        0.10

        +

        (
            player.ovr
            -
            minimum_ovr
        )
        * 0.025

        +

        player.reputation
        * 0.003

    )

    # 국제대회마다 경쟁 정도
    competition_factor = competition.get(
        "selection_factor",
        1.0
    )

    probability *= competition_factor

    return max(
        0.01,
        min(
            0.95,
            probability
        )
    )


def check_national_team(
    player
):

    if player.retired:
        return None

    competitions = (
        eligible_competitions(
            player
        )
    )

    if not competitions:
        return None

    selected = []

    for competition in competitions:

        probability = (
            national_team_probability(
                player,
                competition
            )
        )

        if random.random() < probability:

            result = {

                "season":
                    player.season,

                "competition":
                    competition["name"],

                "country":
                    player.nationality,

                "result":
                    random.choice([
                        "roster",
                        "starter",
                        "bench"
                    ])

            }

            player.national_team_caps += 1

            player.international.append(
                result
            )

            selected.append(
                result
            )

    return selected
