from flask import (
    render_template,
    redirect,
    session,
    request
)
import random
import json
import os

from dynasty_season import rookie_draft_pool
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
    user = supabase.table(
        "dynasty_team"
    ).insert({
    
        "save_id":save_id,
    
        "team_name":save["team_name"],
    
        "logo":save["logo"],
    
        "color":save["color"],
    
        "stadium":save["stadium"],
    
        "is_user":True
    
    }).execute()
    
    session["dynasty_team"] = user.data[0]["id"]

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

    save_id = session["dynasty_save"]

    players = (
        supabase
        .table("dynasty_player")
        .select("*")
        .eq("save_id", save_id)
        .eq("drafted", False)
        .execute()
        .data
    )

    random.shuffle(players)

    players = players[:24]

    return render_template(

        "dynasty_draft.html",

        players=players,

        round=session.get("draft_round",1),

        pick=session.get("draft_pick",1)
    )

@app.route("/dynasty/draft_pick/<int:player_id>") 
def dynasty_pick(player_id):

    save_id=session["dynasty_save"] 
        
    save_id = session["dynasty_save"]
    
    team_id = session["dynasty_team"]
    
    supabase.table(
        "dynasty_roster"
    ).insert({
    
        "save_id": save_id,
    
        "team_id": team_id,
    
        "player_id": player_id,
    
        "role": "Bench",
    
        "depth": 1
    
    }).execute()
    
    supabase.table(
        "dynasty_player"
    ).update({
    
        "drafted": True
    
    }).eq(
    
        "id",
        player_id
    
    ).execute()
    
    return redirect("/dynasty/ai_draft")

@app.route("/dynasty/ai_draft")
def ai_draft():

    save_id=session["dynasty_save"]

    teams=(
        supabase.table(
            "dynasty_team"
        )
        .select("*")
        .eq("save_id",save_id)
        .eq("is_user",False)
        .execute()
        .data
    )

    players=(
        supabase.table(
            "dynasty_player"
        )
        .select("*")
        .eq("save_id",save_id)
        .eq("drafted",False)
        .order(
            "overall",
            desc=True
        )
        .execute()
        .data
    )

    random.shuffle(teams)

    for team in teams:

        if not players:
            break

        p=players.pop(0)

        supabase.table(
            "dynasty_roster"
        ).insert({
        
            "save_id": save_id,
        
            "team_id": team["id"],
        
            "player_id": p["id"],
        
            "role": "Bench",
        
            "depth": 1
        
        }).execute()
        
        supabase.table(
            "dynasty_player"
        ).update({
        
            "drafted": True
        
        }).eq(
        
            "id",
            p["id"]
        
        ).execute()

    session["draft_pick"]=session.get(
        "draft_pick",
        1
    )+1

    if session["draft_pick"] > 25:
        
        teams = (
            
            supabase
    
            .table("dynasty_team")
    
            .select("*")
    
            .eq("save_id", save_id)
    
            .execute()
    
            .data
    
        )
    
        from dynasty_lineup import auto_lineup
    
        for team in teams:
    
            auto_lineup(
                save_id,
                team["id"]
            )
    
        return redirect("/dynasty/home")

    return redirect("/dynasty/draft")

@app.route("/dynasty/dashboard")
def dynasty_dashboard():

    save_id = session["dynasty_save"]

    save = (

        supabase

        .table("dynasty_save")

        .select("*")

        .eq("id", save_id)

        .single()

        .execute()

        .data

    )

    rookies = rookie_draft_pool(save_id)

    return render_template(

        "dynasty_dashboard.html",

        save=save,

        rookies=rookies[:8]

    )

@app.route("/dynasty/next_season")
def dynasty_next_season():

    save_id = session["dynasty_save"]

    next_season(save_id)

    return redirect("/dynasty/dashboard")
