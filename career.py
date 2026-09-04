import json, os, random
from dataclasses import dataclass, asdict
from flask import session

BASE = os.path.join(os.path.dirname(__file__), 'Data', 'Career')

def load(name, default=None):
    path = os.path.join(BASE, name)
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default if default is not None else []

TEAMS = load('career_teams.json')
LEAGUES = load('career_leagues.json')
COUNTRIES = load('career_countries.json')
COMPETITIONS = load('career_competitions.json')
FLAVOR = load('career_events.json', {})
RULES = load('career_rules.json', {})

# ---------------------------------------------------------------------------
# World model: league prestige tiers + each country's entry (academy) league
# and its domestic promotion ladder. Built from the real leagues/teams data.
# ---------------------------------------------------------------------------
LEAGUE_TIER = {
    'KR_IND': 1, 'KBO_FUTURES': 2, 'KBO': 5,
    'NPB_FARM': 2, 'NPB': 5,
    'RK': 1, 'A': 2, 'AA': 3, 'AAA': 4, 'MLB': 6,
    'CBL': 3, 'LMB': 3, 'CPBL': 3, 'LIDOM': 3, 'LVBP': 3, 'LBPRC': 2,
    'ABL': 3, 'HFD': 3, 'NIC': 2, 'COL': 2, 'PAN': 2, 'ITA': 3, 'CZE': 3, 'CUB': 4,
}

ENTRY_LEAGUE = {
    'KR': 'KR_IND', 'JP': 'NPB_FARM', 'US': 'RK', 'CN': 'CBL', 'MX': 'LMB',
    'TW': 'CPBL', 'DO': 'LIDOM', 'VE': 'LVBP', 'PR': 'LBPRC', 'AU': 'ABL',
    'NL': 'HFD', 'NI': 'NIC', 'CO': 'COL', 'PA': 'PAN', 'IT': 'ITA',
    'CZ': 'CZE', 'CU': 'CUB',
}

PROMOTION_PATH = {
    'KR': ['KR_IND', 'KBO_FUTURES', 'KBO'],
    'JP': ['NPB_FARM', 'NPB'],
    'US': ['RK', 'A', 'AA', 'AAA', 'MLB'],
}

PACE_INFO = {
    'focus': {'label': '집중', 'interval': 1, 'desc': '매 시즌 결정을 마주합니다.'},
    'normal': {'label': '보통', 'interval': 2, 'desc': '두 시즌마다 중요한 선택을 만납니다.'},
    'fast': {'label': '빠르게', 'interval': 3, 'desc': '세 시즌마다 중요한 선택을 만납니다.'},
}

ROLE_INFO = {
    'starter': {'label': '주전', 'games_mult': 1.15, 'growth_mult': 1.2},
    'rotation': {'label': '로테이션', 'games_mult': 1.0, 'growth_mult': 1.0},
    'bench': {'label': '벤치/후보', 'games_mult': 0.55, 'growth_mult': 0.7},
}


@dataclass
class CareerState:
    player_name: str = ''
    nationality: str = ''
    position: str = ''
    bats: str = 'R'
    league_id: str = ''
    team_id: str = ''
    age: int = 18
    season: int = 1
    year: int = 2026
    status: str = 'active'          # active | retired
    pace: str = 'normal'            # focus | normal | fast
    pace_counter: int = 0

    overall: int = 50               # long-term skill level (grows/declines)
    stamina: int = 85               # short-term condition, drives injury risk
    fame: int = 0
    loyalty: int = 60
    money: int = 0
    contract_years_left: int = 2
    role: str = 'rotation'          # starter | rotation | bench
    transfers_count: int = 0
    captain: bool = False
    injury_active: bool = False

    injuries: int = 0
    titles: int = 0
    international_caps: int = 0
    international_titles: int = 0
    career_games: int = 0
    career_hits: int = 0
    career_hr: int = 0
    career_rbi: int = 0
    career_wins: int = 0
    career_saves: int = 0
    career_era: float = 0.0

    decision_used: bool = False
    pending_event: dict = None
    last_event: str = ''
    last_result: str = ''
    last_decision: str = ''
    history: list = None

    def __post_init__(self):
        if self.history is None:
            self.history = []


def save_state(state):
    session['career_state'] = asdict(state)
    session.modified = True


def get_state():
    raw = session.get('career_state')
    if not raw:
        return None
    return CareerState(**raw)


POSITION_LABELS = {
    'SP': '선발투수', 'RP': '불펜투수', 'C': '포수', '1B': '1루수', '2B': '2루수',
    '3B': '3루수', 'SS': '유격수', 'LF': '좌익수', 'CF': '중견수', 'RF': '우익수', 'DH': '지명타자',
}
BATS_LABELS = {'R': '우타', 'L': '좌타', 'S': '스위치 히터'}

def position_label(position):
    return POSITION_LABELS.get(position, position or '-')

def bats_label(bats):
    return BATS_LABELS.get(bats, bats or '-')


def rating_tier(value):
    if value >= 88:
        return 'elite'
    if value >= 78:
        return 'high'
    if value >= 60:
        return 'mid'
    return 'low'


AWARD_DEFS = [
    ('titles', 1, '🏆', '우승 반지', '팀 우승을 1회 이상 경험했습니다.'),
    ('titles', 3, '🏆', '명문 구단의 핵심', '팀 우승 3회 이상을 달성했습니다.'),
    ('international_titles', 1, '🌍', '국가의 영웅', '국제대회에서 우승을 경험했습니다.'),
    ('international_caps', 30, '🎖️', '국가대표 단골', '국가대표 30경기 이상 출전했습니다.'),
    ('career_games', 1000, '🧢', '철인', '통산 1,000경기 이상 출전했습니다.'),
    ('fame', 80, '⭐', '슈퍼스타', '명성 80 이상을 기록했습니다.'),
]

def career_awards(state):
    out = []
    for f, threshold, icon, name, desc in AWARD_DEFS:
        if getattr(state, f, 0) >= threshold:
            out.append({'icon': icon, 'name': name, 'desc': desc})
    if state.transfers_count == 0 and state.season >= 5:
        out.append({'icon': '🧭', 'name': '원클럽맨', 'desc': '한 구단에서만 커리어를 이어갔습니다.'})
    if state.transfers_count >= 3:
        out.append({'icon': '✈️', 'name': '저니맨', 'desc': '3회 이상 이적하며 여러 팀을 거쳤습니다.'})
    return out

CLUB_CARD_PALETTE = ['card-red', 'card-blue', 'card-navy', 'card-gray', 'card-teal', 'card-purple']

def club_history(state):
    order, grouped = [], {}
    for entry in state.history:
        key = entry.get('team')
        if key not in grouped:
            grouped[key] = {
                'team': key, 'games': 0, 'primary': 0, 'secondary': 0,
                'titles': 0, 'seasons': 0, 'from_year': entry.get('year'), 'to_year': entry.get('year'),
            }
            order.append(key)
        g = grouped[key]
        g['games'] += entry.get('games', 0)
        g['primary'] += entry.get('primary', 0)
        g['secondary'] += entry.get('secondary', 0)
        g['titles'] += 1 if entry.get('champion') else 0
        g['seasons'] += 1
        g['to_year'] = entry.get('year')
    cards = []
    for i, key in enumerate(order):
        g = grouped[key]
        g['color'] = CLUB_CARD_PALETTE[i % len(CLUB_CARD_PALETTE)]
        cards.append(g)
    return cards

def market_value(state):
    base = (state.overall ** 2) * 420
    age_factor = 1.0
    if state.age > 32:
        age_factor -= (state.age - 32) * 0.07
    elif state.age < 23:
        age_factor += (23 - state.age) * 0.04
    value = base * max(0.25, age_factor) * (1 + state.fame / 220)
    return max(50000, round(value))

def career_score(state):
    return round(
        state.career_games * 2 + state.career_hr * 8 + state.career_rbi * 3 +
        state.career_hits * 1.2 + state.career_wins * 15 + state.career_saves * 10 +
        state.titles * 120 + state.international_titles * 200 + state.international_caps * 6 +
        state.fame * 10 + max(0, (90 - state.career_era * 8)) * (1 if state.position in ('SP', 'RP') else 0)
    )

def career_summary(state):
    is_pitcher = state.position in ('SP', 'RP')
    if is_pitcher:
        stat_labels = [('GAMES', state.career_games), ('WINS', state.career_wins), ('SAVES', state.career_saves)]
        extra_stat = ('ERA', state.career_era)
    else:
        stat_labels = [('GAMES', state.career_games), ('HR', state.career_hr), ('RBI', state.career_rbi)]
        extra_stat = ('HITS', state.career_hits)
    peak_rating = max([e.get('rating', state.overall) for e in state.history], default=state.overall)
    peak_value = max([e.get('market_value', 0) for e in state.history], default=market_value(state))
    return {
        'is_pitcher': is_pitcher,
        'stat_labels': stat_labels,
        'extra_stat': extra_stat,
        'rating': peak_rating,
        'rating_tier': rating_tier(peak_rating),
        'awards': career_awards(state),
        'clubs': club_history(state),
        'peak_value': peak_value,
        'career_score': career_score(state),
        'transfers': state.transfers_count,
    }


def team(team_id):
    return next((x for x in TEAMS if x.get('team_id') == team_id), None)

def league(league_id):
    return next((x for x in LEAGUES if x.get('league_id') == league_id), None)

def country(country_id):
    return next((x for x in COUNTRIES if x.get('country_id') == country_id or x.get('id') == country_id or x.get('code') == country_id), None)

def teams_in_league(league_id):
    return [t for t in TEAMS if t.get('league_id') == league_id]

def eligible_competitions(nationality, age):
    out = []
    for c in COMPETITIONS:
        min_age = c.get('min_age', 0)
        max_age = c.get('max_age', 99)
        if min_age <= age <= max_age:
            out.append(c)
    return out

def flavor(category):
    if isinstance(FLAVOR, dict):
        flavor_data = FLAVOR.get('flavor', {})
        if isinstance(flavor_data, dict):
            bank = flavor_data.get(category)
        else:
            bank = None
    else:
        bank = None

    return random.choice(bank or ['새로운 국면을 맞이했다.'])

# ---------------------------------------------------------------------------
# Career creation: name/nationality/position first, then 3 academy offers
# (mirrors Copero: pick your player, then choose among 3 starting clubs).
# ---------------------------------------------------------------------------

def new_state(name, nationality, position, bats, pace):
    clean_name = (name or '').strip() or '신인'
    pace = pace if pace in PACE_INFO else 'normal'
    return CareerState(player_name=clean_name, nationality=nationality, position=position,
                        bats=bats if bats in BATS_LABELS else 'R', pace=pace)

def generate_academy_offers(nationality):
    """Return 3 real-club academy offers from the player's home entry league."""
    entry_league_id = ENTRY_LEAGUE.get(nationality)
    pool = teams_in_league(entry_league_id) if entry_league_id else []
    if not pool:
        pool = TEAMS
    picks = random.sample(pool, min(3, len(pool)))
    tags = ['즉시 주전 기회', '주전 경쟁 치열', '체계적인 육성 시스템']
    random.shuffle(tags)
    offers = []
    for t, tag in zip(picks, tags):
        offers.append({'team_id': t.get('team_id'), 'name': t.get('name'), 'league_id': t.get('league_id'), 'tag': tag})
    return offers

def start_career(state, team_id, league_id):
    state.team_id = team_id
    state.league_id = league_id
    state.contract_years_left = 2
    state.role = 'bench'
    t = team(team_id)
    state.last_event = f"{t.get('name', team_id) if t else team_id}과(와) 유스 계약을 맺었다."
    return state


# ---------------------------------------------------------------------------
# Narrative event engine: pick the next decision point and resolve choices.
# ---------------------------------------------------------------------------

def _offer_candidates(state, count=2):
    cur_tier = LEAGUE_TIER.get(state.league_id, 1)
    ladder = PROMOTION_PATH.get(state.nationality)
    pool = []
    if ladder and state.league_id in ladder:
        idx = ladder.index(state.league_id)
        if idx + 1 < len(ladder):
            pool += teams_in_league(ladder[idx + 1])
        pool += teams_in_league(state.league_id)
    else:
        pool += [t for t in TEAMS if abs(LEAGUE_TIER.get(t.get('league_id'), cur_tier) - cur_tier) <= 1]
    pool = [t for t in pool if t.get('team_id') != state.team_id]
    if not pool:
        pool = [t for t in TEAMS if t.get('team_id') != state.team_id]
    return random.sample(pool, min(count, len(pool)))


def generate_event(state):
    """Priority-based picker for the next season's narrative decision point."""
    if state.injury_active:
        ev = {
            'type': 'injury',
            'title': '부상에서의 갈림길',
            'desc': flavor('injury'),
            'options': [
                {'id': 'early_return', 'label': '조기 복귀', 'detail': '출전은 빨리 재개하지만 재부상 위험이 남습니다.'},
                {'id': 'full_rehab', 'label': '충분한 재활', 'detail': '한동안 출전은 줄지만 몸 상태를 확실히 회복합니다.'},
            ],
        }
    elif state.contract_years_left <= 1:
        offers = _offer_candidates(state, 2)
        options = [{'id': 'renew', 'label': f"{(team(state.team_id) or {}).get('name','현재 구단')}와 재계약",
                    'detail': '충성도 상승 · 안정적인 역할 유지'}]
        for i, t in enumerate(offers):
            tier_now = LEAGUE_TIER.get(state.league_id, 1)
            tier_t = LEAGUE_TIER.get(t.get('league_id'), tier_now)
            move_desc = '상위 무대 도전 · 벤치 위험' if tier_t > tier_now else ('안정적인 주전 확보' if tier_t < tier_now else '동급 이적 · 새 출발')
            options.append({'id': f'offer_{i}', 'label': f"{t.get('name')} 이적", 'detail': move_desc,
                             'team_id': t.get('team_id'), 'league_id': t.get('league_id')})
        ev = {'type': 'contract', 'title': '계약이 만료됩니다', 'desc': flavor('contract'), 'options': options}
    elif eligible_competitions(state.nationality, state.age) and state.season >= 2 and random.random() < 0.35:
        ev = {
            'type': 'national_call',
            'title': '국가대표 소집',
            'desc': flavor('national_call'),
            'options': [
                {'id': 'accept', 'label': '국가대표 합류', 'detail': '대표팀 경력/명성 상승 · 체력 소모, 클럽 내 입지에는 부담'},
                {'id': 'decline', 'label': '클럽에 집중', 'detail': '클럽 우승 기회와 충성도를 지키지만 대표 경력은 미룹니다.'},
            ],
        }
    elif not state.captain and state.loyalty >= 65 and state.season >= 3 and random.random() < 0.3:
        ev = {
            'type': 'captain',
            'title': '주장 완장 제안',
            'desc': flavor('captain'),
            'options': [
                {'id': 'accept', 'label': '주장 수락', 'detail': '명성/충성도 상승 · 부담감으로 폼 기복 가능'},
                {'id': 'decline', 'label': '정중히 거절', 'detail': '부담 없이 선수 본연에 집중합니다.'},
            ],
        }
    elif state.role == 'bench' and random.random() < 0.4:
        loan_targets = _offer_candidates(state, 1)
        lt = loan_targets[0] if loan_targets else None
        ev = {
            'type': 'loan',
            'title': '임대 제안',
            'desc': flavor('loan'),
            'options': [
                {'id': 'loan', 'label': f"{(lt or {}).get('name','다른 구단')}(으)로 임대", 'detail': '출전 시간 확보 · 소속팀 입지는 불확실',
                 'team_id': (lt or {}).get('team_id'), 'league_id': (lt or {}).get('league_id')},
                {'id': 'stay', 'label': '팀에 잔류', 'detail': '벤치 경쟁을 이어가며 기회를 기다립니다.'},
            ],
        }
    else:
        ev = {
            'type': 'focus',
            'title': '이번 시즌의 준비',
            'desc': flavor('focus'),
            'options': [
                {'id': 'training', 'label': '집중 훈련', 'detail': '기량 +, 부상 위험 소폭 상승'},
                {'id': 'rest', 'label': '컨디션 관리', 'detail': '부상 위험 감소, 체력 회복'},
                {'id': 'media', 'label': '미디어 활동', 'detail': '명성 상승, 기량 변화 없음'},
            ],
        }
    return ev


def resolve_event(state, option_id):
    ev = state.pending_event or {}
    options = ev.get('options', [])
    chosen = next((o for o in options if o['id'] == option_id), options[0] if options else None)
    if not chosen:
        state.decision_used = True
        return state
    etype = ev.get('type')
    label = chosen['label']

    if etype == 'injury':
        if chosen['id'] == 'early_return':
            state.stamina = max(20, state.stamina - 10)
            state.overall = max(30, state.overall - 2)
        else:
            state.stamina = min(100, state.stamina + 20)
        state.injury_active = False

    elif etype == 'contract':
        if chosen['id'] == 'renew':
            state.contract_years_left = random.randint(2, 4)
            state.loyalty = min(100, state.loyalty + 12)
            state.fame = min(100, state.fame + 3)
        else:
            new_team, new_league = chosen.get('team_id'), chosen.get('league_id')
            tier_now = LEAGUE_TIER.get(state.league_id, 1)
            tier_new = LEAGUE_TIER.get(new_league, tier_now)
            state.team_id, state.league_id = new_team, new_league
            state.contract_years_left = random.randint(2, 3)
            state.transfers_count += 1
            state.loyalty = max(10, state.loyalty - 20)
            state.role = 'starter' if tier_new < tier_now else ('bench' if tier_new > tier_now else 'rotation')
            state.fame = min(100, state.fame + (6 if tier_new > tier_now else 2))

    elif etype == 'national_call':
        if chosen['id'] == 'accept':
            state.international_caps += 1
            state.fame = min(100, state.fame + 8)
            state.stamina = max(20, state.stamina - 8)
            state.loyalty = max(10, state.loyalty - 3)
            if random.random() < 0.18:
                state.international_titles += 1
                state.last_event = '국가대표팀 우승을 경험했다!'
        else:
            state.loyalty = min(100, state.loyalty + 5)

    elif etype == 'captain':
        if chosen['id'] == 'accept':
            state.captain = True
            state.fame = min(100, state.fame + 10)
            state.loyalty = min(100, state.loyalty + 10)
        # decline: no change

    elif etype == 'loan':
        if chosen['id'] == 'loan':
            state.team_id = chosen.get('team_id') or state.team_id
            state.league_id = chosen.get('league_id') or state.league_id
            state.role = 'starter'
            state.transfers_count += 1
        else:
            state.stamina = min(100, state.stamina + 5)

    elif etype == 'focus':
        if chosen['id'] == 'training':
            state.overall = min(99, state.overall + random.randint(1, 3))
            state.stamina = max(20, state.stamina - 5)
        elif chosen['id'] == 'rest':
            state.stamina = min(100, state.stamina + 12)
        elif chosen['id'] == 'media':
            state.fame = min(100, state.fame + 6)

    state.last_decision = label
    state.decision_used = True
    if not state.last_event or etype == 'contract':
        state.last_event = f'{label}을(를) 선택했다.'
    state.pending_event = None
    return state


def auto_offseason(state):
    """Used on pace-skip seasons: a light, non-interactive default action."""
    state.overall = min(99, state.overall + random.randint(0, 2))
    state.stamina = min(100, state.stamina + random.randint(2, 8))
    state.last_decision = '자동 진행'
    state.last_event = random.choice(FLAVOR.get('milestones', ['조용히 시즌을 준비했다.']))
    return state


def simulate_season(state):
    role_mult = ROLE_INFO.get(state.role, ROLE_INFO['rotation'])
    growth_noise = random.randint(-6, 10)
    growth = growth_noise * role_mult['growth_mult'] + (2 if state.age <= 24 else 0) - (2 if state.age >= 33 else 0)
    state.overall = max(30, min(99, round(state.overall + growth / 3)))
    strength = state.overall

    games_base = random.randint(95, 144)
    games = max(5, round(games_base * role_mult['games_mult']))

    if state.position in ('SP', 'RP'):
        wins = max(0, round(games * (0.02 + strength / 3200) + random.randint(-2, 5)))
        saves = max(0, round((strength - 48) / 8) + random.randint(0, 8)) if state.position == 'RP' else 0
        era = round(max(1.80, 6.0 - strength / 14 + random.uniform(-0.45, 0.45)), 2)
        hits = hr = rbi = 0
        state.career_wins += wins
        state.career_saves += saves
        state.career_era = round(((state.career_era * max(1, state.season - 1)) + era) / state.season, 2)
        line = f'{games}경기 · {wins}승 · {saves}세이브 · 평균자책 {era}'
        primary, secondary = wins, saves
    else:
        avg = max(.210, min(.390, .220 + strength / 900 + random.uniform(-.018, .018)))
        hits = round(games * 3.4 * avg)
        hr = max(0, round(games * (strength - 40) / 250 + random.randint(-3, 7)))
        rbi = max(0, round(hr * 2.8 + hits * .18 + random.randint(-8, 12)))
        state.career_hits += hits
        state.career_hr += hr
        state.career_rbi += rbi
        line = f'{games}경기 · 타율 {avg:.3f} · {hr}홈런 · {rbi}타점'
        primary, secondary = hr, rbi

    state.career_games += games
    team_obj = team(state.team_id) or {}
    title_chance = (strength + state.fame + (10 if state.role == 'starter' else 0)) / 190
    champion = random.random() < max(.06, min(.6, title_chance))
    if champion:
        state.titles += 1
        state.fame = min(100, state.fame + 8)
        line += ' · 팀 우승'

    injury_risk = max(.03, .16 - state.stamina / 700 - state.overall / 2000)
    injury = random.random() < injury_risk
    if injury:
        state.injuries += 1
        state.injury_active = True
        state.stamina = max(15, state.stamina - 15)
        line += ' · 시즌 중 부상'

    state.stamina = max(15, min(100, state.stamina - random.randint(3, 10)))
    state.contract_years_left = max(0, state.contract_years_left - 1)
    state.money += max(1000, 1500 + state.fame * 120)
    state.last_result = line

    state.history.append({
        'season': state.season, 'year': state.year, 'age': state.age,
        'team': team_obj.get('name', state.team_id), 'result': line,
        'decision': state.last_decision, 'rating': strength, 'games': games,
        'primary': primary, 'secondary': secondary, 'champion': champion,
        'injury': injury, 'market_value': market_value(state),
    })
    state.decision_used = False
    state.last_decision = ''
    return line


def advance(state):
    state.age += 1
    state.season += 1
    state.year += 1
    state.last_result = ''
    interval = PACE_INFO.get(state.pace, PACE_INFO['normal'])['interval']
    state.pace_counter += 1
    if state.pace_counter >= interval:
        state.pace_counter = 0
        state.pending_event = generate_event(state)
    else:
        auto_offseason(state)
        state.pending_event = None
        state.decision_used = True
    return state
