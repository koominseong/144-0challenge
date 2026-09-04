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
EVENTS = load('career_events.json')
RULES = load('career_rules.json', {})

@dataclass
class CareerState:
    player_name: str
    nationality: str
    league_id: str
    team_id: str
    position: str
    age: int = 18
    season: int = 1
    year: int = 2026
    status: str = 'active'
    decision_used: bool = False
    form: int = 50
    fame: int = 0
    money: int = 0
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

def position_label(position):
    return POSITION_LABELS.get(position, position or '-')


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
    for field, threshold, icon, name, desc in AWARD_DEFS:
        if getattr(state, field, 0) >= threshold:
            out.append({'icon': icon, 'name': name, 'desc': desc})
    return out

CLUB_CARD_PALETTE = ['card-red', 'card-blue', 'card-navy', 'card-gray', 'card-teal', 'card-purple']

def club_history(state):
    """Group per-season history entries by club for a career-highlights view."""
    order = []
    grouped = {}
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

def career_summary(state):
    is_pitcher = state.position in ('SP', 'RP')
    if is_pitcher:
        stat_labels = [('GAMES', state.career_games), ('WINS', state.career_wins), ('SAVES', state.career_saves)]
        extra_stat = ('ERA', state.career_era)
    else:
        stat_labels = [('GAMES', state.career_games), ('HR', state.career_hr), ('RBI', state.career_rbi)]
        extra_stat = ('HITS', state.career_hits)
    latest_rating = state.history[-1].get('rating', state.form) if state.history else state.form
    peak_rating = max([e.get('rating', state.form) for e in state.history], default=state.form)
    return {
        'is_pitcher': is_pitcher,
        'stat_labels': stat_labels,
        'extra_stat': extra_stat,
        'rating': peak_rating,
        'rating_tier': rating_tier(peak_rating),
        'latest_rating': latest_rating,
        'awards': career_awards(state),
        'clubs': club_history(state),
    }


def team(team_id):
    return next((x for x in TEAMS if x.get('team_id') == team_id), None)

def league(league_id):
    return next((x for x in LEAGUES if x.get('league_id') == league_id), None)

def country(country_id):
    return next((x for x in COUNTRIES if x.get('country_id') == country_id or x.get('id') == country_id or x.get('code') == country_id), None)

def eligible_competitions(nationality, age):
    out = []
    for c in COMPETITIONS:
        min_age = c.get('min_age', 0)
        max_age = c.get('max_age', 99)
        if min_age <= age <= max_age:
            out.append(c)
    return out

def new_state(name, nationality, league_id, team_id, position):
    clean_name = (name or '').strip() or '신인'
    return CareerState(clean_name, nationality, league_id, team_id, position)

def simulate_season(state):
    # Position-specific lightweight baseball simulation; no OVR dependency.
    strength = max(25, min(99, state.form + random.randint(-8, 12) + min(20, state.season // 2)))
    games = random.randint(95, 144)
    if state.position in ('SP', 'RP'):
        wins = max(0, round(games * (0.025 + strength / 3000) + random.randint(-2, 5)))
        saves = max(0, round((strength - 48) / 8) + random.randint(0, 8)) if state.position == 'RP' else 0
        era = round(max(1.80, 6.0 - strength / 14 + random.uniform(-0.45, 0.45)), 2)
        hits = hr = rbi = 0
        state.career_wins += wins
        state.career_saves += saves
        state.career_era = round(((state.career_era * max(1, state.season-1)) + era) / state.season, 2)
        line = f'{games}경기 · {wins}승 · {saves}세이브 · 평균자책 {era}'
        primary, secondary = wins, saves
    else:
        avg = max(.210, min(.390, .220 + strength / 900 + random.uniform(-.018, .018)))
        hits = round(games * 3.4 * avg)
        hr = max(0, round(games * (strength - 40) / 250 + random.randint(-3, 7)))
        rbi = max(0, round(hr * 2.8 + hits * .18 + random.randint(-8, 12)))
        wins = saves = 0
        state.career_hits += hits
        state.career_hr += hr
        state.career_rbi += rbi
        line = f'{games}경기 · 타율 {avg:.3f} · {hr}홈런 · {rbi}타점'
        primary, secondary = hr, rbi
    state.career_games += games
    team_obj = team(state.team_id) or {}
    title_chance = (strength + state.fame) / 170
    champion = random.random() < max(.08, min(.65, title_chance))
    if champion:
        state.titles += 1
        line += ' · 팀 우승'
    injury = random.random() < max(.03, .13 - state.form / 1000)
    if injury:
        state.injuries += 1
        line += ' · 부상 이탈'
    state.form = max(20, min(90, state.form + random.randint(-8, 10) + (5 if champion else 0) - (8 if injury else 0)))
    state.fame = max(0, state.fame + (8 if champion else 2) + (2 if state.form >= 70 else 0))
    state.money += max(1000, 1500 + state.fame * 120)
    state.last_result = line
    state.history.append({
        'season': state.season, 'year': state.year, 'age': state.age,
        'team': team_obj.get('name', state.team_id), 'result': line, 'decision': state.last_decision,
        'rating': strength, 'games': games, 'primary': primary, 'secondary': secondary,
        'champion': champion, 'injury': injury,
    })
    state.decision_used = False
    state.last_decision = ''
    return line

def apply_decision(state, decision):
    choices = {
        'training': ('집중 훈련', 10, -2, 0),
        'rest': ('컨디션 관리', 5, 3, 0),
        'media': ('스타 마케팅', 2, 0, 8),
        'challenge': ('도전적인 역할 수락', 7, -1, 5),
    }
    label, form_delta, injury_delta, fame_delta = choices.get(decision, choices['rest'])
    state.form = max(20, min(90, state.form + form_delta))
    state.injuries = max(0, state.injuries + injury_delta)
    state.fame = max(0, state.fame + fame_delta)
    state.last_decision = label
    state.decision_used = True
    state.last_event = f'{label}을 선택했다.'
    return state

def advance(state):
    state.age += 1
    state.season += 1
    state.year += 1
    state.last_result = ''
    state.last_event = random.choice([
        '구단이 다음 시즌 주전 경쟁을 예고했다.',
        '현지 언론이 당신을 차세대 스타로 조명했다.',
        '에이전트가 여러 구단의 관심을 전달했다.',
        '국가대표 예비 명단에 이름이 올랐다.',
        '팬들의 기대치가 크게 상승했다.'
    ])
    return state
