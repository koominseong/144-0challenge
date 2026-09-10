from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import threading
from unified_achievements import MODE_ACHIEVEMENTS

from career import (
    TEAMS, COUNTRIES, get_state, save_state, new_state, generate_academy_offers,
    start_career, generate_event, resolve_event, simulate_season, advance_after_season,
    eligible_competitions, team, league, position_label, bats_label, country,
    POSITION_LABELS, BATS_LABELS, PACE_INFO, career_summary, market_value,
    rating_tier, ROLE_INFO, DIFFICULTY_INFO, team_badge, canonical_team_name,
    RETIREMENT_AGE, START_AGE, international_trophy_groups, ability_labels,
    ACHIEVEMENT_DEFS, check_achievements,
)
from career_storage import (
    create_account, authenticate, list_careers, create_career, load_career,
    list_achievements, leaderboard,
)

career_bp = Blueprint('career', __name__, url_prefix='/career')
_CAREER_ACTION_LOCKS = {}

def _career_lock(key):
    return _CAREER_ACTION_LOCKS.setdefault(str(key), threading.Lock())


def _logged_in():
    return bool(session.get('career_account_id'))


def _require_login():
    if not _logged_in():
        return redirect(url_for('career.login', next=request.path))
    return None


@career_bp.get('')
def career_home():
    if not _logged_in():
        return render_template('career_home.html', logged_out=True)
    try:
        careers = list_careers(session['career_account_id'])
    except Exception:
        careers = []
    # The account hub is intentionally always visible. A player can keep
    # several active careers and switch between them without overwriting the
    # currently selected device/session slot.
    return render_template('career_account.html', careers=careers, username=session.get('career_username',''))


@career_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        try:
            account = authenticate(username, password)
        except Exception:
            account = None
        if not account:
            return render_template('career_login.html', mode='login', error='아이디 또는 비밀번호가 올바르지 않습니다.')
        session['career_account_id'] = account['id']
        session['career_username'] = account['username']
        session.pop('career_id', None)
        session.pop('career_state', None)
        return redirect(request.args.get('next') or url_for('career.career_home'))
    return render_template('career_login.html', mode='login')


@career_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if password != password2:
            return render_template('career_login.html', mode='register', error='비밀번호가 서로 다릅니다.')
        try:
            account, error = create_account(username, password)
        except Exception as exc:
            account, error = None, 'db'
        if error:
            messages = {
                'username':'아이디는 2~24자로 입력해 주세요.',
                'password':'비밀번호는 4~72자로 입력해 주세요.',
                'exists':'이미 사용 중인 아이디입니다.',
                'db':'Supabase Career 테이블을 먼저 생성해 주세요.',
            }
            return render_template('career_login.html', mode='register', error=messages.get(error, '회원가입에 실패했습니다.'))
        session['career_account_id'] = account['id']
        session['career_username'] = account['username']
        session.pop('career_id', None)
        session.pop('career_state', None)
        return redirect(url_for('career.career_home'))
    return render_template('career_login.html', mode='register')


@career_bp.get('/logout')
def logout():
    return redirect(url_for('account.logout'))


@career_bp.route('/new', methods=['GET', 'POST'])
def career_new():
    guard = _require_login()
    if guard:
        return guard
    error = request.args.get('error')
    if request.method == 'POST':
        name = request.form.get('player_name')
        nationality = request.form.get('nationality')
        position = request.form.get('position')
        bats = request.form.get('bats')
        pace = request.form.get('pace')
        difficulty = request.form.get('difficulty', 'rookie')
        jersey_number = request.form.get('jersey_number', '1')
        valid_country = any(c.get('country_id') == nationality for c in COUNTRIES)
        if not (name or '').strip(): return redirect(url_for('career.career_new', error='name'))
        if not nationality or not valid_country: return redirect(url_for('career.career_new', error='nationality'))
        if position not in POSITION_LABELS: return redirect(url_for('career.career_new', error='position'))
        if bats not in BATS_LABELS: return redirect(url_for('career.career_new', error='bats'))
        if pace not in PACE_INFO: return redirect(url_for('career.career_new', error='pace'))
        if difficulty not in DIFFICULTY_INFO: return redirect(url_for('career.career_new', error='difficulty'))
        try: jersey_number = max(1, min(99, int(jersey_number)))
        except (TypeError, ValueError): return redirect(url_for('career.career_new', error='jersey'))
        state = new_state(name, nationality, position, bats, pace, difficulty, jersey_number)
        try:
            career_id = create_career(session['career_account_id'], state.__dict__.copy())
        except Exception:
            return render_template('career_new.html', countries=COUNTRIES, positions=POSITION_LABELS,
                bats_options=BATS_LABELS, pace_options=PACE_INFO, difficulty_options=DIFFICULTY_INFO,
                error='db')
        session['career_id'] = career_id
        session['career_state'] = None
        save_state(state)
        session.pop('career_offers', None)
        return redirect(url_for('career.offers'))
    return render_template('career_new.html', countries=COUNTRIES, positions=POSITION_LABELS,
                           bats_options=BATS_LABELS, pace_options=PACE_INFO, difficulty_options=DIFFICULTY_INFO, error=error)


@career_bp.get('/offers')
def offers():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    if state.team_id: return redirect(url_for('career.dashboard'))
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
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_new'))
    offer_list = session.get('career_offers') or []
    team_id = request.form.get('team_id')
    chosen = next((o for o in offer_list if o.get('team_id') == team_id), None)
    if not chosen: return redirect(url_for('career.offers'))
    start_career(state, chosen['team_id'], chosen['league_id'])
    simulate_season(state)
    advance_after_season(state)
    save_state(state)
    session.pop('career_offers', None)
    if state.status == 'retired': return redirect(url_for('career.retire'))
    return redirect(url_for('career.dashboard'))


def _timeline_rows(state):
    rows = [dict(r) for r in state.history]
    for i, r in enumerate(rows):
        r['team'] = canonical_team_name(r.get('team_id'), r.get('team', '무소속'))
        r['badge'] = team_badge(r.get('team_id'), r.get('team'))
        r['transferred_out'] = i + 1 < len(rows) and rows[i + 1].get('team_id') != r.get('team_id')
        r['tier'] = rating_tier(r.get('rating', 50))
    return rows


@career_bp.get('/switch/<career_id>')
def switch_career(career_id):
    guard = _require_login()
    if guard: return guard
    try:
        raw = load_career(session['career_account_id'], career_id)
    except Exception:
        raw = None
    if not raw:
        return redirect(url_for('career.career_home'))
    session['career_id'] = career_id
    session['career_state'] = raw
    return redirect(url_for('career.dashboard' if raw.get('team_id') else 'career.offers'))


@career_bp.get('/dashboard')
def dashboard():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    if not state.team_id: return redirect(url_for('career.offers'))
    if state.status == 'retired': return redirect(url_for('career.retire'))
    rows = _timeline_rows(state)
    last_age = rows[-1]['age'] if rows else state.age - 1
    future_ages = list(range(last_age + 1, RETIREMENT_AGE)) if not state.pending_event else list(range(state.age + 1, RETIREMENT_AGE))
    pending_age = state.age if state.pending_event else None
    if pending_age is not None and pending_age in future_ages: future_ages.remove(pending_age)
    try:
        achievements = list_achievements(session['career_account_id'])
    except Exception:
        achievements = []
    return render_template(
        'career_dashboard.html', state=state, team=team(state.team_id), team_badge=team_badge,
        league=league(state.league_id), country=country(state.nationality), position_label=position_label(state.position),
        bats_label=bats_label(state.bats), role_label=ROLE_INFO.get(state.role, {}).get('label', state.role),
        pace_label=PACE_INFO.get(state.pace, {}).get('label', state.pace), rating_tier=rating_tier(state.overall),
        difficulty_label=DIFFICULTY_INFO.get(state.difficulty, DIFFICULTY_INFO['pro'])['label'], market_value=market_value(state),
        rows=rows, pending_age=pending_age, future_ages=future_ages, achievements=achievements,
        trophy_groups=_trophy_groups(state), ovr_toast=session.pop('career_ovr_toast', None),
        trophy_toast=session.pop('career_trophy_toast', None), achievement_toasts=session.pop('career_achievement_toasts', []),
    )


@career_bp.post('/decision')
def decision():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state:
        return redirect(url_for('career.career_home'))
    with _career_lock(f'decision:{session.get("career_id")}'):
        # 더블클릭/브라우저 재전송/느린 DB 응답으로 같은 시즌이 두 번 진행되는 것을 막는다.
        if not state.pending_event or state.decision_used:
            return redirect(url_for('career.dashboard'))
        option_id = request.form.get('option_id', '')
        resolve_event(state, option_id)
        if state.status != 'retired':
            simulate_season(state)
            advance_after_season(state)
        save_state(state)
        if state.status == 'retired': return redirect(url_for('career.retire'))
        return redirect(url_for('career.dashboard'))

@career_bp.get('/international')
def international():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    eligible = eligible_competitions(state.nationality, state.age)
    return render_template('career_international.html', state=state, competitions=eligible,
                           country=country(state.nationality), trophy_groups=international_trophy_groups(state))


@career_bp.get('/history')
def history():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    rows = list(reversed(_timeline_rows(state)))
    return render_template('career_history.html', state=state, rows=rows,
                           position_label=position_label(state.position), rating_tier=rating_tier)


@career_bp.get('/player')
def player():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    abilities = [(key, label, state.abilities.get(key, 50)) for key, label in ability_labels(state.position)]
    return render_template('career_player.html', state=state, abilities=abilities, team=team(state.team_id),
                           country=country(state.nationality), position_label=position_label(state.position),
                           potential=state.potential, peak_overall=state.peak_overall)


@career_bp.get('/trophies')
def trophies():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    return render_template('career_trophies.html', state=state, groups=_trophy_groups(state),
                           international=international_trophy_groups(state), awards=state.individual_awards)


@career_bp.get('/achievements')
def achievements():
    guard = _require_login()
    if guard: return guard
    try:
        unlocked = {r['achievement_id'] for r in list_achievements(session['career_account_id'])}
    except Exception:
        unlocked = set()
    items = [dict(a, unlocked=a['id'] in unlocked) for a in ACHIEVEMENT_DEFS]
    known={a['id'] for a in ACHIEVEMENT_DEFS}
    for defs in MODE_ACHIEVEMENTS.values():
        known.update(a['id'] for a in defs)
    account_extra=[r for r in list_achievements(session['career_account_id']) if r.get('achievement_id') not in known]
    mode_items = {}
    for mode, defs in MODE_ACHIEVEMENTS.items():
        mode_items[mode] = [dict(a, unlocked=a['id'] in unlocked) for a in defs]
    return render_template('career_achievements.html', items=items, account_extra=account_extra,
                           unlocked_count=len(unlocked), total=len(items), mode_items=mode_items)


@career_bp.get('/records')
def records():
    guard = _require_login()
    if guard: return guard
    try: ranking = leaderboard(50)
    except Exception: ranking = []
    return render_template('career_records.html', ranking=ranking)


@career_bp.get('/retire')
def retire():
    guard = _require_login()
    if guard: return guard
    state = get_state()
    if not state: return redirect(url_for('career.career_home'))
    return render_template('career_retire.html', state=state, summary=career_summary(state),
                           country=country(state.nationality), position_label=position_label(state.position),
                           bats_label=bats_label(state.bats), team=team(state.team_id),
                           international_trophy_groups=international_trophy_groups(state), trophy_groups=_trophy_groups(state))


@career_bp.post('/reset')
def reset():
    # "Play again" creates a new independent slot rather than deleting every save.
    session.pop('career_id', None)
    session.pop('career_state', None)
    session.pop('career_offers', None)
    return redirect(url_for('career.career_new'))


def _trophy_groups(state):
    groups=[]
    # Every actual league gets its own cabinet section.
    league_order=[]
    for trophy in (state.club_trophies or []):
        if trophy.get('type') != 'league': continue
        lid=trophy.get('league_id') or state.league_id
        if lid not in league_order: league_order.append(lid)
    for lid in league_order:
        items=[t for t in (state.club_trophies or []) if t.get('type')=='league' and (t.get('league_id') or state.league_id)==lid]
        lname=(league(lid) or {}).get('name',lid)
        groups.append({'type':'league_'+str(lid),'icon':'🏆','name':lname,'count':len(items),'items':items})
    cup_order=[]
    for trophy in (state.club_trophies or []):
        if trophy.get('type') != 'cup': continue
        lid=trophy.get('league_id') or state.league_id
        if lid not in cup_order: cup_order.append(lid)
    for lid in cup_order:
        items=[t for t in (state.club_trophies or []) if t.get('type')=='cup' and (t.get('league_id') or state.league_id)==lid]
        groups.append({'type':'cup_'+str(lid),'icon':'🥇','name':f"{(league(lid) or {}).get('name',lid)} 국내 컵",'count':len(items),'items':items})
    cont=[t for t in (state.club_trophies or []) if t.get('type')=='continental']
    if cont: groups.append({'type':'continental','icon':'🌍','name':'대륙 클럽 대회','count':len(cont),'items':cont})
    intl=international_trophy_groups(state)
    for g in intl: groups.append({'type':'international_'+g['competition_id'],'icon':'🌐','name':g['name'],'count':g['count'],'items':g['items']})
    if not groups:
        groups=[{'type':'empty','icon':'🏆','name':'아직 획득한 트로피가 없습니다','count':0,'items':[]}]
    return groups

