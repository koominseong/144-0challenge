from flask import Blueprint, render_template, request, redirect, url_for, session
from career import (TEAMS, LEAGUES, COUNTRIES, COMPETITIONS, EVENTS, get_state, save_state, new_state,
                     apply_decision, simulate_season, advance, eligible_competitions, team, league,
                     position_label, country, POSITION_LABELS)

career_bp = Blueprint('career', __name__, url_prefix='/career')

DECISION_LABELS = {
    'training': ('집중 훈련', '폼 +10 · 부상 위험 소폭 상승'),
    'rest': ('컨디션 관리', '부상 위험 감소 · 폼 소폭 상승'),
    'media': ('스타 마케팅', '명성 상승 · 폼 변화 없음'),
    'challenge': ('도전적인 역할 수락', '명성/폼 상승 · 부상 위험 상승'),
}

@career_bp.get('')
def career_home():
    state = get_state()
    if state:
        return redirect(url_for('career.dashboard'))
    return render_template('career_home.html')

@career_bp.route('/new', methods=['GET', 'POST'])
def career_new():
    error = request.args.get('error')
    if request.method == 'POST':
        state = new_state(request.form.get('player_name'), request.form.get('nationality'), request.form.get('league_id'), request.form.get('team_id'), request.form.get('position'))
        valid_team = any(t.get('team_id') == state.team_id and t.get('league_id') == state.league_id for t in TEAMS)
        valid_country = any(c.get('country_id') == state.nationality for c in COUNTRIES)
        valid_league = any(l.get('league_id') == state.league_id for l in LEAGUES)
        if state.player_name == '신인' and not (request.form.get('player_name') or '').strip():
            return redirect(url_for('career.career_new', error='name'))
        if not state.nationality or not valid_country:
            return redirect(url_for('career.career_new', error='nationality'))
        if not state.league_id or not valid_league:
            return redirect(url_for('career.career_new', error='league'))
        if not state.team_id or not valid_team:
            return redirect(url_for('career.career_new', error='team'))
        if state.position not in POSITION_LABELS:
            return redirect(url_for('career.career_new', error='position'))
        save_state(state)
        return redirect(url_for('career.dashboard'))
    return render_template('career_new.html', countries=COUNTRIES, leagues=LEAGUES, teams=TEAMS, error=error)

@career_bp.get('/dashboard')
def dashboard():
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    return render_template(
        'career_dashboard.html',
        state=state,
        team=team(state.team_id),
        league=league(state.league_id),
        country=country(state.nationality),
        position_label=position_label(state.position),
        decision_labels=DECISION_LABELS,
        competitions=eligible_competitions(state.nationality, state.age),
    )

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
    return render_template('career_international.html', state=state, competitions=eligible, country=country(state.nationality))

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
    if not state: return redirect(url_for('career.career_new'))
    return render_template('career_retire.html', state=state)

@career_bp.post('/reset')
def reset():
    session.pop('career_state', None)
    return redirect(url_for('career.career_home'))
