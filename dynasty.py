from flask import *
import random
import json
import os

from dynasty_import import import_players
from app import app, supabase


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

    data = {
        "team_name": request.form["team_name"],
        "logo": request.form["logo"],
        "color": request.form["color"],
        "stadium": request.form["stadium"]
    }

    result = (
        supabase
        .table("dynasty_save")
        .insert(data)
        .execute()
    )

    save_id = result.data[0]["id"]

    import_players(save_id)

    session["dynasty_save"] = save_id

    return redirect("/dynasty/setup")

@app.route("/dynasty/setup")
def dynasty_setup():

    save_id = session["dynasty_save"]

    save = (
        supabase
        .table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .single()
        .execute()
    ).data

    teams = [

        ("LG 트윈스","⚡"),
        ("두산 베어스","🐻"),
        ("KIA 타이거즈","🐯"),
        ("삼성 라이온즈","🦁"),
        ("롯데 자이언츠","🚢"),
        ("한화 이글스","🦅"),
        ("KT 위즈","🪄"),
        ("NC 다이노스","🦕"),
        ("SSG 랜더스","🚀")

    ]

    # 유저 팀 생성
    supabase.table("dynasty_team").insert({

        "save_id":save_id,

        "team_name":save["team_name"],

        "logo":save["logo"],

        "color":save["color"],

        "stadium":save["stadium"],

        "is_user":True

    }).execute()

    # AI 팀 생성
    for name, logo in teams:

        supabase.table("dynasty_team").insert({

            "save_id":save_id,

            "team_name":name,

            "logo":logo,

            "color":"Default",

            "stadium":"",

            "is_user":False

        }).execute()

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
