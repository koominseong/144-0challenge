import random
from app import supabase


def generate_schedule(save_id):

    teams = (

        supabase

        .table("dynasty_team")

        .select("id")

        .eq("save_id", save_id)

        .execute()

        .data

    )

    ids = [t["id"] for t in teams]

    random.shuffle(ids)

    season = (

        supabase

        .table("dynasty_save")

        .select("season")

        .eq("id", save_id)

        .single()

        .execute()

        .data["season"]

    )

    records = []

    week = 1

    for _ in range(24):

        random.shuffle(ids)

        for i in range(0,10,2):

            records.append({

                "save_id":save_id,

                "season":season,

                "week":week,

                "home_team":ids[i],

                "away_team":ids[i+1]

            })

        week += 1

    supabase.table(

        "dynasty_schedule"

    ).insert(records).execute()
