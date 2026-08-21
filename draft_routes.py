from flask import Blueprint, render_template, request, redirect, url_for
from draft import new_game, get, act, view

draft_bp = Blueprint("draft", __name__, url_prefix="/draft")

@draft_bp.route("/<save_id>")
def setup(save_id):
    return render_template("draft_setup.html", save_id=save_id)

@draft_bp.route("/<save_id>/start", methods=["POST"])
def start(save_id):
    try:
        limits={"투수":request.form.get("pitchers",2,type=int),"내야수":request.form.get("infielders",2,type=int),"외야수":request.form.get("outfielders",2,type=int),"포수":request.form.get("catchers",1,type=int)}
        state=new_game(save_id,limits,request.form.get("money",20,type=int),request.form.get("player_a","PLAYER A"),request.form.get("player_b","PLAYER B"))
        return redirect(url_for("draft.game",save_id=save_id,game_id=state["id"]))
    except Exception as e:
        return render_template("draft_setup.html",save_id=save_id,error=str(e),form=request.form)

@draft_bp.route("/<save_id>/game/<game_id>")
def game(save_id,game_id):
    state=get(game_id)
    if state["finished"]: return redirect(url_for("draft.result",save_id=save_id,game_id=game_id))
    return render_template("draft_game.html",state=view(state),error=None,save_id=save_id,game_id=game_id)

@draft_bp.route("/<save_id>/game/<game_id>/action",methods=["POST"])
def action(save_id,game_id):
    try:
        act(game_id,request.form.get("side"),request.form.get("action"))
    except Exception as e:
        state=get(game_id)
        return render_template("draft_game.html",state=view(state),error=str(e),save_id=save_id,game_id=game_id)
    state=get(game_id)
    if state["finished"]: return redirect(url_for("draft.result",save_id=save_id,game_id=game_id))
    return redirect(url_for("draft.game",save_id=save_id,game_id=game_id))

@draft_bp.route("/<save_id>/result/<game_id>")
def result(save_id,game_id):
    state=get(game_id)
    if not state["finished"]: return redirect(url_for("draft.game",save_id=save_id,game_id=game_id))
    return render_template("draft_result.html",state=view(state),save_id=save_id,game_id=game_id)
