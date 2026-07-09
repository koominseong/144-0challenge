import random

from app import supabase


def team_strength(team_id):

    roster = (

        supabase

        .table("dynasty_roster")

        .select("role,dynasty_player(*)")

        .eq("team_id",team_id)

        .execute()

        .data

    )

    hit = 0

    pitch = 0

    count = 0

    sp = 0

    for r in roster:

        p = r["dynasty_player"]

        role = r["role"]

        if role == "SP":

            pitch += (

                p["stuff"]

                + p["control"]

                + p["stamina"]

            ) / 3

            sp += 1

        elif role == "RP":

            pitch += (

                p["stuff"]

                + p["control"]

            ) / 2

        elif role not in ["Bench","Minor"]:

            hit += (

                p["contact"]

                + p["power"]

                + p["eye"]

            ) / 3

            count += 1

    if count:

        hit /= count

    if sp:

        pitch /= (sp + 7)

    return hit + pitch

def simulate_game(home_id,away_id):

    home = team_strength(home_id)

    away = team_strength(away_id)

    home += random.uniform(-8,8)

    away += random.uniform(-8,8)

    home_score = max(

        0,

        int(

            random.gauss(home/18,2)

        )

    )

    away_score = max(

        0,

        int(

            random.gauss(away/18,2)

        )

    )

    while home_score == away_score:

        if random.random() < .5:

            home_score += 1

        else:

            away_score += 1

    return home_score,away_score

def simulate_week(save_id):

    save=(

        supabase

        .table("dynasty_save")

        .select("*")

        .eq("id",save_id)

        .single()

        .execute()

        .data

    )

    games=(

        supabase

        .table("dynasty_schedule")

        .select("*")

        .eq("save_id",save_id)

        .eq("season",save["season"])

        .eq("week",save["week"])

        .execute()

        .data

    )

    results=[]

    for g in games:

        hs,ascore=simulate_game(

            g["home_team"],

            g["away_team"]

        )

        supabase.table(

            "dynasty_schedule"

        ).update({

            "played":True,

            "home_score":hs,

            "away_score":ascore

        }).eq(

            "id",
            g["id"]

        ).execute()

        results.append({

            "home":g["home_team"],

            "away":g["away_team"],

            "home_score":hs,

            "away_score":ascore

        })

    return results
