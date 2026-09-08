import json, os, random, re
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
# Canonical team registry
# team_id -> exact display name / league / logo is the single source of truth.
# ---------------------------------------------------------------------------
TEAM_REGISTRY = {t.get('team_id'): dict(t) for t in TEAMS if t.get('team_id')}
TEAM_ALIASES = {}
for _team in TEAMS:
    _tid = _team.get('team_id')
    for _value in (_team.get('name'), _team.get('logo_key'), _tid):
        if _value:
            TEAM_ALIASES[str(_value).strip().lower()] = _tid


def canonical_team_id(team_id=None, team_name=None):
    if team_id and team_id in TEAM_REGISTRY:
        return team_id
    if team_name:
        return TEAM_ALIASES.get(str(team_name).strip().lower())
    return None


def canonical_team_name(team_id=None, fallback='무소속'):
    tid = canonical_team_id(team_id)
    if tid:
        return TEAM_REGISTRY[tid].get('name', fallback)
    return fallback


def team_logo_filename(team_id):
    tid = canonical_team_id(team_id)
    return f'team_logo_{tid}.jpg' if tid else None

RETIREMENT_AGE = 40
START_AGE = 16

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

DIFFICULTY_INFO = {
    'rookie': {'label': '루키', 'desc': '성장이 빠르고 부상 부담이 낮습니다.', 'start_ovr': 56, 'growth_bonus': 1.0, 'injury_mult': 0.55},
    'pro': {'label': '프로', 'desc': '성장과 하락이 가장 균형 잡힌 기본 난이도입니다.', 'start_ovr': 53, 'growth_bonus': 0.0, 'injury_mult': 0.75},
    'legend': {'label': '레전드', 'desc': '성장 폭이 작고 전성기 이후 하락이 빠릅니다.', 'start_ovr': 50, 'growth_bonus': -0.5, 'injury_mult': 1.0},
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

BADGE_PALETTE = ['#8f2734', '#1f5fa8', '#1c2540', '#454b54', '#136a63', '#5e2f8a',
                 '#b97e1a', '#2f7fc4', '#7d3fce', '#0b433e', '#a83279', '#3c6e47']


ABILITY_GROUPS = {
    'hitter': [('contact', '컨택'), ('power', '파워'), ('eye', '선구안'), ('speed', '주력'), ('fielding', '수비'), ('arm', '송구')],
    'pitcher': [('velocity', '구속'), ('command', '제구'), ('breaking', '변화구'), ('stamina_skill', '지구력')],
}

def _initial_abilities(position, overall, potential):
    rng = random.Random(f'{position}:{overall}:{potential}')
    if position in ('SP', 'RP'):
        names = [k for k, _ in ABILITY_GROUPS['pitcher']]
    else:
        names = [k for k, _ in ABILITY_GROUPS['hitter']]
    out = {}
    for key in names:
        out[key] = max(25, min(99, int(overall + rng.randint(-7, 7))))
    return out

def ability_labels(position):
    return ABILITY_GROUPS['pitcher' if position in ('SP', 'RP') else 'hitter']

def _update_abilities(state, growth):
    if not state.abilities:
        state.abilities = _initial_abilities(state.position, state.overall, state.potential)
    direction = 1 if growth > 0 else -1 if growth < 0 else 0
    for key in list(state.abilities):
        step = direction * random.choice([0, 0, 1, 1, 2])
        state.abilities[key] = max(25, min(99, state.abilities[key] + step))
    # Keep the visible attributes broadly tied to OVR without making them identical.
    gap = state.overall - round(sum(state.abilities.values()) / max(1, len(state.abilities)))
    if abs(gap) >= 4:
        for key in state.abilities:
            state.abilities[key] = max(25, min(99, state.abilities[key] + (1 if gap > 0 else -1)))


@dataclass
class CareerState:
    player_name: str = ''
    nationality: str = ''
    position: str = ''
    bats: str = 'R'
    league_id: str = ''
    team_id: str = ''
    age: int = START_AGE
    season: int = 1
    year: int = 2026
    status: str = 'active'          # active | retired
    pace: str = 'normal'            # focus | normal | fast
    pace_counter: int = 0
    difficulty: str = 'pro'         # rookie | pro | legend
    jersey_number: int = 1          # 고정 등번호

    overall: int = 48               # long-term skill level (grows/declines)
    potential: int = 84              # soft ceiling; growth slows naturally as OVR approaches it
    abilities: dict = None            # visible player attributes
    stamina: int = 95               # short-term condition, drives injury risk
    fame: int = 0
    loyalty: int = 60
    money: int = 0
    role: str = 'rotation'          # starter | rotation | bench
    transfers_count: int = 0
    captain: bool = False
    injury_active: bool = False
    high_school_done: bool = False

    injuries: int = 0
    titles: int = 0
    league_titles: int = 0
    cup_titles: int = 0
    continental_titles: int = 0
    international_caps: int = 0
    international_titles: int = 0
    international_trophies: list = None  # tournament-specific national-team titles
    club_trophies: list = None          # league / domestic cup / continental cup
    individual_awards: list = None      # season-by-season personal awards
    last_mvp_race: dict = None          # latest MVP race result / candidates
    last_mvp_race: dict = None          # latest MVP race result / candidates
    achievement_log: list = None
    peak_overall: int = 48
    last_ovr: int = 48
    ovr_change: int = 0
    last_trophy: dict = None
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
        if self.international_trophies is None:
            self.international_trophies = []
        if self.club_trophies is None:
            self.club_trophies = []
        if self.individual_awards is None:
            self.individual_awards = []
        if self.achievement_log is None:
            self.achievement_log = []
        if self.abilities is None:
            self.abilities = _initial_abilities(self.position, self.overall, self.potential)
        if not self.peak_overall:
            self.peak_overall = self.overall
        if not self.last_ovr:
            self.last_ovr = self.overall


def _normalize_state(raw):
    data = dict(raw or {})
    tid = canonical_team_id(data.get('team_id'), data.get('team'))
    if tid:
        data['team_id'] = tid
        data['league_id'] = TEAM_REGISTRY[tid].get('league_id', data.get('league_id', ''))

    history = []
    for row in data.get('history') or []:
        r = dict(row)
        rid = canonical_team_id(r.get('team_id'), r.get('team'))
        if rid:
            r['team_id'] = rid
            r['league_id'] = TEAM_REGISTRY[rid].get('league_id', r.get('league_id', ''))
            r['team'] = TEAM_REGISTRY[rid].get('name', r.get('team', rid))
        history.append(r)
    data['history'] = history
    # Older saves only have the total count; keep them compatible.
    data.setdefault('international_trophies', [])
    data.setdefault('club_trophies', [])
    data.setdefault('individual_awards', [])
    data.setdefault('last_mvp_race', None)
    data.setdefault('last_mvp_race', None)
    data.setdefault('achievement_log', [])
    data.setdefault('league_titles', data.get('titles', 0))
    data.setdefault('cup_titles', 0)
    data.setdefault('continental_titles', 0)
    data.setdefault('potential', max(70, data.get('overall', 50) + 12))
    data.setdefault('peak_overall', data.get('overall', 50))
    data.setdefault('last_ovr', data.get('overall', 50))
    data.setdefault('ovr_change', 0)
    data.setdefault('last_trophy', None)
    if not data.get('abilities'):
        data['abilities'] = _initial_abilities(data.get('position',''), data.get('overall',50), data.get('potential',84))
    return data


def save_state(state):
    raw = _normalize_state(asdict(state))
    session['career_state'] = raw
    session.modified = True
    if state.ovr_change:
        session['career_ovr_toast'] = {
            'from': state.last_ovr, 'to': state.overall, 'delta': state.ovr_change,
        }
    if state.last_trophy:
        session['career_trophy_toast'] = dict(state.last_trophy)
    account_id = session.get('career_account_id')
    career_id = session.get('career_id')
    if account_id and career_id:
        try:
            from career_storage import save_career, unlock
            save_career(account_id, career_id, raw, career_score(state))
            unlocked = unlock(account_id, check_achievements(state))
            if unlocked:
                state.achievement_log = unlocked
                session['career_achievement_toasts'] = unlocked
                session['career_state'] = _normalize_state(asdict(state))
                session.modified = True
        except Exception:
            pass

def get_state():
    account_id = session.get('career_account_id')
    career_id = session.get('career_id')
    if account_id and career_id:
        try:
            from career_storage import load_career
            raw = load_career(account_id, career_id)
            if raw:
                raw = _normalize_state(raw)
                session['career_state'] = raw
                return CareerState(**raw)
        except Exception:
            pass
    raw = session.get('career_state')
    if not raw:
        return None
    return CareerState(**_normalize_state(raw))


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


def team_badge(team_id, name=None):
    tid = canonical_team_id(team_id, name)
    display_name = TEAM_REGISTRY.get(tid, {}).get('name', name or tid or '?')
    key = tid or display_name
    idx = sum(ord(c) for c in key) % len(BADGE_PALETTE)
    badge = {
        'text': display_name[:2] or '?',
        'color': BADGE_PALETTE[idx],
        'team_id': tid,
        'team_name': display_name,
        'logo': team_logo_filename(tid),
    }
    return badge


AWARD_DEFS = [
    ('titles', 1, '🏆', '우승 반지', '팀 우승을 1회 이상 경험했습니다.'),
    ('titles', 3, '🏆', '명문 구단의 핵심', '팀 우승 3회 이상을 달성했습니다.'),
    ('international_titles', 1, '🌍', '국가의 영웅', '국제대회에서 우승을 경험했습니다.'),
    ('international_caps', 30, '🎖️', '국가대표 단골', '국가대표 30경기 이상 출전했습니다.'),
    ('career_games', 1000, '🧢', '철인', '통산 1,000경기 이상 출전했습니다.'),
    ('fame', 80, '⭐', '슈퍼스타', '명성 80 이상을 기록했습니다.'),
]

ACHIEVEMENT_DEFS = [
    {'id':'first_pro','name':'프로의 첫걸음','desc':'첫 프로 시즌을 완료하세요.','icon':'⚾'},
    {'id':'ovr70','name':'주목받는 유망주','desc':'OVR 70에 도달하세요.','icon':'🌟'},
    {'id':'ovr80','name':'리그의 스타','desc':'OVR 80에 도달하세요.','icon':'⭐'},
    {'id':'ovr90','name':'괴물의 탄생','desc':'OVR 90에 도달하세요.','icon':'👑'},
    {'id':'peak95','name':'95의 벽을 넘다','desc':'커리어 최고 OVR 95를 기록하세요.','icon':'💎'},
    {'id':'league1','name':'첫 우승','desc':'리그 우승을 차지하세요.','icon':'🏆'},
    {'id':'league5','name':'왕조의 시작','desc':'리그 우승 5회를 기록하세요.','icon':'🏰'},
    {'id':'cup1','name':'컵을 들어 올리다','desc':'국내 컵 우승을 차지하세요.','icon':'🥇'},
    {'id':'continental1','name':'대륙의 정상','desc':'대륙 대회 우승을 차지하세요.','icon':'🌍'},
    {'id':'intl1','name':'국가의 영웅','desc':'국가대표 대회 우승을 경험하세요.','icon':'🌐'},
    {'id':'award5','name':'수상 수집가','desc':'개인 수상 5개를 모으세요.','icon':'🎖️'},
    {'id':'mvp1','name':'리그 MVP','desc':'MVP를 수상하세요.','icon':'👑'},
    {'id':'hr100','name':'거포','desc':'통산 100홈런을 기록하세요.','icon':'💥'},
    {'id':'hit1000','name':'안타 제조기','desc':'통산 1,000안타를 기록하세요.','icon':'🧢'},
    {'id':'win100','name':'100승 클럽','desc':'통산 100승을 기록하세요.','icon':'🔥'},
    {'id':'save100','name':'마무리의 자격','desc':'통산 100세이브를 기록하세요.','icon':'🚪'},
    {'id':'games1000','name':'철인','desc':'통산 1,000경기에 출전하세요.','icon':'🦾'},
    {'id':'transfer5','name':'세계일주','desc':'5회 이상 이적하세요.','icon':'✈️'},
    {'id':'oneclub','name':'원클럽맨','desc':'5시즌 이상 한 팀에서 뛰세요.','icon':'❤️'},
    {'id':'captain','name':'주장 완장','desc':'주장이 되세요.','icon':'🎽'},
    {'id':'allstar5','name':'단골 올스타','desc':'올스타 5회 이상을 기록하세요.','icon':'✨'},
    {'id':'retire','name':'마지막 타석','desc':'40세까지 커리어를 완주하세요.','icon':'🏁'},
]

def check_achievements(state):
    vals = {a['id']: False for a in ACHIEVEMENT_DEFS}
    vals['first_pro'] = bool(state.history)
    vals['ovr70'] = state.peak_overall >= 70
    vals['ovr80'] = state.peak_overall >= 80
    vals['ovr90'] = state.peak_overall >= 90
    vals['peak95'] = state.peak_overall >= 95
    vals['league1'] = state.league_titles >= 1
    vals['league5'] = state.league_titles >= 5
    vals['cup1'] = state.cup_titles >= 1
    vals['continental1'] = state.continental_titles >= 1
    vals['intl1'] = state.international_titles >= 1
    vals['award5'] = len(state.individual_awards) >= 5
    vals['mvp1'] = any(a.get('award_id') == 'MVP' for a in state.individual_awards)
    vals['hr100'] = state.career_hr >= 100
    vals['hit1000'] = state.career_hits >= 1000
    vals['win100'] = state.career_wins >= 100
    vals['save100'] = state.career_saves >= 100
    vals['games1000'] = state.career_games >= 1000
    vals['transfer5'] = state.transfers_count >= 5
    vals['oneclub'] = any(c.get('seasons',0) >= 5 for c in club_history(state))
    vals['captain'] = state.captain
    vals['allstar5'] = sum(1 for a in state.individual_awards if a.get('award_id') == 'ALL_STAR') >= 5
    vals['retire'] = state.status == 'retired'
    return [dict(a, unlocked=True) for a in ACHIEVEMENT_DEFS if vals.get(a['id'])]


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
        g['badge'] = team_badge(None, key)
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

def international_trophy_groups(state):
    """Group national-team trophies by the actual international tournament."""
    order = []
    groups = {}
    for t in (state.international_trophies or []):
        if isinstance(t, str):
            cid, cname, year = 'LEGACY', t, '-'
        else:
            cid = t.get('competition_id', 'INTL')
            cname = t.get('competition_name', t.get('name', '국제대회'))
            year = t.get('year', '-')
        if cid not in groups:
            groups[cid] = {'competition_id': cid, 'name': cname, 'count': 0, 'items': []}
            order.append(cid)
        groups[cid]['count'] += 1
        groups[cid]['items'].append({'name': cname, 'year': year})
    return [groups[cid] for cid in order]

def career_score(state):
    return round(
        state.career_games * 2 + state.career_hr * 8 + state.career_rbi * 3 +
        state.career_hits * 1.2 + state.career_wins * 15 + state.career_saves * 10 +
        state.titles * 120 + state.international_titles * 200 + state.international_caps * 6 +
        len(state.individual_awards) * 80 + state.continental_titles * 100 +
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
    tid = canonical_team_id(team_id)
    return TEAM_REGISTRY.get(tid) if tid else None

def league(league_id):
    return next((x for x in LEAGUES if x.get('league_id') == league_id), None)

def country(country_id):
    return next((x for x in COUNTRIES if x.get('country_id') == country_id or x.get('id') == country_id or x.get('code') == country_id), None)

def teams_in_league(league_id):
    return [t for t in TEAMS if t.get('league_id') == league_id]

def eligible_competitions(nationality, age, year=None):
    """Return national-team competitions that make sense for this season.

    National-team duty is intentionally sparse: senior competitions only appear
    in their rough real-world cycles, while U18/U23 are limited by age.
    """
    year = year or 2026
    out = []
    for c in COMPETITIONS:
        name = str(c.get('name', '')).lower()
        min_age = c.get('min_age', 0)
        max_age = c.get('max_age', 99)
        if not (min_age <= age <= max_age):
            if 'u-23' in name or 'u23' in name:
                if age > 23:
                    continue
            elif 'u-18' in name or 'u18' in name:
                if age > 18:
                    continue
            else:
                continue

        # Keep national duty from becoming an annual event.
        if 'world baseball classic' in name:
            if (year - 2026) % 3 != 0:
                continue
        elif 'premier12' in name:
            if (year - 2027) % 4 != 0:
                continue
        elif 'olympic' in name:
            if (year - 2028) % 4 != 0:
                continue
        elif 'asian games' in name:
            if (year - 2026) % 4 != 0:
                continue
        elif 'u-23' in name or 'u23' in name:
            if age > 23 or year % 2 == 0:
                continue
        elif 'u-18' in name or 'u18' in name:
            if age > 18:
                continue

        out.append(c)
    return out


def _national_selection_probability(state):
    """Small automatic selection chance driven mainly by OVR."""
    if state.age < 18 or state.overall < 65:
        return 0.0
    # OVR is the main selector; fame is only a light tie-breaker.
    chance = 0.025 + max(0, state.overall - 65) * 0.007
    chance += min(0.035, state.fame * 0.00035)
    if state.overall >= 85:
        chance += 0.025
    return min(0.24, chance)


def _maybe_national_team_selection(state):
    """Rare, mostly automatic national-team call-up.

    This runs once per simulated season and selects at most one competition.
    The player does not choose in the normal case; the game simply decides
    whether the player made the roster based on ability.
    """
    if getattr(state, 'status', 'active') == 'retired':
        return False
    competitions = eligible_competitions(state.nationality, state.age, state.year)
    if not competitions:
        return False
    chance = _national_selection_probability(state)
    if random.random() >= chance:
        return False

    competition = random.choice(competitions)
    state.international_caps += 1
    if random.random() < (0.08 + max(0, state.overall - 70) * 0.004):
        state.international_titles += 1
        trophy = {
            'competition_id': competition.get('competition_id', 'INTL'),
            'competition_name': competition.get('name', '국제대회'),
            'year': state.year,
            'age': state.age,
        }
        state.international_trophies.append(trophy)
        state.last_trophy = {'type':'international', 'category':'국가대표', 'name':competition.get('name', '국제대회') + ' 우승', 'year':state.year}
        state.last_event = f'{competition.get("name", "국제대회")}에서 대표팀 우승을 경험했다!'
    else:
        state.last_event = f'{competition.get("name", "국제대회")} 대표팀에 자동 차출됐다.'
    state.fame = min(100, state.fame + 4)
    state.stamina = max(20, state.stamina - 4)
    return True

def flavor(category):
    bank = None
    if isinstance(FLAVOR, dict) and isinstance(FLAVOR.get('flavor'), dict):
        bank = FLAVOR['flavor'].get(category)
    if not bank or not isinstance(bank, list):
        return '새로운 국면을 맞이했다.'
    return random.choice(bank)


# ---------------------------------------------------------------------------
# Career creation: name/nationality/position first, then 3 academy offers
# (mirrors Copero: pick your player, then choose among 3 starting clubs).
# ---------------------------------------------------------------------------

def new_state(name, nationality, position, bats, pace, difficulty='pro', jersey_number=1):
    clean_name = (name or '').strip() or '신인'
    pace = pace if pace in PACE_INFO else 'normal'
    difficulty = difficulty if difficulty in DIFFICULTY_INFO else 'pro'
    try:
        jersey_number = int(jersey_number)
    except (TypeError, ValueError):
        jersey_number = 1
    jersey_number = max(1, min(99, jersey_number))
    start_ovr = DIFFICULTY_INFO[difficulty]['start_ovr']
    potential = random.randint(86, 96) if difficulty == 'rookie' else random.randint(82, 94) if difficulty == 'pro' else random.randint(78, 91)
    return CareerState(
        player_name=clean_name, nationality=nationality, position=position,
        bats=bats if bats in BATS_LABELS else 'R', pace=pace,
        difficulty=difficulty, jersey_number=jersey_number, overall=start_ovr,
        potential=potential, peak_overall=start_ovr, last_ovr=start_ovr,
        abilities=_initial_abilities(position, start_ovr, potential)
    )

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
        offers.append({
            'team_id': t.get('team_id'), 'name': t.get('name'), 'league_id': t.get('league_id'), 'tag': tag,
            'badge': team_badge(t.get('team_id'), t.get('name')),
        })
    return offers

def start_career(state, team_id, league_id):
    state.team_id = team_id
    state.league_id = league_id
    state.role = 'rotation'
    t = team(team_id)
    state.last_event = f"{t.get('name', team_id) if t else team_id}과(와) 유스 계약을 맺었다."
    return state


# ---------------------------------------------------------------------------
# Narrative event engine: pick the next decision point and resolve choices.
# ---------------------------------------------------------------------------

def _offer_candidates(state, count=2):
    """OVR와 리그 수준이 맞는 현실적인 이적 제안을 만든다."""
    cur_tier = LEAGUE_TIER.get(state.league_id, 1)
    ovr = state.overall

    # 리그에 진입하기 위해 필요한 대략적인 OVR.
    min_ovr_by_tier = {1: 50, 2: 55, 3: 60, 4: 66, 5: 70, 6: 80}
    max_reasonable_tier = max(
        tier for tier, minimum in min_ovr_by_tier.items() if ovr >= minimum
    )

    pool = []
    for t in TEAMS:
        tid = t.get('team_id')
        lid = t.get('league_id')
        if not tid or tid == state.team_id:
            continue
        tier = LEAGUE_TIER.get(lid, 1)

        # OVR보다 한 단계 이상 높은 리그는 일반 제안에서 제외한다.
        if tier > max_reasonable_tier:
            continue

        # 현재 수준에서 너무 동떨어진 하위팀도 무작정 제안하지 않는다.
        if tier < cur_tier - 1:
            continue

        # 한 단계 상승은 가능하지만 OVR이 낮으면 확률적으로만 허용한다.
        if tier == cur_tier + 1 and ovr < min_ovr_by_tier.get(tier, 99) + 2:
            if random.random() > 0.22:
                continue

        pool.append(t)

    # 같은 리그가 너무 많이 나오지 않으면서도 OVR에 맞는 팀을 우선한다.
    def _score(t):
        tier = LEAGUE_TIER.get(t.get('league_id'), cur_tier)
        score = random.random() * 5
        if tier == cur_tier:
            score += 18
        elif tier == cur_tier + 1:
            score += 17
        elif tier == cur_tier - 1:
            score += 8
        else:
            score -= abs(tier - cur_tier) * 4

        # OVR과 리그의 적합도가 높을수록 우선.
        gap = ovr - min_ovr_by_tier.get(tier, 50)
        score += max(-10, min(10, gap * 0.45))

        # KBO/NPB는 70+, MLB는 80+부터 정상적인 상위 선택지로 취급.
        if t.get('league_id') in ('KBO', 'NPB'):
            score += 4 if ovr >= 70 else -8
        elif t.get('league_id') == 'MLB':
            score += 7 if ovr >= 80 else -15
        return score

    pool.sort(key=_score, reverse=True)
    if not pool:
        pool = [t for t in TEAMS if t.get('team_id') != state.team_id]

    chosen, used = [], set()
    # 우선 현재 수준/한 단계 상승을 섞고, 나머지는 적합도 순으로 채운다.
    buckets = {
        'same': [t for t in pool if LEAGUE_TIER.get(t.get('league_id'), cur_tier) == cur_tier],
        'up': [t for t in pool if LEAGUE_TIER.get(t.get('league_id'), cur_tier) == cur_tier + 1],
        'other': [t for t in pool if LEAGUE_TIER.get(t.get('league_id'), cur_tier) != cur_tier and LEAGUE_TIER.get(t.get('league_id'), cur_tier) != cur_tier + 1],
    }
    for key in ('same', 'up', 'other'):
        candidates = [t for t in buckets[key] if t.get('team_id') not in used]
        if candidates and len(chosen) < count:
            pick = random.choice(candidates)
            chosen.append(pick)
            used.add(pick.get('team_id'))

    for t in pool:
        if len(chosen) >= count:
            break
        if t.get('team_id') not in used:
            chosen.append(t)
            used.add(t.get('team_id'))
    return chosen[:count]

def _club_option(t, tier_now):
    tier_t = LEAGUE_TIER.get(t.get('league_id'), tier_now)
    if tier_t > tier_now:
        detail = '상위 무대 도전 · 벤치 위험'
    elif tier_t < tier_now:
        detail = '안정적인 주전 확보'
    else:
        detail = '동급 이적 · 새 출발'
    return {
        'id': f"club_{t.get('team_id')}", 'kind': 'club', 'label': f"{t.get('name')}(으)로 이적",
        'detail': detail, 'team_id': t.get('team_id'), 'league_id': t.get('league_id'),
        'name': t.get('name'), 'league_name': (league(t.get('league_id')) or {}).get('name', ''),
        'badge': team_badge(t.get('team_id'), t.get('name')),
    }


def generate_event(state):
    """Priority-based picker for the next season's narrative decision point."""
    if state.injury_active:
        return {
            'type': 'injury', 'title': '부상에서의 갈림길', 'desc': flavor('injury'),
            'options': [
                {'id': 'early_return', 'kind': 'plain', 'icon': '⚡', 'label': '조기 복귀',
                 'detail': '출전은 빨리 재개하지만 재부상 위험이 남습니다.'},
                {'id': 'full_rehab', 'kind': 'plain', 'icon': '🩹', 'label': '충분한 재활',
                 'detail': '한동안 출전은 줄지만 몸 상태를 확실히 회복합니다.'},
            ],
        }

    if not state.high_school_done and 17 <= state.age <= 19 and random.random() < 0.22:
        state.high_school_done = True
        return {
            'type': 'high_school', 'title': '학업과 커리어 사이', 'desc': flavor('focus') if False else
            '학업을 마저 끝낼지, 야구에만 전념할지 결정할 시간이다.',
            'options': [
                {'id': 'accept', 'kind': 'plain', 'icon': '🎓', 'label': '학업 병행',
                 'detail': '일시적으로 OVR -1, 대신 정신적으로 안정되어 충성도가 오릅니다.'},
                {'id': 'reject', 'kind': 'plain', 'icon': '⚾', 'label': '야구에 전념',
                 'detail': '변화 없이 훈련에 집중합니다.'},
            ],
        }

    if not state.captain and state.loyalty >= 65 and state.season >= 3 and random.random() < 0.18:
        return {
            'type': 'captain', 'title': '주장 완장 제안', 'desc': flavor('captain'),
            'options': [
                {'id': 'accept', 'kind': 'plain', 'icon': '🎖️', 'label': '주장 수락',
                 'detail': '명성/충성도 상승 · 부담감으로 폼 기복 가능'},
                {'id': 'decline', 'kind': 'plain', 'icon': '🙅', 'label': '정중히 거절',
                 'detail': '부담 없이 선수 본연에 집중합니다.'},
            ],
        }

    # National-team duty is normally automatic.  A user-choice call-up is
    # intentionally rare and only appears when the player is genuinely good
    # enough to be in the conversation.
    if (state.overall >= 72 and state.age >= 19 and
            eligible_competitions(state.nationality, state.age, state.year) and
            random.random() < 0.035):
        competition = random.choice(eligible_competitions(state.nationality, state.age, state.year))
        return {
            'type': 'national_call', 'title': '국가대표 합류 여부', 'desc':
                f'{competition.get("name", "국제대회")} 대표팀 선발 경쟁에 이름을 올렸다. 이번에는 직접 결정할 수 있다.',
            'competition': competition,
            'options': [
                {'id': 'accept', 'kind': 'plain', 'icon': '🌍', 'label': '국가대표 합류',
                 'detail': '대표팀 경력/명성 상승 · 체력 소모'},
                {'id': 'decline', 'kind': 'plain', 'icon': '🏟️', 'label': '클럽에 집중',
                 'detail': '이번 소집을 고사하고 클럽 시즌에 집중합니다.'},
            ],
        }

    if state.fame >= 40 and state.age >= 23 and random.random() < 0.12:
        alt = _offer_candidates(state, 1)
        alt_t = alt[0] if alt else None
        cur = team(state.team_id) or {}
        options = [
            {'id': 'fight', 'kind': 'plain', 'icon': '💢', 'label': f"{cur.get('name','현 구단')}에서 버티기",
             'detail': '일시적으로 OVR -2 (심리적 압박), 버텨내면 팬 신뢰 회복'},
        ]
        if alt_t:
            options.append(_club_option(alt_t, LEAGUE_TIER.get(state.league_id, 1)) | {
                'id': 'leave', 'label': f"{alt_t.get('name')}(으)로 떠나기", 'detail': '새 출발 · 이적 기록 +1',
            })
        return {'type': 'fan_backlash', 'title': '팬들의 반발', 'desc': flavor('injury') if False else
                '최근 부진으로 팬들이 당신의 입지에 의문을 제기하기 시작했다.', 'options': options}

    # default: transfer window (stay + 2 real-club offers), every decision point
    tier_now = LEAGUE_TIER.get(state.league_id, 1)
    offers = _offer_candidates(state, 2)
    cur = team(state.team_id) or {}
    options = [{
        'id': 'stay', 'kind': 'club', 'label': f"{cur.get('name','현재 구단')}에 잔류",
        'detail': '안정적인 역할 유지', 'team_id': state.team_id, 'league_id': state.league_id,
        'name': cur.get('name', '현재 구단'), 'league_name': (league(state.league_id) or {}).get('name', ''),
        'badge': team_badge(state.team_id, cur.get('name')), 'stay': True,
    }]
    for t in offers:
        options.append(_club_option(t, tier_now))
    if state.age >= 34:
        options.append({'id': 'retire_now', 'kind': 'plain', 'icon': '🏁', 'label': '은퇴 결심',
                         'detail': '지금까지의 커리어를 마무리합니다.'})
    return {
        'type': 'transfer_window', 'title': '이적 시장이 열렸다', 'desc': flavor('contract'),
        'options': options,
    }


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

    elif etype == 'high_school':
        if chosen['id'] == 'accept':
            state.overall = max(30, state.overall - 1)
            state.loyalty = min(100, state.loyalty + 8)

    elif etype == 'captain':
        if chosen['id'] == 'accept':
            state.captain = True
            state.fame = min(100, state.fame + 10)
            state.loyalty = min(100, state.loyalty + 10)

    elif etype == 'national_call':
        if chosen['id'] == 'accept':
            state.international_caps += 1
            state.fame = min(100, state.fame + 8)
            state.stamina = max(20, state.stamina - 8)
            state.loyalty = max(10, state.loyalty - 3)
            if random.random() < 0.18:
                state.international_titles += 1
                competition = ev.get('competition') or {}
                trophy = {
                    'competition_id': competition.get('competition_id', 'INTL'),
                    'competition_name': competition.get('name', '국제대회'),
                    'year': state.year,
                    'age': state.age,
                }
                state.international_trophies.append(trophy)
                state.last_trophy = {'type':'international', 'category':'국가대표', 'name':competition.get('name', '국제대회') + ' 우승', 'year':state.year}
                state.last_event = f'{competition.get("name", "국제대회")} 우승을 경험했다!'
        else:
            state.loyalty = min(100, state.loyalty + 5)

    elif etype == 'fan_backlash':
        if chosen['id'] == 'fight':
            state.overall = max(30, state.overall - 2)
            state.loyalty = min(100, state.loyalty + 15)
        else:
            state.team_id = chosen.get('team_id') or state.team_id
            state.league_id = chosen.get('league_id') or state.league_id
            state.transfers_count += 1
            state.loyalty = max(10, state.loyalty - 15)
            state.fame = min(100, state.fame + 2)

    elif etype == 'transfer_window':
        if chosen['id'] == 'retire_now':
            state.status = 'retired'
        elif chosen.get('stay'):
            state.loyalty = min(100, state.loyalty + 6)
            state.fame = min(100, state.fame + 1)
        else:
            new_team, new_league = chosen.get('team_id'), chosen.get('league_id')
            tier_now = LEAGUE_TIER.get(state.league_id, 1)
            tier_new = LEAGUE_TIER.get(new_league, tier_now)
            state.team_id, state.league_id = new_team, new_league
            state.transfers_count += 1
            state.loyalty = max(10, state.loyalty - 20)
            state.role = 'starter' if tier_new < tier_now else ('bench' if tier_new > tier_now else 'rotation')
            state.fame = min(100, state.fame + (6 if tier_new > tier_now else 2))

    state.last_decision = label
    state.decision_used = True
    if not state.last_event or etype in ('transfer_window', 'fan_backlash'):
        state.last_event = f'{label}을(를) 선택했다.'
    state.pending_event = None
    return state


def _mvp_score(state, games, extra, champion=False):
    """Convert one season's actual production into an MVP ballot score.

    MVP is no longer a random award.  The player's season is compared with
    four generated league competitors.  The formula rewards production first,
    then quality/availability and finally team success.
    """
    ovr = state.overall
    if state.position in ('SP', 'RP'):
        era = extra.get('era', 6.0)
        wins = extra.get('wins', 0)
        saves = extra.get('saves', 0)
        so = extra.get('so', 0)
        innings = extra.get('innings', 0)
        if state.position == 'SP':
            score = (
                wins * 4.0 + max(0, 4.60 - era) * 17.0 + so * 0.055
                + innings * 0.025 + ovr * 0.38
            )
        else:
            score = (
                saves * 2.0 + max(0, 4.20 - era) * 15.0 + so * 0.035
                + games * 0.10 + ovr * 0.34
            )
    else:
        avg = extra.get('avg', .250)
        hr = extra.get('hr', 0)
        rbi = extra.get('rbi', 0)
        ops = extra.get('ops', .700)
        pa = extra.get('pa', 0)
        score = (
            max(0, avg - .240) * 620
            + hr * 1.45 + rbi * 0.72
            + max(0, ops - .650) * 72
            + pa * 0.018 + ovr * 0.34
        )
    if champion:
        score += 5.0
    if state.role == 'starter':
        score += 2.0
    elif state.role == 'bench':
        score -= 3.0
    return round(score, 1)


def _mvp_candidate(state, score, idx):
    """Create a believable AI MVP candidate for the same league."""
    rng = random.Random(f"mvp:{state.year}:{state.team_id}:{state.player_name}:{idx}")
    tier = LEAGUE_TIER.get(state.league_id, 1)
    base_ovr = max(55, min(96, state.overall + rng.randint(-7, 7) + (tier - 3) * 1))
    games = rng.randint(105, 144) if state.position not in ('SP','RP') else rng.randint(20, 34)
    if state.position == 'SP':
        wins = max(7, round(games * (0.22 + base_ovr / 720) + rng.randint(-3, 3)))
        era = round(max(1.85, min(5.2, 6.05 - base_ovr / 15 + rng.uniform(-.35, .35))), 2)
        so = max(70, round(games * rng.uniform(5.0, 7.0) + base_ovr * 1.2))
        extra = {'wins': wins, 'era': era, 'so': so, 'innings': games * rng.uniform(4.5, 6.4), 'saves': 0}
        statline = f'{wins}승 · ERA {era} · {so}K'
    elif state.position == 'RP':
        games = rng.randint(45, 72)
        saves = max(8, round((base_ovr - 55) * .75 + rng.randint(-5, 8)))
        era = round(max(1.75, min(5.0, 5.6 - base_ovr / 16 + rng.uniform(-.35, .35))), 2)
        so = max(45, round(games * rng.uniform(1.0, 1.7) + base_ovr * .55))
        extra = {'wins': max(1, rng.randint(2, 9)), 'saves': saves, 'era': era, 'so': so, 'innings': games * rng.uniform(.8, 1.7)}
        statline = f'{games}경기 · {saves}SV · ERA {era}'
    else:
        games = rng.randint(110, 144)
        avg = round(min(.370, max(.255, .275 + (base_ovr - 60) / 1000 + rng.uniform(-.018, .018))), 3)
        hr = max(8, round(games * max(.05, (base_ovr - 45) / 350) + rng.randint(-5, 6)))
        rbi = max(25, round(hr * 2.4 + games * (base_ovr - 50) / 420 + rng.randint(-10, 11)))
        ops = round(min(1.180, max(.620, .560 + base_ovr / 210 + rng.uniform(-.045, .045))), 3)
        extra = {'avg': avg, 'hr': hr, 'rbi': rbi, 'ops': ops, 'pa': games * rng.uniform(3.5, 4.4)}
        statline = f'{games}경기 · {avg:.3f} · {hr}HR · {rbi}RBI · OPS {ops:.3f}'
    fake = type('MVPProxy', (), {
        'position': state.position, 'overall': base_ovr, 'role': 'starter'
    })()
    fake_score = _mvp_score(fake, games, extra, champion=rng.random() < .28)
    return {
        'name': f'리그 MVP 후보 {idx}',
        'overall': base_ovr,
        'score': fake_score,
        'statline': statline,
    }


def _resolve_mvp(state, games, extra, champion=False):
    """Run an actual MVP race and return True only when the player wins."""
    player_score = _mvp_score(state, games, extra, champion)
    candidates = [_mvp_candidate(state, player_score, i) for i in range(1, 5)]
    candidates.append({
        'name': state.player_name,
        'overall': state.overall,
        'score': player_score,
        'statline': (
            f"{games}경기 · {extra.get('avg', 0):.3f} · {extra.get('hr', 0)}HR · {extra.get('rbi', 0)}RBI"
            if state.position not in ('SP','RP') else
            f"{games}경기 · {extra.get('wins', 0)}승 · {extra.get('saves', 0)}SV · ERA {extra.get('era', 0):.2f}"
        )
    })
    candidates.sort(key=lambda x: x['score'], reverse=True)
    for rank, item in enumerate(candidates, 1):
        item['rank'] = rank
    winner = candidates[0]
    state.last_mvp_race = {
        'year': state.year,
        'winner': winner['name'],
        'won': winner['name'] == state.player_name,
        'player_score': player_score,
        'candidates': candidates,
    }
    return winner['name'] == state.player_name


def _mvp_score(state, games, extra, champion=False):
    """Turn one season into an MVP ballot score."""
    ovr = state.overall
    if state.position in ('SP', 'RP'):
        era = extra.get('era', 6.0); wins = extra.get('wins', 0); saves = extra.get('saves', 0)
        so = extra.get('so', 0); innings = extra.get('innings', 0)
        if state.position == 'SP':
            score = wins * 4.0 + max(0, 4.60 - era) * 17.0 + so * 0.055 + innings * 0.025 + ovr * 0.38
        else:
            score = saves * 2.0 + max(0, 4.20 - era) * 15.0 + so * 0.035 + games * 0.10 + ovr * 0.34
    else:
        avg = extra.get('avg', .250); hr = extra.get('hr', 0); rbi = extra.get('rbi', 0)
        ops = extra.get('ops', .700); pa = extra.get('pa', 0)
        score = (max(0, avg - .240) * 620 + hr * 1.45 + rbi * 0.72
                 + max(0, ops - .650) * 72 + pa * 0.018 + ovr * 0.34)
    if champion: score += 5.0
    if state.role == 'starter': score += 2.0
    elif state.role == 'bench': score -= 3.0
    return round(score, 1)

def _mvp_candidate(state, idx):
    """Generate a same-league AI MVP candidate with comparable production."""
    rng = random.Random(f"mvp:{state.year}:{state.team_id}:{state.player_name}:{idx}")
    tier = LEAGUE_TIER.get(state.league_id, 1)
    base_ovr = max(55, min(96, state.overall + rng.randint(-7, 7) + (tier - 3)))
    if state.position == 'SP':
        games = rng.randint(20, 34)
        wins = max(7, round(games * (0.22 + base_ovr / 720) + rng.randint(-3, 3)))
        era = round(max(1.85, min(5.2, 6.05 - base_ovr / 15 + rng.uniform(-.35, .35))), 2)
        so = max(70, round(games * rng.uniform(5.0, 7.0) + base_ovr * 1.2))
        extra = {'wins': wins, 'saves': 0, 'era': era, 'so': so, 'innings': games * rng.uniform(4.5, 6.4)}
        statline = f'{games}경기 · {wins}승 · ERA {era} · {so}K'
    elif state.position == 'RP':
        games = rng.randint(45, 72)
        saves = max(8, round((base_ovr - 55) * .75 + rng.randint(-5, 8)))
        era = round(max(1.75, min(5.0, 5.6 - base_ovr / 16 + rng.uniform(-.35, .35))), 2)
        so = max(45, round(games * rng.uniform(1.0, 1.7) + base_ovr * .55))
        extra = {'wins': rng.randint(2, 9), 'saves': saves, 'era': era, 'so': so, 'innings': games * rng.uniform(.8, 1.7)}
        statline = f'{games}경기 · {saves}SV · ERA {era}'
    else:
        games = rng.randint(110, 144)
        avg = round(min(.370, max(.255, .275 + (base_ovr - 60) / 1000 + rng.uniform(-.018, .018))), 3)
        hr = max(8, round(games * max(.05, (base_ovr - 45) / 350) + rng.randint(-5, 6)))
        rbi = max(25, round(hr * 2.4 + games * (base_ovr - 50) / 420 + rng.randint(-10, 11)))
        ops = round(min(1.180, max(.620, .560 + base_ovr / 210 + rng.uniform(-.045, .045))), 3)
        extra = {'avg': avg, 'hr': hr, 'rbi': rbi, 'ops': ops, 'pa': games * rng.uniform(3.5, 4.4)}
        statline = f'{games}경기 · {avg:.3f} · {hr}HR · {rbi}RBI · OPS {ops:.3f}'
    fake = type('MVPProxy', (), {'position': state.position, 'overall': base_ovr, 'role': 'starter'})()
    champion = rng.random() < .28
    return {'name': f'리그 MVP 후보 {idx}', 'overall': base_ovr,
            'score': _mvp_score(fake, games, extra, champion), 'statline': statline}

def _resolve_mvp(state, games, extra, champion=False):
    """Compare the player's season against four league-wide candidates."""
    player_score = _mvp_score(state, games, extra, champion)
    candidates = [_mvp_candidate(state, i) for i in range(1, 5)]
    candidates.append({'name': state.player_name, 'overall': state.overall, 'score': player_score,
                       'statline': (f"{games}경기 · {extra.get('avg', 0):.3f} · {extra.get('hr', 0)}HR · {extra.get('rbi', 0)}RBI"
                                    if state.position not in ('SP','RP') else
                                    f"{games}경기 · {extra.get('wins', 0)}승 · {extra.get('saves', 0)}SV · ERA {extra.get('era', 0):.2f}")})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    for rank, item in enumerate(candidates, 1): item['rank'] = rank
    winner = candidates[0]
    state.last_mvp_race = {'year': state.year, 'winner': winner['name'],
                           'won': winner['name'] == state.player_name, 'player_score': player_score,
                           'candidates': candidates}
    return winner['name'] == state.player_name

def _add_individual_awards(state, strength, games, extra, champion=False):
    awards = []
    if strength >= 72 and games >= (80 if state.position in ('SP','RP') else 100) and random.random() < 0.48:
        awards.append(('ALL_STAR', '올스타', '시즌 올스타에 선정됐다.', '✨'))
    if state.position in ('SP','RP'):
        era = extra.get('era', 9.99); wins = extra.get('wins', 0); saves = extra.get('saves', 0)
        if state.position == 'SP' and (era <= 2.65 and wins >= 13 and strength >= 78):
            awards.append(('CY_YOUNG', '사이영상', '리그 최고의 선발투수에게 주어지는 상을 수상했다.', '🏅'))
        if state.position == 'RP' and saves >= 30 and strength >= 78:
            awards.append(('RELIEVER', '올해의 마무리', '최고의 마무리투수로 선정됐다.', '🚨'))
        if state.age <= 22 and strength >= 68 and games >= 20 and not any(a.get('award_id') == 'ROY' for a in state.individual_awards):
            awards.append(('ROY', '신인왕', '신인왕을 차지했다.', '🌟'))
    else:
        avg = extra.get('avg', 0); hr = extra.get('hr', 0); rbi = extra.get('rbi', 0)
        field = state.abilities.get('fielding', 50) if state.abilities else 50
        if avg >= .330 and games >= 100: awards.append(('BATTING_TITLE', '타격왕', '시즌 타율 1위를 기록했다.', '🏏'))
        if hr >= 35 and games >= 100: awards.append(('HR_KING', '홈런왕', '시즌 홈런 1위를 기록했다.', '💥'))
        if rbi >= 105 and games >= 100: awards.append(('RBI_KING', '타점왕', '시즌 타점 1위를 기록했다.', '🔥'))
        if field >= 82 and games >= 105: awards.append(('GOLD_GLOVE', '골드글러브', '수비력을 인정받아 골드글러브를 수상했다.', '🧤'))
        if state.age <= 22 and strength >= 68 and games >= 70 and not any(a.get('award_id') == 'ROY' for a in state.individual_awards):
            awards.append(('ROY', '신인왕', '신인왕을 차지했다.', '🌟'))
    if _resolve_mvp(state, games, extra, champion):
        awards.append(('MVP', 'MVP', '리그 MVP 경쟁에서 가장 높은 평가를 받아 시즌 MVP에 선정됐다.', '👑'))
    for aid, name, desc, icon in awards:
        state.individual_awards.append({'award_id': aid, 'name': name, 'desc': desc, 'icon': icon, 'year': state.year, 'age': state.age})
    return awards

def _add_club_trophies(state, strength):
    tier = LEAGUE_TIER.get(state.league_id, 1)
    state.last_trophy = None
    # League title. Higher OVR + starter role + league tier = stronger chance.
    league_chance = max(.05, min(.48, .05 + strength / 300 + tier * .012 + (0.05 if state.role == 'starter' else 0)))
    if random.random() < league_chance:
        trophy = {'type':'league', 'category':'리그', 'name':f"{(league(state.league_id) or {}).get('name','리그')} 우승", 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id)}
        state.club_trophies.append(trophy); state.league_titles += 1; state.titles += 1; state.last_trophy = trophy
    # Domestic cup is rarer and separate from the league title.
    if random.random() < min(.18, .02 + strength / 480 + tier * .006):
        trophy = {'type':'cup', 'category':'국내 컵', 'name':'국내 컵 우승', 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id)}
        state.club_trophies.append(trophy); state.cup_titles += 1; state.titles += 1; state.last_trophy = trophy
    # Continental titles are reserved for upper-level leagues.
    if tier >= 4 and random.random() < min(.12, .008 + strength / 900 + (tier-3)*.014):
        trophy = {'type':'continental', 'category':'대륙 대회', 'name':'대륙 클럽 대회 우승', 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id)}
        state.club_trophies.append(trophy); state.continental_titles += 1; state.titles += 1; state.last_trophy = trophy
    return state.last_trophy


def simulate_season(state):
    """야구식 시즌 시뮬레이션. 난이도에 따라 성장/부상/성적 변동폭을 조절한다."""
    role_mult = ROLE_INFO.get(state.role, ROLE_INFO['rotation'])
    diff = DIFFICULTY_INFO.get(state.difficulty, DIFFICULTY_INFO['pro'])

    # Age + potential based curve: fast teenage growth, stable prime, gradual decline.
    # Growth now eases toward each player's individual potential instead of
    # repeatedly adding the same random amount.
    if state.age <= 18:
        age_base = random.uniform(3.5, 5.5)
    elif state.age <= 21:
        age_base = random.uniform(2.7, 4.5)
    elif state.age <= 24:
        age_base = random.uniform(1.8, 3.5)
    elif state.age <= 27:
        age_base = random.uniform(0.8, 2.4)
    elif state.age <= 30:
        age_base = random.uniform(0.0, 1.5)
    elif state.age <= 33:
        age_base = random.uniform(-0.5, 0.8)
    elif state.age <= 36:
        age_base = random.uniform(-1.5, 0.2)
    else:
        age_base = random.uniform(-3.2, -1.0)

    potential_gap = state.potential - state.overall
    if potential_gap <= 0:
        age_base = min(age_base, -0.25 if state.age >= 28 else 0.0)
    elif potential_gap < 5:
        age_base *= 0.35
    elif potential_gap < 10:
        age_base *= 0.65

    role_bonus = {'starter': 0.45, 'rotation': 0.0, 'bench': -0.45}.get(state.role, 0)
    growth = age_base + diff['growth_bonus'] + role_bonus
    # Small random noise keeps OVR from looking scripted while avoiding wild jumps.
    growth += random.uniform(-0.35, 0.35)
    old_ovr = state.overall
    state.overall = max(30, min(99, round(state.overall + growth)))
    actual_growth = state.overall - old_ovr
    state.last_ovr = old_ovr
    state.ovr_change = actual_growth
    state.peak_overall = max(state.peak_overall, state.overall)
    _update_abilities(state, actual_growth)

    strength = state.overall

    if state.position in ('SP', 'RP'):
        # 선발은 시즌 20~34경기, 불펜은 35~75경기 정도가 현실적인 범위
        if state.position == 'SP':
            games = max(8, round(random.randint(20, 34) * role_mult['games_mult']))
            innings = max(35, round(games * random.uniform(4.2, 6.4)))
            wins = max(0, round(games * (0.15 + strength / 900) + random.randint(-3, 3)))
            saves = 0
        else:
            games = max(15, round(random.randint(38, 72) * role_mult['games_mult']))
            innings = max(25, round(games * random.uniform(0.8, 1.8)))
            wins = max(0, round(games * (0.07 + strength / 1700) + random.randint(-2, 3)))
            saves = max(0, round((strength - 55) / 4 + random.randint(-3, 8))) if strength >= 65 else random.randint(0, 4)

        era = round(max(1.80, min(6.80, 6.25 - strength / 13.0 + random.uniform(-0.55, 0.55))), 2)
        so = max(15, round(innings * (5.0 + strength / 22) + random.randint(-12, 15)))
        state.career_wins += wins
        state.career_saves += saves
        state.career_era = round(((state.career_era * max(1, state.season - 1)) + era) / state.season, 2)
        line = f'{games}경기 · {wins}승 · {saves}세이브 · ERA {era} · {so}탈삼진'
        primary, secondary = wins, saves
        extra = {'era': era, 'so': so, 'innings': innings}
    else:
        games = max(35, round(random.randint(100, 144) * role_mult['games_mult']))
        pa = max(80, round(games * random.uniform(3.2, 4.5)))
        avg = max(.210, min(.390, .220 + strength / 900 + random.uniform(-.018, .018)))
        hits = max(1, round(pa * avg))
        hr = max(0, round(games * (strength - 42) / 260 + random.randint(-4, 6)))
        rbi = max(0, round(hr * 2.5 + hits * .16 + random.randint(-8, 12)))
        state.career_hits += hits
        state.career_hr += hr
        state.career_rbi += rbi
        ops = max(.480, min(1.200, .520 + strength / 210 + random.uniform(-.045, .045)))
        line = f'{games}경기 · 타율 {avg:.3f} · {hr}홈런 · {rbi}타점 · OPS {ops:.3f}'
        primary, secondary = hr, rbi
        extra = {'avg': avg, 'ops': ops, 'pa': pa}

    state.career_games += games
    team_obj = team(state.team_id) or {}

    trophy = _add_club_trophies(state, strength)
    champion = bool(trophy)
    if champion:
        state.fame = min(100, state.fame + 8)
        line += f' · {trophy["name"]}'

    # Personal awards are stored separately from club/international trophies.
    extra['wins'] = wins if state.position in ('SP','RP') else 0
    extra['saves'] = saves if state.position in ('SP','RP') else 0
    extra['hr'] = hr if state.position not in ('SP','RP') else 0
    extra['rbi'] = rbi if state.position not in ('SP','RP') else 0
    season_awards = _add_individual_awards(state, strength, games, extra, champion=champion)
    if season_awards:
        line += ' · ' + ', '.join(a[1] for a in season_awards[:2])
        state.fame = min(100, state.fame + 4 * len(season_awards))

    injury_risk = max(.012, (.11 - state.stamina / 850 - state.overall / 2600) * diff['injury_mult'])
    injury = random.random() < injury_risk
    if injury:
        state.injuries += 1
        state.injury_active = True
        state.stamina = max(15, state.stamina - 15)
        line += ' · 시즌 중 부상'

    state.stamina = max(25, min(100, state.stamina - random.randint(2, 7)))
    state.money += max(1000, 1500 + state.fame * 120)

    # National-team selection is primarily automatic and rare.  It happens
    # independently of the regular decision event, so quiet seasons can still
    # produce an occasional call-up without turning every season into a choice.
    _maybe_national_team_selection(state)

    state.last_result = line

    state.history.append({
        'season': state.season, 'year': state.year, 'age': state.age,
        'team_id': state.team_id, 'league_id': state.league_id, 'team': canonical_team_name(state.team_id, state.team_id), 'result': line,
        'decision': state.last_decision, 'rating': strength, 'games': games,
        'primary': primary, 'secondary': secondary, 'champion': champion,
        'injury': injury, 'market_value': market_value(state),
        'ovr_change': state.ovr_change, 'awards': [a[1] for a in season_awards],
        'trophy': trophy.get('name') if trophy else None,
        'mvp_race': state.last_mvp_race, **extra,
    })
    return line


def advance_after_season(state):
    """Move the clock forward after a season was simulated, and either land on
    the next interactive decision point (per pace) or auto-resolve quiet
    seasons (a neutral 'stay' transfer window) until one is reached."""
    while True:
        if state.status == 'retired':
            state.pending_event = None
            state.decision_used = True
            return state

        state.age += 1
        state.season += 1
        state.year += 1
        state.last_result = ''

        if state.age >= RETIREMENT_AGE:
            state.status = 'retired'
            state.pending_event = None
            state.decision_used = True
            return state

        interval = PACE_INFO.get(state.pace, PACE_INFO['normal'])['interval']
        state.pace_counter += 1

        if state.pace_counter >= interval:
            state.pace_counter = 0
            state.pending_event = generate_event(state)
            state.decision_used = False
            return state
        else:
            # quiet season: auto "stay" and simulate immediately, then loop
            state.loyalty = min(100, state.loyalty + 3)
            state.last_decision = '자동 진행'
            state.last_event = random.choice(FLAVOR.get('milestones', ['조용히 시즌을 준비했다.'])) \
                if isinstance(FLAVOR, dict) else '조용히 시즌을 준비했다.'
            simulate_season(state)
            # loop again to check the next season
