from flask import Blueprint, render_template, request, redirect, url_for, session
from career import (
    TEAMS, COUNTRIES, get_state, save_state, new_state, generate_academy_offers,
    start_career, generate_event, resolve_event, simulate_season, advance_after_season,
    eligible_competitions, team, league, position_label, bats_label, country,
    POSITION_LABELS, BATS_LABELS, PACE_INFO, career_summary, market_value,
    rating_tier, ROLE_INFO, DIFFICULTY_INFO, team_badge, canonical_team_name, RETIREMENT_AGE, START_AGE,
)

career_bp = Blueprint('career', __name__, url_prefix='/career')


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
        difficulty = request.form.get('difficulty', 'pro')
        jersey_number = request.form.get('jersey_number', '1')
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
        if difficulty not in DIFFICULTY_INFO:
            return redirect(url_for('career.career_new', error='difficulty'))
        try:
            jersey_number = max(1, min(99, int(jersey_number)))
        except (TypeError, ValueError):
            return redirect(url_for('career.career_new', error='jersey'))
        state = new_state(name, nationality, position, bats, pace, difficulty, jersey_number)
        save_state(state)
        session.pop('career_offers', None)
        return redirect(url_for('career.offers'))
    return render_template('career_new.html', countries=COUNTRIES, positions=POSITION_LABELS,
                            bats_options=BATS_LABELS, pace_options=PACE_INFO, difficulty_options=DIFFICULTY_INFO, error=error)


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
    # the academy signing immediately plays out its first season, Copero-style
    simulate_season(state)
    advance_after_season(state)
    save_state(state)
    session.pop('career_offers', None)
    if state.status == 'retired':
        return redirect(url_for('career.retire'))
    return redirect(url_for('career.dashboard'))


def _timeline_rows(state):
    rows = [dict(r) for r in state.history]
    for i, r in enumerate(rows):
        r['team'] = canonical_team_name(r.get('team_id'), r.get('team', '무소속'))
        r['badge'] = team_badge(r.get('team_id'), r.get('team'))
        r['transferred_out'] = i + 1 < len(rows) and rows[i + 1].get('team_id') != r.get('team_id')
        r['tier'] = rating_tier(r.get('rating', 50))
    return rows


@career_bp.get('/dashboard')
def dashboard():
    state = get_state()
    if not state:
        return redirect(url_for('career.career_new'))
    if not state.team_id:
        return redirect(url_for('career.offers'))
    if state.status == 'retired':
        return redirect(url_for('career.retire'))

    rows = _timeline_rows(state)
    last_age = rows[-1]['age'] if rows else state.age - 1
    future_ages = list(range(last_age + 1, RETIREMENT_AGE)) if not state.pending_event else \
        list(range(state.age + 1, RETIREMENT_AGE))
    # the "current" row (being decided) sits at state.age when a decision is pending
    pending_age = state.age if state.pending_event else None
    if pending_age is not None and pending_age in future_ages:
        future_ages.remove(pending_age)

    return render_template(
        'career_dashboard.html',
        state=state,
        team=team(state.team_id),
        team_badge=team_badge,
        league=league(state.league_id),
        country=country(state.nationality),
        position_label=position_label(state.position),
        bats_label=bats_label(state.bats),
        role_label=ROLE_INFO.get(state.role, {}).get('label', state.role),
        pace_label=PACE_INFO.get(state.pace, {}).get('label', state.pace),
        rating_tier=rating_tier(state.overall),
        difficulty_label=DIFFICULTY_INFO.get(state.difficulty, DIFFICULTY_INFO['pro'])['label'],
        market_value=market_value(state),
        rows=rows,
        pending_age=pending_age,
        future_ages=future_ages,
    )


@career_bp.post('/decision')
def decision():
    state = get_state()
    if not state or not state.pending_event:
        return redirect(url_for('career.dashboard'))
    resolve_event(state, request.form.get('option_id', ''))
    if state.status != 'retired':
        simulate_season(state)
        advance_after_season(state)
    save_state(state)
    if state.status == 'retired':
        return redirect(url_for('career.retire'))
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
    rows = list(reversed(_timeline_rows(state)))
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
