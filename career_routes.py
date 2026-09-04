from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from career import load, countries, leagues, teams, start, state, season_decision, advance, choose_transfer, international_status

career_routes = Blueprint("career_routes", __name__)

def page_data(c=None):
    c=c or state()
    return {"career":c,"countries":countries(),"leagues":leagues(),"teams":teams(),
            "league_teams":[x for x in teams() if c and x.get("league_id")==c.get("league_id")] if c else [],
            "international":international_status(c) if c else None}

@career_routes.get("/career")
def career_home():
    return render_template("career_home.html", **page_data())

@career_routes.post("/career/start")
def career_start():
    try:
        start(request.form.get("name"),request.form.get("nationality","KR"),request.form.get("league_id","KBO"),request.form.get("team_id") or None,int(request.form.get("age",18)),request.form.get("position","내야"),request.form.get("mode","default"))
    except Exception as e:
        flash(str(e)); return redirect(url_for("career_routes.career_home"))
    return redirect(url_for("career_routes.career_dashboard"))

@career_routes.get("/career/dashboard")
def career_dashboard():
    if not state(): return redirect(url_for("career_routes.career_home"))
    return render_template("career_dashboard.html", **page_data())

@career_routes.post("/career/decision")
def career_decision():
    c=state()
    if not c: return redirect(url_for("career_routes.career_home"))
    try: season_decision(c,request.form.get("decision","훈련 집중"))
    except Exception as e: flash(str(e))
    return redirect(url_for("career_routes.career_dashboard"))

@career_routes.post("/career/advance")
def career_advance():
    c=state()
    if c: advance(c)
    return redirect(url_for("career_routes.career_dashboard"))

@career_routes.post("/career/transfer")
def career_transfer():
    c=state()
    if c:
        try: choose_transfer(c,request.form.get("league_id",c["league_id"]))
        except Exception as e: flash(str(e))
    return redirect(url_for("career_routes.career_dashboard"))

@career_routes.get("/career/international")
def career_international():
    c=state()
    if not c: return redirect(url_for("career_routes.career_home"))
    return render_template("career_international.html", **page_data(c))

@career_routes.get("/career/api/state")
def career_api_state():
    return jsonify(state() or {"active":False})

@career_routes.post("/career/reset")
def career_reset():
    from flask import session
    session.pop("career",None); return redirect(url_for("career_routes.career_home"))
