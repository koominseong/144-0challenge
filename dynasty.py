from flask import (
    render_template,
    redirect,
    session,
    request
)

import random
import json
import os

from app import app


# ==========================
# Dynasty Home
# ==========================

@app.route("/dynasty")
def dynasty():

    # 로그인 안 되어 있으면
    if "user_id" not in session:
        return redirect("/login")

    saves = []

    for i in range(1,4):

        path = os.path.join(
            "Dynasty",
            session["user_id"],
            f"save{i}.json"
        )

        if os.path.exists(path):

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                saves.append(json.load(f))

        else:

            saves.append(None)

    return render_template(
        "dynasty_home.html",
        saves=saves
    )


# ==========================
# New Dynasty
# ==========================

@app.route("/dynasty/new")
def dynasty_new():

    return render_template(
        "dynasty_new.html"
    )


@app.route(
    "/dynasty/create",
    methods=["POST"]
)
def dynasty_create():

    team_name = request.form["team_name"]

    logo = request.form["logo"]

    color = request.form["color"]

    stadium = request.form["stadium"]

    save = {

        "season":2026,

        "team_name":team_name,

        "logo":logo,

        "color":color,

        "stadium":stadium,

        "wins":0,

        "losses":0,

        "money":500,

        "fans":100000,

        "coach_level":1,

        "training":1,

        "medical":1,

        "scout":1,

        "roster":[],

        "prospects":[],

        "history":[]

    }

    folder = os.path.join(
        "Dynasty",
        session["user_id"]
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    path = os.path.join(
        folder,
        "save1.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            save,
            f,
            ensure_ascii=False,
            indent=4
        )

    return redirect(
        "/dynasty/home/1"
    )


# ==========================
# Continue
# ==========================

@app.route("/dynasty/home/<int:slot>")
def dynasty_home(slot):

    path = os.path.join(

        "Dynasty",

        session["user_id"],

        f"save{slot}.json"

    )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        save = json.load(f)

    return render_template(

        "dynasty_dashboard.html",

        save=save,

        slot=slot

    )
