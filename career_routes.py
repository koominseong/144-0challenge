from flask import Blueprint, render_template, request, redirect, url_for, session
from career import (
    TEAMS, COUNTRIES, get_state, save_state, new_state, generate_academy_offers,
    start_career, generate_event, resolve_event, simulate_season, advance,
    eligible_competitions, team, league, position_label, bats_label, country,
    POSITION_LABELS, BATS_LABELS, PACE_INFO, career_summary, market_value,
    rating_tier, ROLE_INFO,
)

career_bp = Blueprint('career', __name__, url_prefix='/career')

RETIREMENT_AGE = 40


@career_bp.get('')
def career_home():
    state = get_state()
    if state and state.team_id:
        return redirect(url_for('career.dashboard'))
    if state and not state.team_id:
        return redirect(url_for('career.offers'))
    return render_template('career_home.html')


@career_bp.route('/new', methods=['GET', 'POST'])
def career_new():
    error = request.args.get('error')
    if request.method == 'POST':
        name = request.form.get('player_name')
        nationality = request.form.get('nationality')
        position = request.form.get('position')
        bats = request.form.get('bats')
        pace = request.form.get('pace')
        valid_country = any(c.get('country_id') == nationality for c in COUNTRIES)
        if not (name or '').strip():
            return redirect(url_for('career.career_new', error='name'))
        if not nationality or not valid_country:
            return redirect(url_for('career.career_new', error='nationality'))
        if position not in POSITION_LABELS:
            return redirect(url_for('career.career_new', error='position'))
        if bats not in BATS_LABELS:
            return redirect(url_for('career.career_new', error='bats'))
        if pace not in PACE_INFO:
            return redirect(url_for('career.career_new', error='pace'))
        state = new_state(name, nationality, position, bats, pace)
        save_state(state)
        session.pop('career_offers', None)
        return redirect(url_for('career.offers'))
    return render_template('career_new.html', countries=COUNTRIES, positions=POSITION_LABELS,
                            bats_options=BATS_LABELS, pace_options=PACE_INFO, error=error)


@career_bp.get('/offers')
def offers():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    if state.team_id:
        return redirect(url_for('career.dashboard'))
    offer_list = session.get('career_offers')
    if not offer_list:
        offer_list = generate_academy_offers(state.nationality)
        session['career_offers'] = offer_list
        session.modified = True
    for o in offer_list:
        o['league_name'] = (league(o.get('league_id')) or {}).get('name', o.get('league_id'))
    return render_template('career_offers.html', state=state, offer_list=offer_list,
                            country=country(state.nationality), position_label=position_label(state.position))


@career_bp.post('/offers')
def offers_choose():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    offer_list = session.get('career_offers') or []
    team_id = request.form.get('team_id')
    chosen = next((o for o in offer_list if o.get('team_id') == team_id), None)
    if not chosen:
        return redirect(url_for('career.offers'))
    start_career(state, chosen['team_id'], chosen['league_id'])
    state.pending_event = generate_event(state)
    state.decision_used = False
    save_state(state)
    session.pop('career_offers', None)
    return redirect(url_for('career.dashboard'))


@career_bp.get('/dashboard')
def dashboard():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    if not state.team_id:
        return redirect(url_for('career.offers'))
    if state.status == 'retired':
        return redirect(url_for('career.retire'))
    return render_template(
        'career_dashboard.html',
        state=state,
        team=team(state.team_id),
        league=league(state.league_id),
        country=country(state.nationality),
        position_label=position_label(state.position),
        bats_label=bats_label(state.bats),
        role_label=ROLE_INFO.get(state.role, {}).get('label', state.role),
        pace_label=PACE_INFO.get(state.pace, {}).get('label', state.pace),
        competitions=eligible_competitions(state.nationality, state.age),
        rating_tier=rating_tier(state.overall),
        market_value=market_value(state),
    )


@career_bp.post('/decision')
def decision():
    state = get_state()
    if not state or state.decision_used or not state.pending_event:
        return redirect(url_for('career.dashboard'))
    resolve_event(state, request.form.get('option_id', ''))
    save_state(state)
    return redirect(url_for('career.dashboard'))


@career_bp.post('/season')
def season():
    state = get_state()
    if not state or not state.decision_used:
        return redirect(url_for('career.dashboard'))
    simulate_season(state)
    save_state(state)
    return redirect(url_for('career.season_result'))


@career_bp.get('/season-result')
def season_result():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    return render_template('career_season_result.html', state=state, retirement_age=RETIREMENT_AGE,
                            team=team(state.team_id), market_value=market_value(state))


@career_bp.post('/next-season')
def next_season():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    if state.age >= RETIREMENT_AGE:
        state.status = 'retired'
        save_state(state)
        return redirect(url_for('career.retire'))
    advance(state)
    save_state(state)
    return redirect(url_for('career.dashboard'))


@career_bp.get('/international')
def international():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    eligible = eligible_competitions(state.nationality, state.age)
    return render_template('career_international.html', state=state, competitions=eligible,
                            country=country(state.nationality))


@career_bp.get('/history')
def history():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    rows = list(reversed(state.history))
    return render_template(
        'career_history.html', state=state, rows=rows,
        position_label=position_label(state.position), rating_tier=rating_tier,
    )


@career_bp.get('/retire')
def retire():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    return render_template(
        'career_retire.html', state=state, summary=career_summary(state),
        country=country(state.nationality), position_label=position_label(state.position),
        bats_label=bats_label(state.bats), team=team(state.team_id),
    )


@career_bp.post('/reset')
def reset():
    session.pop('career_state', None)
    session.pop('career_offers', None)
    return redirect(url_for('career.career_home'))
