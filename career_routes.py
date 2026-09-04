from flask import Blueprint, render_template, request, redirect, url_for, session
from career import TEAMS, LEAGUES, COUNTRIES, COMPETITIONS, EVENTS, get_state, save_state, new_state, apply_decision, simulate_season, advance, eligible_competitions, team, league

career_bp = Blueprint('career', __name__, url_prefix='/career')

@career_bp.get('')
def career_home():
    return render_template('career_home.html', state=get_state())

@career_bp.route('/new', methods=['GET', 'POST'])
def career_new():
    if request.method == 'POST':
        state = new_state(request.form.get('player_name'), request.form.get('nationality'), request.form.get('league_id'), request.form.get('team_id'), request.form.get('position'))
        valid_team = any(t.get('team_id') == state.team_id and t.get('league_id') == state.league_id for t in TEAMS)
        valid_country = any(c.get('country_id') == state.nationality for c in COUNTRIES)
        valid_league = any(l.get('league_id') == state.league_id for l in LEAGUES)
        if not state.nationality or not state.league_id or not state.team_id or not valid_team or not valid_country or not valid_league:
            return redirect(url_for('career.career_new'))
        save_state(state)
        return redirect(url_for('career.dashboard'))
    return render_template('career_new.html', countries=COUNTRIES, leagues=LEAGUES, teams=TEAMS)

@career_bp.get('/dashboard')
def dashboard():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    return render_template('career_dashboard.html', state=state, team=team(state.team_id), league=league(state.league_id), competitions=eligible_competitions(state.nationality, state.age))

@career_bp.post('/decision')
def decision():
    state = get_state()
    if not state or state.decision_used: return redirect(url_for('career.dashboard'))
    apply_decision(state, request.form.get('decision', 'rest'))
    save_state(state)
    return redirect(url_for('career.dashboard'))

@career_bp.post('/season')
def season():
    state = get_state()
    if not state or not state.decision_used: return redirect(url_for('career.dashboard'))
    simulate_season(state)
    save_state(state)
    return redirect(url_for('career.season_result'))

@career_bp.get('/season-result')
def season_result():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    return render_template('career_season_result.html', state=state)

@career_bp.post('/next-season')
def next_season():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    if state.age >= 40:
        state.status = 'retired'
        save_state(state)
        return redirect(url_for('career.retire'))
    advance(state)
    save_state(state)
    return redirect(url_for('career.dashboard'))

@career_bp.get('/international')
def international():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    eligible = eligible_competitions(state.nationality, state.age)
    return render_template('career_international.html', state=state, competitions=eligible)

@career_bp.post('/international/play')
def international_play():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    eligible = eligible_competitions(state.nationality, state.age)
    requested = request.form.get('competition_id')
    event = next((c for c in eligible if c.get('competition_id') == requested), eligible[0] if eligible else None)
    if event:
        state.international_caps += 1
        if (state.fame + state.form + state.age) % 5 == 0:
            state.international_titles += 1
            state.last_event = f"{event.get('name','국제대회')}에서 대표팀 우승!"
        else:
            state.last_event = f"{event.get('name','국제대회')} 대표팀에 참가했다."
    save_state(state)
    return redirect(url_for('career.international'))

@career_bp.get('/retire')
def retire():
    state = get_state()
    return render_template('career_retire.html', state=state)

@career_bp.post('/reset')
def reset():
    session.pop('career_state', None)
    return redirect(url_for('career.career_home'))
