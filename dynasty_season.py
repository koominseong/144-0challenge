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
