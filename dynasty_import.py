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
    
def import_players(save_id):

    folder = "Data/kbo_json_v5"

    players = {}

    for file in os.listdir(folder):

        if not file.endswith(".json"):
            continue

        with open(
            os.path.join(folder,file),
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        for p in data:

            name = p["name"]

            if name not in players:

                players[name] = {

                    "name":name,

                    "positions":p["positions"],

                    "debut_year":p["Year"],

                    "peak_war":p["war"]

                }

            else:

                # 가장 빠른 데뷔연도

                players[name]["debut_year"] = min(

                    players[name]["debut_year"],

                    p["Year"]

                )

                # 최고 WAR

                if p["war"] > players[name]["peak_war"]:

                    players[name]["peak_war"] = p["war"]

                    players[name]["positions"] = p["positions"]
                    
        for p in players.values():
            
            overall = calc_overall(
                p["peak_war"]
            )

            if "SP" in p["positions"] or "RP" in p["positions"]:
                
                stat = calc_pitcher(p)
            
            else:
                
                stat = calc_hitter(p)
    
            potential = min(
                overall + random.randint(0,4),
                99
            )
    
            supabase.table(
                "dynasty_player"
            ).insert({
    
                "save_id":save_id,
    
                "name":p["name"],
    
                "team":"FA",
    
                "positions":p["positions"],
    
                "debut_year":p["debut_year"],
    
                "appear_season":calc_season(
                    p["debut_year"]
                ),
    
                "war":p["peak_war"],
    
                "overall":overall,
    
                "potential":potential,
    
                "drafted":False,
    
                "retired":False

                **stat
    
            }).execute()

def calc_hitter(p):

    contact = 60
    power = 60
    eye = 60
    speed = 60
    defense = 60
    arm = 60

    avg = p.get("AVG")
    ops = p.get("ops")
    hr = p.get("HR")
    sb = p.get("SB")

    if avg is not None:
        contact += int(avg * 100)

    if ops is not None:
        eye += int((ops - 0.6) * 70)
        power += int((ops - 0.6) * 55)

    if hr is not None:
        power += min(hr,40)

    if sb is not None:
        speed += min(sb,35)

    return {

        "contact":max(40,min(99,contact)),
        "power":max(40,min(99,power)),
        "eye":max(40,min(99,eye)),
        "speed":max(40,min(99,speed)),
        "defense":defense,
        "arm":arm

    }

def calc_pitcher(p):

    stuff = 65
    control = 65
    stamina = 65

    era = p.get("ERA")
    so = p.get("SO")
    ip = p.get("IP")

    if era is not None:

        stuff += int((5-era)*8)

        control += int((5-era)*5)

    if so is not None:

        stuff += min(
            int(so/8),
            20
        )

    if ip is not None:

        stamina += min(
            int(ip/10),
            25
        )

    return {

        "stuff":max(40,min(99,stuff)),
        "control":max(40,min(99,control)),
        "stamina":max(40,min(99,stamina))

    }
