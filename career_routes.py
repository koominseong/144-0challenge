from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from career_engine import create_player, start_career, simulate_season, apply_choice, retire, NATIONS, KBO_TEAMS

career_bp = Blueprint("career", __name__, url_prefix="/career")


def _save(p):
    session["career"] = p
    session.modified = True


def _get():
    return session.get("career")


@career_bp.get("/")
def create():
    return render_template("career/create.html", nations=NATIONS, teams=KBO_TEAMS)


@career_bp.post("/start")
def start():
    try:
        age = int(request.form.get("age", 19))
    except ValueError:
        age = 19
    player = create_player(
        request.form.get("name", "신인 선수"),
        request.form.get("nationality", "KOR"),
        request.form.get("position", "내야수"),
        age,
        request.form.get("mode", "normal"),
        {"league": "KBO", "name": request.form.get("team", "LG 트윈스")},
    )
    _save(start_career(player))
    return redirect(url_for("career.home"))


@career_bp.get("/home")
def home():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    return render_template("career/home.html", p=p)


@career_bp.post("/season")
def season():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    _save(simulate_season(p))
    return redirect(url_for("career.event" if session["career"].get("pending_event") else "career.home"))


@career_bp.get("/event")
def event():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    if not p.get("pending_event"):
        return redirect(url_for("career.home"))
    return render_template("career/event.html", p=p, event=p["pending_event"])


@career_bp.post("/event/choice")
def choice():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    _save(apply_choice(p, request.form.get("choice_id", "0")))
    return redirect(url_for("career.home"))


@career_bp.get("/timeline")
def timeline():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    return render_template("career/timeline.html", p=p)


@career_bp.post("/retire")
def do_retire():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    _save(retire(p))
    return redirect(url_for("career.summary"))


@career_bp.get("/summary")
def summary():
    p = _get()
    if not p:
        return redirect(url_for("career.create"))
    return render_template("career/summary.html", p=p)


@career_bp.post("/reset")
def reset():
    session.pop("career", None)
    return redirect(url_for("career.create"))
