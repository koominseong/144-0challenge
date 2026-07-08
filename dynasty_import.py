import os
import json
import random

from app import supabase

START_YEAR = 1982


def calc_season(year):

    # 1982~1984 → Season1
    # 1985~1987 → Season2

    return ((year - START_YEAR) // 3) + 1


def calc_overall(war):

    if war >= 10:
        return random.randint(97, 99)

    elif war >= 8:
        return random.randint(92, 96)

    elif war >= 6:
        return random.randint(87, 91)

    elif war >= 4:
        return random.randint(82, 86)

    elif war >= 2:
        return random.randint(75, 81)

    return random.randint(65, 74)

def calc_potential(overall):

    return min(
        99,
        overall + random.randint(0, 4)
    )
