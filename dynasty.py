from flask import *
import random
import json
import os

from app import app


# ==========================
# Dynasty 메인
# ==========================

@app.route("/dynasty")
def dynasty():

    return render_template(
        "dynasty_home.html"
    )


# ==========================
# 새 게임
# ==========================

@app.route("/dynasty/new")
def dynasty_new():

    return render_template(
        "dynasty_new.html"
    )


# ==========================
# 창단
# ==========================

@app.route(
    "/dynasty/create",
    methods=["POST"]
)
def dynasty_create():

    session["dynasty"] = {

        "season":1,

        "team_name":
        request.form["team_name"],

        "money":500,

        "fans":100000,

        "wins":0,

        "losses":0,

        "day":1

    }

    return redirect(
        "/dynasty/start"
    )


# ==========================
# 리그 생성
# ==========================

@app.route("/dynasty/start")
def dynasty_start():

    teams=[

        session["dynasty"]["team_name"],

        "LG",

        "두산",

        "삼성",

        "롯데",

        "한화",

        "KIA",

        "KT",

        "NC",

        "SSG"

    ]

    session["dynasty"]["league"]=teams

    return redirect(
        "/dynasty/dashboard"
    )


# ==========================
# 대시보드
# ==========================

@app.route("/dynasty/dashboard")
def dynasty_dashboard():

    return render_template(

        "dynasty_dashboard.html",

        dynasty=session["dynasty"]

    )
