import random


def grow_player(player):

    age = player["age"]

    overall = player["overall"]

    potential = player["potential"]


    # 18~23 급성장
    if age <= 23:

        gain = random.randint(1, 4)

    # 24~27 완만한 성장
    elif age <= 27:

        gain = random.randint(0, 2)

    # 28~31 전성기
    elif age <= 31:

        gain = random.randint(-1, 1)

    # 32~35 노쇠
    elif age <= 35:

        gain = random.randint(-3, 0)

    # 36+
    else:

        gain = random.randint(-5, -2)

    overall += gain

    overall = max(
        40,
        min(
            overall,
            potential
        )
    )

    return overall

def age_player(player):

    player["age"] += 1

    player["overall"] = grow_player(player)

    return player

def retire(player):

    if player["age"] < 38:
        return False

    chance = (player["age"] - 37) * 20

    return random.randint(1,100) <= chance

def next_season(player):

    player["contract"] -= 1

    age_player(player)

    if retire(player):

        player["retired"] = True

    return player
