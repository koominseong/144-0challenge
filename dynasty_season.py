from app import supabase


def next_season(save_id):

    save = (

        supabase

        .table("dynasty_save")

        .select("*")

        .eq("id", save_id)

        .single()

        .execute()

        .data

    )

    season = save["season"] + 1

    supabase.table(

        "dynasty_save"

    ).update({

        "season": season,

        "week": 1

    }).eq(

        "id",
        save_id

    ).execute()

    return season

from random import shuffle


def rookie_draft_pool(save_id):

    save = (

        supabase

        .table("dynasty_save")

        .select("season")

        .eq("id", save_id)

        .single()

        .execute()

        .data

    )

    season = save["season"]

    rookies = (

        supabase

        .table("dynasty_player")

        .select("*")

        .eq("save_id", save_id)

        .eq("drafted", False)

        .eq("appear_season", season)

        .execute()

        .data

    )

    shuffle(rookies)

    return rookies
