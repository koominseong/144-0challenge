from app import supabase


def best(players):

    if not players:
        return None

    return sorted(
        players,
        key=lambda x: x["overall"],
        reverse=True
    )[0]


def auto_lineup(save_id, team_id):

    roster = (

        supabase

        .table("dynasty_roster")

        .select(
            "id,player_id,dynasty_player(*)"
        )

        .eq("save_id", save_id)

        .eq("team_id", team_id)

        .execute()

        .data

    )

    players = []

    for r in roster:

        p = r["dynasty_player"]

        p["roster_id"] = r["id"]

        players.append(p)

    used = set()

    lineup = {}

    positions = [

        "C",
        "1B",
        "2B",
        "3B",
        "SS",
        "LF",
        "CF",
        "RF"

    ]

    # -------------------
    # 야수
    # -------------------

    for pos in positions:

        cand = [

            p for p in players

            if (
                pos in p["positions"]
                and
                p["id"] not in used
            )

        ]

        pick = best(cand)

        if pick:

            lineup[pos] = pick

            used.add(pick["id"])

    # -------------------
    # DH
    # -------------------

    cand = [

        p for p in players

        if (
            "SP" not in p["positions"]
            and
            "RP" not in p["positions"]
            and
            p["id"] not in used
        )

    ]

    pick = best(cand)

    if pick:

        lineup["DH"] = pick

        used.add(pick["id"])

    # -------------------
    # 선발
    # -------------------

    sp = sorted(

        [

            p for p in players

            if "SP" in p["positions"]

        ],

        key=lambda x: x["overall"],

        reverse=True

    )[:5]

    # -------------------
    # 불펜
    # -------------------

    rp = sorted(

        [

            p for p in players

            if (
                "RP" in p["positions"]
                and
                p["id"] not in {

                    x["id"]

                    for x in sp

                }

            )

        ],

        key=lambda x: x["overall"],

        reverse=True

    )[:7]

    # -------------------
    # DB 업데이트
    # -------------------

    for pos, player in lineup.items():

        supabase.table(

            "dynasty_roster"

        ).update({

            "role": pos

        }).eq(

            "id",
            player["roster_id"]

        ).execute()

    for i, p in enumerate(sp):

        supabase.table(

            "dynasty_roster"

        ).update({

            "role": "SP",

            "depth": i + 1

        }).eq(

            "id",
            p["roster_id"]

        ).execute()

    for i, p in enumerate(rp):

        supabase.table(

            "dynasty_roster"

        ).update({

            "role": "RP",

            "depth": i + 1

        }).eq(

            "id",
            p["roster_id"]

        ).execute()
