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

    user_team = request.form["team_name"]

    logo = request.form["logo"]

    color = request.form["color"]

    stadium = request.form["stadium"]


    league = [

        {
            "name":user_team,
            "logo":logo,
            "user":True
        },

        {
            "name":"LG 트윈스",
            "logo":"⚡",
            "user":False
        },

        {
            "name":"두산 베어스",
            "logo":"🐻",
            "user":False
        },

        {
            "name":"KIA 타이거즈",
            "logo":"🐯",
            "user":False
        },

        {
            "name":"삼성 라이온즈",
            "logo":"🦁",
            "user":False
        },

        {
            "name":"롯데 자이언츠",
            "logo":"🚢",
            "user":False
        },

        {
            "name":"한화 이글스",
            "logo":"🦅",
            "user":False
        },

        {
            "name":"KT 위즈",
            "logo":"🪄",
            "user":False
        },

        {
            "name":"NC 다이노스",
            "logo":"🦕",
            "user":False
        },

        {
            "name":"SSG 랜더스",
            "logo":"🚀",
            "user":False
        }

    ]


    random.shuffle(league)


    session["dynasty"]={

        "season":1,

        "week":1,

        "money":500,

        "fans":100000,

        "wins":0,

        "losses":0,

        "logo":logo,

        "color":color,

        "stadium":stadium,

        "team_name":user_team,

        "league":league,

        "roster":[],

        "prospects":[],

        "free_agents":[],

        "history":[]

    }

    return redirect("/dynasty/draft")

@app.route("/dynasty/draft")
def dynasty_draft():

    dynasty=session["dynasty"]

    return render_template(

        "dynasty_draft.html",

        dynasty=dynasty

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
