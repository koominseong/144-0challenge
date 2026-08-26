# auction_routes.py
# =========================================
# 144-0 Challenge - PLAYER AUCTION routes
# =========================================

from flask import Blueprint, render_template, redirect, url_for, session

from auction import new_game, user_action, score_game, AI_NAMES, ROUNDS


auction_bp = Blueprint("auction", __name__)


def _get_state():
    return session.get("auction_state")


@auction_bp.route("/auction")
def auction_home():
    return render_template("auction_home.html")


@auction_bp.route("/auction/new")
def auction_new():
    session["auction_state"] = new_game()
    session.modified = True
    return redirect(url_for("auction.auction_play"))


@auction_bp.route("/auction/play")
def auction_play():
    state = _get_state()

    if not state:
        return redirect(url_for("auction.auction_home"))

    if state.get("done"):
        return redirect(url_for("auction.auction_result"))

    return render_template(
        "auction_game.html",
        state=state,
        round=state["round"],
        total_rounds=ROUNDS,
        ai_names=AI_NAMES,
    )


@auction_bp.route("/auction/action/<action>")
def auction_action(action):
    state = _get_state()

    if not state:
        return redirect(url_for("auction.auction_home"))

    state = user_action(state, action)
    session["auction_state"] = state
    session.modified = True

    if state.get("done"):
        return redirect(url_for("auction.auction_result"))

    return redirect(url_for("auction.auction_play"))


@auction_bp.route("/auction/result")
def auction_result():
    state = _get_state()

    if not state:
        return redirect(url_for("auction.auction_home"))

    if not state.get("done"):
        return redirect(url_for("auction.auction_play"))

    result = score_game(state)

    return render_template(
        "auction_result.html",
        state=state,
        result=result,
        ai_names=AI_NAMES,
    )
