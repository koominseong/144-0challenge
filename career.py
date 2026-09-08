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
    'rookie': {
        'label': '초보자',
        'desc': '성장이 비교적 빠르고 부상·성적 변동이 적습니다.',
        'start_ovr': 56, 'growth_bonus': 0.9, 'injury_mult': 0.60, 'performance_mult': 1.08,
    },
    'pro': {
        'label': '프로',
        'desc': '성장과 경쟁이 빡빡합니다. 전성기 이후 OVR 유지가 중요합니다.',
        'start_ovr': 51, 'growth_bonus': -0.15, 'injury_mult': 0.95, 'performance_mult': 1.00,
    },
    'hell': {
        'label': '파멸',
        'desc': '성장 폭이 매우 작고 부상·부진·경쟁이 가혹합니다.',
        'start_ovr': 47, 'growth_bonus': -0.85, 'injury_mult': 1.45, 'performance_mult': 0.88,
    },
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
    difficulty: str = 'pro'         # rookie | pro | hell
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
    if data.get('difficulty') == 'legend': data['difficulty'] = 'hell'
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

ACHIEVEMENT_DEFS = [{'id': 'easy02', 'tier': 'easy', 'name': '첫 프로 시즌', 'desc': '프로 첫 시즌 기록을 남기세요.', 'icon': '⚾'}, {'id': 'easy03', 'tier': 'easy', 'name': 'OVR 70', 'desc': '최고 OVR 70을 기록하세요.', 'icon': '🌟'}, {'id': 'easy04', 'tier': 'easy', 'name': '첫 올스타', 'desc': '올스타에 1회 선정되세요.', 'icon': '✨'}, {'id': 'easy05', 'tier': 'easy', 'name': '첫 이적', 'desc': '첫 이적을 경험하세요.', 'icon': '✈️'}, {'id': 'easy06', 'tier': 'easy', 'name': '통산 200경기', 'desc': '통산 200경기를 기록하세요.', 'icon': '🧢'}, {'id': 'easy07', 'tier': 'easy', 'name': '첫 국가대표', 'desc': '국가대표 경기에 출전하세요.', 'icon': '🌏'}, {'id': 'easy08', 'tier': 'easy', 'name': '첫 개인상', 'desc': '개인 수상을 획득하세요.', 'icon': '🎖️'}, {'id': 'easy09', 'tier': 'easy', 'name': '첫 트로피', 'desc': '첫 우승을 경험하세요.', 'icon': '🏆'}, {'id': 'easy10', 'tier': 'easy', 'name': '20세의 벽', 'desc': '20세 이전에 OVR 75를 기록하세요.', 'icon': '🔥'}, {'id': 'easy11', 'tier': 'easy', 'name': '유망주 탈출', 'desc': 'OVR 78에 도달하세요.', 'icon': '🚀'}, {'id': 'easy12', 'tier': 'easy', 'name': '100안타', 'desc': '한 시즌 100안타를 기록하세요.', 'icon': '🧢'}, {'id': 'easy13', 'tier': 'easy', 'name': '20홈런', 'desc': '한 시즌 20홈런을 기록하세요.', 'icon': '💥'}, {'id': 'easy14', 'tier': 'easy', 'name': '10승', 'desc': '한 시즌 10승을 기록하세요.', 'icon': '🎯'}, {'id': 'easy15', 'tier': 'easy', 'name': '20세이브', 'desc': '한 시즌 20세이브를 기록하세요.', 'icon': '🚪'}, {'id': 'easy16', 'tier': 'easy', 'name': '원클럽 3년', 'desc': '한 팀에서 3시즌을 보내세요.', 'icon': '❤️'}, {'id': 'easy17', 'tier': 'easy', 'name': '주장', 'desc': '주장이 되세요.', 'icon': '🎽'}, {'id': 'easy18', 'tier': 'easy', 'name': '최고가치 10억', 'desc': '시장가치 10억원을 넘기세요.', 'icon': '💰'}, {'id': 'easy19', 'tier': 'easy', 'name': '3개 대회 우승', 'desc': '클럽 대회 3종을 우승하세요.', 'icon': '🌍'}, {'id': 'easy20', 'tier': 'easy', 'name': 'MVP 후보', 'desc': 'MVP 레이스 TOP3에 드세요.', 'icon': '👑'}, {'id': 'easy21', 'tier': 'easy', 'name': '25세 최고점', 'desc': '25세까지 OVR 82를 기록하세요.', 'icon': '📈'}, {'id': 'easy22', 'tier': 'easy', 'name': '통산 500안타', 'desc': '통산 500안타를 기록하세요.', 'icon': '🧱'}, {'id': 'easy23', 'tier': 'easy', 'name': '통산 50홈런', 'desc': '통산 50홈런을 기록하세요.', 'icon': '💣'}, {'id': 'easy24', 'tier': 'easy', 'name': '통산 50승', 'desc': '통산 50승을 기록하세요.', 'icon': '🔥'}, {'id': 'easy25', 'tier': 'easy', 'name': '통산 50세이브', 'desc': '통산 50세이브를 기록하세요.', 'icon': '🚨'}, {'id': 'easy26', 'tier': 'easy', 'name': '첫 은퇴', 'desc': '커리어를 은퇴까지 완주하세요.', 'icon': '🏁'}, {'id': 'normal02', 'tier': 'normal', 'name': 'OVR 85', 'desc': '최고 OVR 85를 기록하세요.', 'icon': '⭐'}, {'id': 'normal03', 'tier': 'normal', 'name': '올스타 3회', 'desc': '올스타 3회 이상을 기록하세요.', 'icon': '✨'}, {'id': 'normal04', 'tier': 'normal', 'name': '리그 우승 3회', 'desc': '리그 우승 3회를 기록하세요.', 'icon': '🏆'}, {'id': 'normal05', 'tier': 'normal', 'name': '국내 컵 2회', 'desc': '국내 컵 우승 2회를 기록하세요.', 'icon': '🥇'}, {'id': 'normal06', 'tier': 'normal', 'name': '대륙 우승', 'desc': '대륙 클럽 대회 우승을 기록하세요.', 'icon': '🌍'}, {'id': 'normal07', 'tier': 'normal', 'name': '국가대표 10경기', 'desc': '국가대표 10경기를 기록하세요.', 'icon': '🌏'}, {'id': 'normal08', 'tier': 'normal', 'name': 'MVP 경쟁 TOP2', 'desc': 'MVP 레이스 2위 이상을 기록하세요.', 'icon': '👑'}, {'id': 'normal09', 'tier': 'normal', 'name': '20홈런 시즌 3회', 'desc': '20홈런 시즌을 3회 기록하세요.', 'icon': '💥'}, {'id': 'normal10', 'tier': 'normal', 'name': '3할 시즌 3회', 'desc': '3할 이상 시즌을 3회 기록하세요.', 'icon': '🏏'}, {'id': 'normal11', 'tier': 'normal', 'name': '10승 시즌 3회', 'desc': '10승 이상 시즌을 3회 기록하세요.', 'icon': '🎯'}, {'id': 'normal12', 'tier': 'normal', 'name': '30세이브 시즌 2회', 'desc': '30세이브 시즌을 2회 기록하세요.', 'icon': '🚨'}, {'id': 'normal13', 'tier': 'normal', 'name': '통산 1000안타', 'desc': '통산 1,000안타를 기록하세요.', 'icon': '🧢'}, {'id': 'normal14', 'tier': 'normal', 'name': '통산 100홈런', 'desc': '통산 100홈런을 기록하세요.', 'icon': '💥'}, {'id': 'normal15', 'tier': 'normal', 'name': '통산 100승', 'desc': '통산 100승을 기록하세요.', 'icon': '🔥'}, {'id': 'normal16', 'tier': 'normal', 'name': '통산 100세이브', 'desc': '통산 100세이브를 기록하세요.', 'icon': '🚪'}, {'id': 'normal17', 'tier': 'normal', 'name': '5회 이적', 'desc': '5회 이상 이적하세요.', 'icon': '✈️'}, {'id': 'normal18', 'tier': 'normal', 'name': '한 팀 5시즌', 'desc': '한 팀에서 5시즌 이상 뛰세요.', 'icon': '❤️'}, {'id': 'normal19', 'tier': 'normal', 'name': '최고가치 30억', 'desc': '시장가치 30억원을 넘기세요.', 'icon': '💰'}, {'id': 'normal20', 'tier': 'normal', 'name': '개인상 10개', 'desc': '개인 수상 10개를 모으세요.', 'icon': '🎖️'}, {'id': 'normal21', 'tier': 'normal', 'name': '국제대회 2회', 'desc': '국가대표 대회 우승 2회를 기록하세요.', 'icon': '🌐'}, {'id': 'normal22', 'tier': 'normal', 'name': 'OVR 90', 'desc': '최고 OVR 90을 기록하세요.', 'icon': '💎'}, {'id': 'normal23', 'tier': 'normal', 'name': '25세 이전 85', 'desc': '25세 이전 OVR 85를 기록하세요.', 'icon': '📈'}, {'id': 'normal24', 'tier': 'normal', 'name': '1000경기', 'desc': '통산 1,000경기를 기록하세요.', 'icon': '🦾'}, {'id': 'normal25', 'tier': 'normal', 'name': '왕조의 핵심', 'desc': '리그 우승 5회 또는 그 이상을 기록하세요.', 'icon': '🏰'}, {'id': 'normal26', 'tier': 'normal', 'name': '올스타 5회', 'desc': '올스타 5회를 기록하세요.', 'icon': '🌟'}, {'id': 'hard02', 'tier': 'hard', 'name': 'OVR 92', 'desc': '최고 OVR 92를 기록하세요.', 'icon': '💎'}, {'id': 'hard03', 'tier': 'hard', 'name': 'MVP 1회', 'desc': '리그 MVP를 1회 수상하세요.', 'icon': '👑'}, {'id': 'hard04', 'tier': 'hard', 'name': 'MVP 3회', 'desc': '리그 MVP를 3회 수상하세요.', 'icon': '👑'}, {'id': 'hard05', 'tier': 'hard', 'name': '사이영상 2회', 'desc': '사이영상을 2회 수상하세요.', 'icon': '🏅'}, {'id': 'hard06', 'tier': 'hard', 'name': '골드글러브 3회', 'desc': '골드글러브를 3회 수상하세요.', 'icon': '🧤'}, {'id': 'hard07', 'tier': 'hard', 'name': '홈런왕 3회', 'desc': '홈런왕을 3회 수상하세요.', 'icon': '💥'}, {'id': 'hard08', 'tier': 'hard', 'name': '타격왕 3회', 'desc': '타격왕을 3회 수상하세요.', 'icon': '🏏'}, {'id': 'hard09', 'tier': 'hard', 'name': '타점왕 3회', 'desc': '타점왕을 3회 수상하세요.', 'icon': '🔥'}, {'id': 'hard10', 'tier': 'hard', 'name': '올해의 마무리 3회', 'desc': '올해의 마무리를 3회 수상하세요.', 'icon': '🚨'}, {'id': 'hard11', 'tier': 'hard', 'name': '리그 우승 8회', 'desc': '리그 우승 8회를 기록하세요.', 'icon': '🏆'}, {'id': 'hard12', 'tier': 'hard', 'name': '국내 컵 5회', 'desc': '국내 컵 5회를 기록하세요.', 'icon': '🥇'}, {'id': 'hard13', 'tier': 'hard', 'name': '대륙 우승 3회', 'desc': '대륙 클럽 우승 3회를 기록하세요.', 'icon': '🌍'}, {'id': 'hard14', 'tier': 'hard', 'name': '국제대회 3종 우승', 'desc': 'WBC/프리미어12/올림픽·아시안게임 중 3종을 우승하세요.', 'icon': '🌐'}, {'id': 'hard15', 'tier': 'hard', 'name': '국가대표 30경기', 'desc': '국가대표 30경기를 기록하세요.', 'icon': '🛡️'}, {'id': 'hard16', 'tier': 'hard', 'name': '통산 2000안타', 'desc': '통산 2,000안타를 기록하세요.', 'icon': '🧱'}, {'id': 'hard17', 'tier': 'hard', 'name': '통산 300홈런', 'desc': '통산 300홈런을 기록하세요.', 'icon': '💣'}, {'id': 'hard18', 'tier': 'hard', 'name': '통산 200승', 'desc': '통산 200승을 기록하세요.', 'icon': '🔥'}, {'id': 'hard19', 'tier': 'hard', 'name': '통산 200세이브', 'desc': '통산 200세이브를 기록하세요.', 'icon': '🚪'}, {'id': 'hard20', 'tier': 'hard', 'name': '통산 1500경기', 'desc': '통산 1,500경기를 기록하세요.', 'icon': '🦾'}, {'id': 'hard21', 'tier': 'hard', 'name': '5개 개인상 종류', 'desc': '서로 다른 개인상 5종을 획득하세요.', 'icon': '🎖️'}, {'id': 'hard22', 'tier': 'hard', 'name': '최고가치 50억', 'desc': '시장가치 50억원을 넘기세요.', 'icon': '💰'}, {'id': 'hard23', 'tier': 'hard', 'name': '30세까지 OVR 90', 'desc': '30세 이하에서 OVR 90을 기록하세요.', 'icon': '⏱️'}, {'id': 'hard24', 'tier': 'hard', 'name': '10시즌 올스타', 'desc': '올스타 10회를 기록하세요.', 'icon': '⭐'}, {'id': 'hard25', 'tier': 'hard', 'name': '통산 우승 10회', 'desc': '클럽+국가대표 우승 10회를 기록하세요.', 'icon': '🏆'}, {'id': 'hard26', 'tier': 'hard', 'name': '커리어 점수 5000', 'desc': '커리어 점수 5,000점을 넘기세요.', 'icon': '📊'}, {'id': 'hell02', 'tier': 'hell', 'name': 'OVR 95', 'desc': '최고 OVR 95를 기록하세요.', 'icon': '☠️'}, {'id': 'hell03', 'tier': 'hell', 'name': 'OVR 97', 'desc': '최고 OVR 97을 기록하세요.', 'icon': '💀'}, {'id': 'hell04', 'tier': 'hell', 'name': 'MVP 5회', 'desc': 'MVP를 5회 수상하세요.', 'icon': '👑'}, {'id': 'hell05', 'tier': 'hell', 'name': 'MVP 8회', 'desc': 'MVP를 8회 수상하세요.', 'icon': '👑'}, {'id': 'hell06', 'tier': 'hell', 'name': '사이영상 5회', 'desc': '사이영상을 5회 수상하세요.', 'icon': '🏅'}, {'id': 'hell07', 'tier': 'hell', 'name': '골드글러브 8회', 'desc': '골드글러브를 8회 수상하세요.', 'icon': '🧤'}, {'id': 'hell08', 'tier': 'hell', 'name': '홈런왕 7회', 'desc': '홈런왕을 7회 수상하세요.', 'icon': '💥'}, {'id': 'hell09', 'tier': 'hell', 'name': '타격왕 7회', 'desc': '타격왕을 7회 수상하세요.', 'icon': '🏏'}, {'id': 'hell10', 'tier': 'hell', 'name': '올해의 마무리 7회', 'desc': '올해의 마무리를 7회 수상하세요.', 'icon': '🚨'}, {'id': 'hell11', 'tier': 'hell', 'name': '리그 우승 12회', 'desc': '리그 우승 12회를 기록하세요.', 'icon': '🏆'}, {'id': 'hell12', 'tier': 'hell', 'name': '국내 컵 8회', 'desc': '국내 컵 8회를 기록하세요.', 'icon': '🥇'}, {'id': 'hell13', 'tier': 'hell', 'name': '대륙 우승 6회', 'desc': '대륙 우승 6회를 기록하세요.', 'icon': '🌍'}, {'id': 'hell14', 'tier': 'hell', 'name': '국제대회 5종', 'desc': '국제대회 5종류를 모두 우승하세요.', 'icon': '🌐'}, {'id': 'hell15', 'tier': 'hell', 'name': '국가대표 50경기', 'desc': '국가대표 50경기를 기록하세요.', 'icon': '🛡️'}, {'id': 'hell16', 'tier': 'hell', 'name': '통산 3000안타', 'desc': '통산 3,000안타를 기록하세요.', 'icon': '🧱'}, {'id': 'hell17', 'tier': 'hell', 'name': '통산 500홈런', 'desc': '통산 500홈런을 기록하세요.', 'icon': '💣'}, {'id': 'hell18', 'tier': 'hell', 'name': '통산 250승', 'desc': '통산 250승을 기록하세요.', 'icon': '🔥'}, {'id': 'hell19', 'tier': 'hell', 'name': '통산 300세이브', 'desc': '통산 300세이브를 기록하세요.', 'icon': '🚪'}, {'id': 'hell20', 'tier': 'hell', 'name': '통산 2000경기', 'desc': '통산 2,000경기를 기록하세요.', 'icon': '🦾'}, {'id': 'hell21', 'tier': 'hell', 'name': '개인상 25개', 'desc': '개인 수상 25개를 모으세요.', 'icon': '🎖️'}, {'id': 'hell22', 'tier': 'hell', 'name': '서로 다른 개인상 8종', 'desc': '서로 다른 개인상 8종을 획득하세요.', 'icon': '🏅'}, {'id': 'hell23', 'tier': 'hell', 'name': '커리어 점수 10000', 'desc': '커리어 점수 10,000점을 넘기세요.', 'icon': '📊'}, {'id': 'hell24', 'tier': 'hell', 'name': '커리어 점수 20000', 'desc': '커리어 점수 20,000점을 넘기세요.', 'icon': '📈'}, {'id': 'hell25', 'tier': 'hell', 'name': '원클럽 10년', 'desc': '한 팀에서 10시즌 이상 뛰세요.', 'icon': '❤️'}, {'id': 'hell26', 'tier': 'hell', 'name': '철인 완주', 'desc': '40세 은퇴 + 통산 2,000경기를 동시에 달성하세요.', 'icon': '☠️'}]

def check_achievements(state):
    # Derived achievement counters are intentionally based on full career history.
    awards=state.individual_awards or []
    aid=[a.get('award_id') for a in awards]
    seasons=state.history or []
    def count_aw(x): return aid.count(x)
    def season_count(fn): return sum(1 for r in seasons if fn(r))
    unique_awards=len(set(x for x in aid if x))
    intl_types=len(set((x.get('competition_id') if isinstance(x,dict) else str(x)) for x in (state.international_trophies or [])))
    club_types=len(set(x.get('type') for x in (state.club_trophies or []) if isinstance(x,dict)))
    score=career_score(state)
    value=market_value(state)
    oneclub=max([c.get('seasons',0) for c in club_history(state)] or [0])
    def ok(c):
        return {
            'first':bool(seasons),'ovr70':state.peak_overall>=70,'allstar1':count_aw('ALL_STAR')>=1,'transfer1':state.transfers_count>=1,'games200':state.career_games>=200,'caps1':state.international_caps>=1,'award1':len(awards)>=1,'title1':state.titles+state.international_titles>=1,'young75':any(r.get('age',99)<=20 and r.get('rating',0)>=75 for r in seasons),'ovr78':state.peak_overall>=78,'season_hit100':season_count(lambda r:r.get('hits',0)>=100)>=1,'season_hr20':season_count(lambda r:r.get('hr',0)>=20)>=1,'season_w10':season_count(lambda r:r.get('wins',0)>=10)>=1,'season_sv20':season_count(lambda r:r.get('saves',0)>=20)>=1,'oneclub3':oneclub>=3,'captain':state.captain,'value10':value>=1_000_000_000,'three_types':club_types>=3,'mvp_top3':any(r.get('mvp_race',{}).get('rank',99)<=3 for r in seasons if isinstance(r.get('mvp_race'),dict)),'age25_82':any(r.get('age',99)<=25 and r.get('rating',0)>=82 for r in seasons),'hit500':state.career_hits>=500,'hr50':state.career_hr>=50,'win50':state.career_wins>=50,'save50':state.career_saves>=50,'retire':state.status=='retired',
            'ovr85':state.peak_overall>=85,'allstar3':count_aw('ALL_STAR')>=3,'league3':state.league_titles>=3,'cup2':state.cup_titles>=2,'continental1':state.continental_titles>=1,'caps10':state.international_caps>=10,'mvp_top2':any(r.get('mvp_race',{}).get('rank',99)<=2 for r in seasons if isinstance(r.get('mvp_race'),dict)),'hr20_3':season_count(lambda r:r.get('hr',0)>=20)>=3,'avg300_3':season_count(lambda r:float(r.get('avg',0) or 0)>=.300)>=3,'w10_3':season_count(lambda r:r.get('wins',0)>=10)>=3,'sv30_2':season_count(lambda r:r.get('saves',0)>=30)>=2,'hit1000':state.career_hits>=1000,'hr100':state.career_hr>=100,'win100':state.career_wins>=100,'save100':state.career_saves>=100,'transfer5':state.transfers_count>=5,'oneclub5':oneclub>=5,'value30':value>=3_000_000_000,'award10':len(awards)>=10,'intl2':state.international_titles>=2,'ovr90':state.peak_overall>=90,'age25_85':any(r.get('age',99)<=25 and r.get('rating',0)>=85 for r in seasons),'games1000':state.career_games>=1000,'league5':state.league_titles>=5,'allstar5':count_aw('ALL_STAR')>=5,
            'ovr92':state.peak_overall>=92,'mvp1':count_aw('MVP')>=1,'mvp3':count_aw('MVP')>=3,'cy2':count_aw('CY_YOUNG')>=2,'gg3':count_aw('GOLD_GLOVE')>=3,'hrking3':count_aw('HR_KING')>=3,'batting3':count_aw('BATTING_TITLE')>=3,'rbi3':count_aw('RBI_KING')>=3,'reliever3':count_aw('RELIEVER')>=3,'league8':state.league_titles>=8,'cup5':state.cup_titles>=5,'continental3':state.continental_titles>=3,'intl3types':intl_types>=3,'caps30':state.international_caps>=30,'hit2000':state.career_hits>=2000,'hr300':state.career_hr>=300,'win200':state.career_wins>=200,'save200':state.career_saves>=200,'games1500':state.career_games>=1500,'awardtypes5':unique_awards>=5,'value50':value>=5_000_000_000,'age30_90':any(r.get('age',99)<=30 and r.get('rating',0)>=90 for r in seasons),'allstar10':count_aw('ALL_STAR')>=10,'titles10':state.titles+state.international_titles>=10,'score5000':score>=5000,
            'ovr95':state.peak_overall>=95,'ovr97':state.peak_overall>=97,'mvp5':count_aw('MVP')>=5,'mvp8':count_aw('MVP')>=8,'cy5':count_aw('CY_YOUNG')>=5,'gg8':count_aw('GOLD_GLOVE')>=8,'hrking7':count_aw('HR_KING')>=7,'batting7':count_aw('BATTING_TITLE')>=7,'reliever7':count_aw('RELIEVER')>=7,'league12':state.league_titles>=12,'cup8':state.cup_titles>=8,'continental6':state.continental_titles>=6,'intl5types':intl_types>=5,'caps50':state.international_caps>=50,'hit3000':state.career_hits>=3000,'hr500':state.career_hr>=500,'win250':state.career_wins>=250,'save300':state.career_saves>=300,'games2000':state.career_games>=2000,'award25':len(awards)>=25,'awardtypes8':unique_awards>=8,'score10000':score>=10000,'score20000':score>=20000,'oneclub10':oneclub>=10,'ironfinish':state.status=='retired' and state.career_games>=2000}.get(c, False)

    cond_map={'easy02': 'first', 'easy03': 'ovr70', 'easy04': 'allstar1', 'easy05': 'transfer1', 'easy06': 'games200', 'easy07': 'caps1', 'easy08': 'award1', 'easy09': 'title1', 'easy10': 'young75', 'easy11': 'ovr78', 'easy12': 'season_hit100', 'easy13': 'season_hr20', 'easy14': 'season_w10', 'easy15': 'season_sv20', 'easy16': 'oneclub3', 'easy17': 'captain', 'easy18': 'value10', 'easy19': 'three_types', 'easy20': 'mvp_top3', 'easy21': 'age25_82', 'easy22': 'hit500', 'easy23': 'hr50', 'easy24': 'win50', 'easy25': 'save50', 'easy26': 'retire', 'normal02': 'ovr85', 'normal03': 'allstar3', 'normal04': 'league3', 'normal05': 'cup2', 'normal06': 'continental1', 'normal07': 'caps10', 'normal08': 'mvp_top2', 'normal09': 'hr20_3', 'normal10': 'avg300_3', 'normal11': 'w10_3', 'normal12': 'sv30_2', 'normal13': 'hit1000', 'normal14': 'hr100', 'normal15': 'win100', 'normal16': 'save100', 'normal17': 'transfer5', 'normal18': 'oneclub5', 'normal19': 'value30', 'normal20': 'award10', 'normal21': 'intl2', 'normal22': 'ovr90', 'normal23': 'age25_85', 'normal24': 'games1000', 'normal25': 'league5', 'normal26': 'allstar5', 'hard02': 'ovr92', 'hard03': 'mvp1', 'hard04': 'mvp3', 'hard05': 'cy2', 'hard06': 'gg3', 'hard07': 'hrking3', 'hard08': 'batting3', 'hard09': 'rbi3', 'hard10': 'reliever3', 'hard11': 'league8', 'hard12': 'cup5', 'hard13': 'continental3', 'hard14': 'intl3types', 'hard15': 'caps30', 'hard16': 'hit2000', 'hard17': 'hr300', 'hard18': 'win200', 'hard19': 'save200', 'hard20': 'games1500', 'hard21': 'awardtypes5', 'hard22': 'value50', 'hard23': 'age30_90', 'hard24': 'allstar10', 'hard25': 'titles10', 'hard26': 'score5000', 'hell02': 'ovr95', 'hell03': 'ovr97', 'hell04': 'mvp5', 'hell05': 'mvp8', 'hell06': 'cy5', 'hell07': 'gg8', 'hell08': 'hrking7', 'hell09': 'batting7', 'hell10': 'reliever7', 'hell11': 'league12', 'hell12': 'cup8', 'hell13': 'continental6', 'hell14': 'intl5types', 'hell15': 'caps50', 'hell16': 'hit3000', 'hell17': 'hr500', 'hell18': 'win250', 'hell19': 'save300', 'hell20': 'games2000', 'hell21': 'award25', 'hell22': 'awardtypes8', 'hell23': 'score10000', 'hell24': 'score20000', 'hell25': 'oneclub10', 'hell26': 'ironfinish'}
    return [dict(a, unlocked=True) for a in ACHIEVEMENT_DEFS if ok(cond_map.get(a['id'], ''))]

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
    order=[]; groups={}
    for trophy in (state.international_trophies or []):
        if isinstance(trophy, str):
            cid, cname, year = 'LEGACY', trophy, '-'
        else:
            cid=trophy.get('competition_id','INTL')
            raw=trophy.get('competition_name',trophy.get('name','국제대회'))
            cname={'World Baseball Classic':'월드베이스볼클래식(WBC)','WBSC Premier12':'프리미어12','Olympic Baseball':'올림픽 야구','Asian Games Baseball':'아시안게임 야구','WBSC U-23':'WBSC U-23 야구월드컵','WBSC U-18':'WBSC U-18 야구월드컵'}.get(raw,raw)
            year=trophy.get('year','-')
        if cid not in groups:
            groups[cid]={'competition_id':cid,'name':cname,'count':0,'items':[]}
            order.append(cid)
        groups[cid]['count']+=1; groups[cid]['items'].append({'name':cname,'year':year})
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
        cid = str(c.get('competition_id', '')).upper()
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
        if cid == 'WBC':
            if (year - 2026) % 3 != 0: continue
        elif cid == 'PREMIER12':
            if (year - 2027) % 4 != 0: continue
        elif cid == 'OLY':
            if (year - 2028) % 4 != 0: continue
        elif cid == 'ASIAN_GAMES':
            if (year - 2026) % 4 != 0: continue
        elif cid == 'U23':
            if age > 23 or year % 2 == 0: continue
        elif cid == 'U18':
            if age > 18: continue

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
    """Rare automatic national-team call-up with tournament-specific trophies."""
    if getattr(state, 'status', 'active') == 'retired':
        return False
    competitions = eligible_competitions(state.nationality, state.age, state.year)
    if not competitions or random.random() >= _national_selection_probability(state):
        return False
    competition = random.choice(competitions)
    state.international_caps += 1
    names = {
        'World Baseball Classic': '월드베이스볼클래식(WBC)',
        'WBSC Premier12': '프리미어12',
        'Olympic Baseball': '올림픽 야구',
        'Asian Games Baseball': '아시안게임 야구',
        'WBSC U-23': 'WBSC U-23 야구월드컵',
        'WBSC U-18': 'WBSC U-18 야구월드컵',
    }
    cname = names.get(competition.get('name'), competition.get('name', '국제대회'))
    if random.random() < (0.06 + max(0, state.overall - 72) * 0.0035):
        state.international_titles += 1
        trophy = {'competition_id': competition.get('competition_id','INTL'), 'competition_name': cname, 'year': state.year, 'age': state.age}
        state.international_trophies.append(trophy)
        state.last_trophy = {'type':'international', 'category':'국가대표', 'name':cname + ' 우승', 'year':state.year}
        state.last_event = f'{cname}에서 대표팀 우승을 경험했다!'
    else:
        state.last_event = f'{cname} 대표팀에 차출됐다.'
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
    potential = random.randint(87, 96) if difficulty == 'rookie' else random.randint(80, 91) if difficulty == 'pro' else random.randint(74, 87)
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
    """Copero-inspired random career event engine.

    Decision points are not always transfer windows anymore. A season can
    produce a short card-style event such as an extra training camp, media
    attention, equipment opportunity, role battle, slump, sponsor offer, or
    clubhouse incident. The outcome can be good, neutral, or costly.
    """
    if state.injury_active:
        return {
            'type': 'injury', 'title': '부상에서의 갈림길', 'desc': flavor('injury'), 'icon': '🩹',
            'options': [
                {'id': 'early_return', 'kind': 'plain', 'icon': '⚡', 'label': '조기 복귀',
                 'detail': '출전은 빨라지지만 재부상 위험이 남습니다.'},
                {'id': 'full_rehab', 'kind': 'plain', 'icon': '🩹', 'label': '충분한 재활',
                 'detail': '출전은 줄지만 몸 상태를 회복합니다.'},
            ],
        }

    # Copero-like short random event cards. Difficulty controls how often
    # the player sees truly useful positive outcomes.
    event_chance = {'rookie': .78, 'pro': .64, 'hell': .50}.get(state.difficulty, .64)
    if random.random() < event_chance:
        events = [
            ('extra_camp', '추가 훈련 캠프', '코칭스태프가 특별 캠프 참가를 제안했다.', '⛺', [
                ('camp_attend', '참가한다', '훈련 강도가 높아지지만 성장 기회를 얻는다.', {'ovr': 2, 'stamina': -12, 'fame': 1}),
                ('camp_rest', '휴식을 택한다', '몸을 보호하고 다음 시즌을 준비한다.', {'stamina': 10, 'loyalty': 3}),
            ]),
            ('equipment', '새 장비 테스트', '구단이 새로운 장비의 테스트 선수를 찾고 있다.', '🧤', [
                ('equipment_yes', '테스트에 참가', '장비가 잘 맞으면 기량이 올라갈 수 있다.', {'ovr': 1, 'fame': 2}),
                ('equipment_no', '기존 장비 유지', '익숙한 장비를 계속 사용한다.', {'loyalty': 2}),
            ]),
            ('coach', '타격/투구 코치의 제안', '전담 코치가 당신에게 새로운 훈련법을 제안했다.', '🎯', [
                ('coach_change', '새 방법을 시도', '성공하면 능력치가 크게 오른다.', {'ovr': 2, 'potential': 1}),
                ('coach_keep', '기존 루틴 유지', '검증된 루틴을 지킨다.', {'stamina': 5, 'loyalty': 2}),
            ]),
            ('media', '언론의 집중 조명', '최근 활약으로 인터뷰 요청이 쏟아지고 있다.', '📺', [
                ('media_yes', '인터뷰에 응한다', '인지도가 크게 올라간다.', {'fame': 6, 'stamina': -3}),
                ('media_no', '야구에만 집중', '조용히 다음 경기를 준비한다.', {'ovr': 1, 'fame': 1}),
            ]),
            ('role_battle', '주전 경쟁', '새로운 경쟁자가 들어와 주전 자리가 흔들리고 있다.', '⚔️', [
                ('role_fight', '정면 승부', '출전 경쟁에서 밀어붙인다.', {'ovr': 1, 'stamina': -8, 'fame': 2}),
                ('role_team', '팀을 우선한다', '팀플레이를 택해 코칭스태프의 신뢰를 얻는다.', {'loyalty': 8, 'fame': 1}),
            ]),
            ('sponsor', '뜻밖의 후원 제안', '지역 기업이 당신을 공식 후원 선수로 만들고 싶어 한다.', '💰', [
                ('sponsor_accept', '후원 계약', '수입과 인지도가 오른다.', {'money': 6000000, 'fame': 4}),
                ('sponsor_decline', '정중히 거절', '훈련과 경기에만 집중한다.', {'loyalty': 3, 'ovr': 1}),
            ]),
            ('slump', '갑작스러운 슬럼프', '한 달째 타격/투구 밸런스가 흔들리고 있다.', '📉', [
                ('slump_fix', '훈련량을 늘린다', '회복을 노리지만 체력 부담이 생긴다.', {'ovr': 2, 'stamina': -15}),
                ('slump_reset', '과감히 쉰다', '일시적으로 출전은 줄지만 컨디션을 회복한다.', {'stamina': 18, 'ovr': -1}),
            ]),
            ('veteran_mentor', '베테랑의 조언', '팀의 베테랑이 당신에게 자신의 노하우를 전수하겠다고 했다.', '🧠', [
                ('mentor_accept', '배운다', '경험을 흡수해 꾸준함이 좋아진다.', {'ovr': 1, 'loyalty': 6, 'fame': 1}),
                ('mentor_independent', '스스로 해결한다', '자신만의 방법을 고집한다.', {'ovr': 2, 'loyalty': -2}),
            ]),
            ('fan_vote', '팬 투표 이벤트', '팬들이 뽑는 시즌 인기 선수 후보에 올랐다.', '📣', [
                ('fan_engage', '팬들과 소통', '팬들의 지지가 크게 올라간다.', {'fame': 8, 'loyalty': 4}),
                ('fan_focus', '경기에 집중', '팬보다 성적을 선택한다.', {'ovr': 1}),
            ]),
            ('defense_special', '수비 특훈', '수비 코치가 당신의 약점을 정확히 짚었다.', '🛡️', [
                ('defense_yes', '특훈 참가', '수비 능력 향상을 노린다.', {'ovr': 1, 'ability_fielding': 3, 'stamina': -6}),
                ('defense_no', '타격/투구 집중', '주무기를 더 날카롭게 만든다.', {'ovr': 1, 'stamina': -3}),
            ]),
            ('contract_risk', '계약 연장 협상', '구단이 장기 계약을 제안했지만 금액은 기대보다 낮다.', '📝', [
                ('contract_safe', '안정적으로 서명', '안정적인 커리어를 선택한다.', {'money': 10000000, 'loyalty': 8}),
                ('contract_bet', '더 기다린다', '성적이 더 좋아지면 큰 계약을 노릴 수 있다.', {'fame': 3, 'loyalty': -4}),
            ]),
        ]
        key, title, desc, icon, choices = random.choice(events)
        return {'type': 'random_card', 'event_id': key, 'title': title, 'desc': desc, 'icon': icon,
                'options': [{'id': choice_id, 'kind': 'plain', 'icon': '✓' if i == 0 else '→', 'label': label,
                             'detail': detail, 'effect': effect} for i, (choice_id, label, detail, effect) in enumerate(choices)]}

    # Existing milestone events are kept as rarer special events.
    if not state.high_school_done and 17 <= state.age <= 19 and random.random() < .30:
        state.high_school_done = True
        return {'type':'high_school','title':'학업과 커리어 사이','desc':'학업을 마저 끝낼지, 야구에만 전념할지 결정할 시간이다.','icon':'🎓',
                'options':[{'id':'accept','kind':'plain','icon':'🎓','label':'학업 병행','detail':'일시적으로 OVR -1, 대신 충성도가 오릅니다.'},
                           {'id':'reject','kind':'plain','icon':'⚾','label':'야구에 전념','detail':'훈련에 집중합니다.'}]}

    if not state.captain and state.loyalty >= 70 and state.season >= 4 and random.random() < .22:
        return {'type':'captain','title':'주장 완장 제안','desc':flavor('captain'),'icon':'🎖️',
                'options':[{'id':'accept','kind':'plain','icon':'🎖️','label':'주장 수락','detail':'명성과 충성도가 상승합니다.'},
                           {'id':'decline','kind':'plain','icon':'🙅','label':'정중히 거절','detail':'선수 본연에 집중합니다.'}]}

    if (state.overall >= 74 and state.age >= 19 and eligible_competitions(state.nationality, state.age, state.year) and random.random() < .05):
        competition = random.choice(eligible_competitions(state.nationality, state.age, state.year))
        return {'type':'national_call','title':'국가대표 합류 여부','desc':f'{competition.get("name", "국제대회")} 대표팀 선발 경쟁에 이름을 올렸다.','icon':'🌍','competition':competition,
                'options':[{'id':'accept','kind':'plain','icon':'🌍','label':'국가대표 합류','detail':'대표팀 경력과 명성이 상승합니다.'},
                           {'id':'decline','kind':'plain','icon':'🏟️','label':'클럽에 집중','detail':'이번 소집을 고사합니다.'}]}

    tier_now = LEAGUE_TIER.get(state.league_id, 1)
    offers = _offer_candidates(state, 2)
    cur = team(state.team_id) or {}
    options = [{'id':'stay','kind':'club','label':f"{cur.get('name','현재 구단')}에 잔류",'detail':'안정적인 역할 유지','team_id':state.team_id,'league_id':state.league_id,
                'name':cur.get('name','현재 구단'),'league_name':(league(state.league_id) or {}).get('name',''),'badge':team_badge(state.team_id,cur.get('name')),'stay':True}]
    for t in offers: options.append(_club_option(t,tier_now))
    if state.age >= 34:
        options.append({'id':'retire_now','kind':'plain','icon':'🏁','label':'은퇴 결심','detail':'지금까지의 커리어를 마무리합니다.'})
    return {'type':'transfer_window','title':'이적 시장이 열렸다','desc':flavor('contract'),'icon':'🔄','options':options}

def resolve_event(state, option_id):
    ev=state.pending_event or {}
    options=ev.get('options',[])
    chosen=next((o for o in options if str(o.get('id'))==str(option_id)), options[0] if options else None)
    if not chosen:
        state.decision_used=True; return state
    etype=ev.get('type'); label=chosen.get('label','선택')
    if etype=='random_card':
        effect=chosen.get('effect',{})
        state.overall=max(30,min(99,state.overall+int(effect.get('ovr',0))))
        state.potential=max(state.overall,min(99,state.potential+int(effect.get('potential',0))))
        state.stamina=max(10,min(100,state.stamina+int(effect.get('stamina',0))))
        state.fame=max(0,min(100,state.fame+int(effect.get('fame',0))))
        state.loyalty=max(0,min(100,state.loyalty+int(effect.get('loyalty',0))))
        state.money=max(0,state.money+int(effect.get('money',0)))
        for key in ('fielding','contact','power','eye','speed','arm','velocity','command','breaking','stamina_skill'):
            if state.abilities and effect.get('ability_'+key):
                state.abilities[key]=max(25,min(99,state.abilities.get(key,50)+int(effect['ability_'+key])))
    elif etype=='injury':
        if chosen['id']=='early_return': state.stamina=max(20,state.stamina-10); state.overall=max(30,state.overall-2)
        else: state.stamina=min(100,state.stamina+20)
        state.injury_active=False
    elif etype=='high_school':
        if chosen['id']=='accept': state.overall=max(30,state.overall-1); state.loyalty=min(100,state.loyalty+8)
    elif etype=='captain':
        if chosen['id']=='accept': state.captain=True; state.fame=min(100,state.fame+10); state.loyalty=min(100,state.loyalty+10)
    elif etype=='national_call':
        if chosen['id']=='accept':
            state.international_caps+=1; state.fame=min(100,state.fame+8); state.stamina=max(20,state.stamina-8); state.loyalty=max(10,state.loyalty-3)
            if random.random() < (0.08 + max(0,state.overall-75)*0.003):
                state.international_titles+=1; comp=ev.get('competition') or {}
                names={'World Baseball Classic':'월드베이스볼클래식(WBC)','WBSC Premier12':'프리미어12','Olympic Baseball':'올림픽 야구','Asian Games Baseball':'아시안게임 야구','WBSC U-23':'WBSC U-23 야구월드컵','WBSC U-18':'WBSC U-18 야구월드컵'}
                cname=names.get(comp.get('name'),comp.get('name','국제대회'))
                trophy={'competition_id':comp.get('competition_id','INTL'),'competition_name':cname,'year':state.year,'age':state.age}
                state.international_trophies.append(trophy); state.last_trophy={'type':'international','category':'국가대표','name':cname+' 우승','year':state.year}
                state.last_event=cname+' 우승을 경험했다!'
        else: state.loyalty=min(100,state.loyalty+5)
    elif etype=='fan_backlash':
        if chosen['id']=='fight': state.overall=max(30,state.overall-2); state.loyalty=min(100,state.loyalty+15)
        else:
            state.team_id=chosen.get('team_id') or state.team_id; state.league_id=chosen.get('league_id') or state.league_id; state.transfers_count+=1; state.loyalty=max(10,state.loyalty-15); state.fame=min(100,state.fame+2)
    elif etype=='transfer_window':
        if chosen['id']=='retire_now': state.status='retired'
        elif chosen.get('stay'): state.loyalty=min(100,state.loyalty+6); state.fame=min(100,state.fame+1)
        else:
            new_team,new_league=chosen.get('team_id'),chosen.get('league_id'); tier_now=LEAGUE_TIER.get(state.league_id,1); tier_new=LEAGUE_TIER.get(new_league,tier_now)
            state.team_id,state.league_id=new_team,new_league; state.transfers_count+=1; state.loyalty=max(10,state.loyalty-20); state.role='starter' if tier_new<tier_now else ('bench' if tier_new>tier_now else 'rotation'); state.fame=min(100,state.fame+(6 if tier_new>tier_now else 2))
    state.last_decision=label; state.decision_used=True
    if not state.last_event or etype in ('transfer_window','fan_backlash','random_card'): state.last_event=f'{label}을(를) 선택했다.'
    state.pending_event=None
    return state

def _mvp_score(state,games,extra,champion=False):
    ovr=state.overall
    if state.position=='SP':
        era=extra.get('era',6.0); wins=extra.get('wins',0); so=extra.get('so',0); innings=extra.get('innings',0)
        score=wins*4.6+max(0,4.40-era)*18.5+so*.06+innings*.03+ovr*.30
        if games<24 or innings<145: score-=max(0,24-games)*5+max(0,145-innings)*.05
    elif state.position=='RP':
        era=extra.get('era',6.0); saves=extra.get('saves',0); so=extra.get('so',0)
        score=saves*2.15+max(0,4.00-era)*17+so*.04+games*.10+ovr*.25
        if games<55 or saves<30: score-=max(0,55-games)*1.8+max(0,30-saves)*2
    else:
        avg=extra.get('avg',.250); hr=extra.get('hr',0); rbi=extra.get('rbi',0); ops=extra.get('ops',.700); pa=extra.get('pa',0)
        score=max(0,avg-.240)*760+hr*1.65+rbi*.82+max(0,ops-.650)*105+pa*.025+ovr*.30
        if games<110 or pa<450: score-=max(0,110-games)*1.5+max(0,450-pa)*.035
    if champion: score+=7
    if state.role=='starter': score+=2
    elif state.role=='bench': score-=5
    if ovr<82: score-=(82-ovr)*1.8
    return round(score,1)

def _mvp_candidate(state,idx):
    rng=random.Random(f"mvp:{state.year}:{state.team_id}:{state.player_name}:{idx}:{state.difficulty}")
    base=max(72,min(98,state.overall+rng.randint(-4,8)))
    if state.position=='SP':
        games=rng.randint(25,34); wins=max(12,round(games*(.42+base/1000)+rng.randint(-2,2))); era=round(max(1.75,min(4.8,5.9-base/18+rng.uniform(-.3,.3))),2); innings=games*rng.uniform(5,6.4); so=max(100,round(innings*(6+base/35))); extra={'wins':wins,'saves':0,'era':era,'so':so,'innings':innings}; line=f'{games}경기 · {wins}승 · ERA {era} · {so}K'
    elif state.position=='RP':
        games=rng.randint(55,76); saves=max(30,round((base-48)*.75+rng.randint(-3,7))); era=round(max(1.5,min(4.5,5.3-base/17+rng.uniform(-.3,.3))),2); so=max(55,round(games*(1.1+base/100))); extra={'wins':rng.randint(3,10),'saves':saves,'era':era,'so':so,'innings':games*rng.uniform(.9,1.5)}; line=f'{games}경기 · {saves}SV · ERA {era}'
    else:
        games=rng.randint(112,144); avg=round(min(.370,max(.260,.278+(base-65)/1200+rng.uniform(-.012,.012))),3); hr=max(15,round(games*max(.07,(base-45)/310)+rng.randint(-3,5))); rbi=max(45,round(hr*2.35+games*(base-50)/400+rng.randint(-8,8))); ops=round(min(1.180,max(.700,.590+base/230+rng.uniform(-.035,.035))),3); pa=games*rng.uniform(3.8,4.5); extra={'avg':avg,'hr':hr,'rbi':rbi,'ops':ops,'pa':pa}; line=f'{games}경기 · {avg:.3f} · {hr}HR · {rbi}RBI · OPS {ops:.3f}'
    fake=type('MVPProxy',(),{'position':state.position,'overall':base,'role':'starter'})()
    return {'name':f'리그 MVP 후보 {idx}','overall':base,'score':_mvp_score(fake,games,extra,champion=rng.random()<.35),'statline':line}

def _resolve_mvp(state,games,extra,champion=False):
    if state.position=='SP': eligible=games>=24 and extra.get('innings',0)>=145 and state.overall>=82
    elif state.position=='RP': eligible=games>=55 and extra.get('saves',0)>=30 and state.overall>=82
    else: eligible=games>=110 and extra.get('pa',0)>=450 and state.overall>=82
    player_score=_mvp_score(state,games,extra,champion); candidates=[_mvp_candidate(state,i) for i in range(1,5)]
    candidates.append({'name':state.player_name,'overall':state.overall,'score':player_score,'statline':(f"{games}경기 · {extra.get('avg',0):.3f} · {extra.get('hr',0)}HR · {extra.get('rbi',0)}RBI" if state.position not in ('SP','RP') else f"{games}경기 · {extra.get('wins',0)}승 · {extra.get('saves',0)}SV · ERA {extra.get('era',0):.2f}")})
    candidates.sort(key=lambda x:x['score'],reverse=True)
    for rank,item in enumerate(candidates,1): item['rank']=rank
    winner=candidates[0]; won=eligible and winner['name']==state.player_name
    state.last_mvp_race={'year':state.year,'winner':winner['name'],'won':won,'eligible':eligible,'player_score':player_score,'candidates':candidates}
    return won

def _add_individual_awards(state,strength,games,extra,champion=False):
    awards=[]; allstar_min=20 if state.position=='SP' else 55 if state.position=='RP' else 110
    if strength>=76 and games>=allstar_min and random.random()<.28: awards.append(('ALL_STAR','올스타','충분한 출전과 성적을 바탕으로 올스타에 선정됐다.','✨'))
    if state.position=='SP':
        era=extra.get('era',9.99); wins=extra.get('wins',0); innings=extra.get('innings',0)
        if era<=2.45 and wins>=15 and innings>=160 and strength>=84 and random.random()<.55: awards.append(('CY_YOUNG','사이영상','리그 최고의 선발투수에게 주어지는 상을 수상했다.','🏅'))
        if state.age<=22 and strength>=72 and games>=24 and not any(a.get('award_id')=='ROY' for a in state.individual_awards): awards.append(('ROY','신인왕','신인왕을 차지했다.','🌟'))
    elif state.position=='RP':
        era=extra.get('era',9.99); saves=extra.get('saves',0)
        if saves>=35 and era<=2.50 and games>=55 and strength>=84 and random.random()<.55: awards.append(('RELIEVER','올해의 마무리','최고의 마무리투수로 선정됐다.','🚨'))
    else:
        avg=extra.get('avg',0); hr=extra.get('hr',0); rbi=extra.get('rbi',0); pa=extra.get('pa',0); field=state.abilities.get('fielding',50) if state.abilities else 50
        if avg>=.335 and games>=120 and pa>=480: awards.append(('BATTING_TITLE','타격왕','충분한 타석을 소화하고 시즌 타율 1위를 기록했다.','🏏'))
        if hr>=40 and games>=120: awards.append(('HR_KING','홈런왕','40홈런 이상과 충분한 출장으로 홈런왕을 차지했다.','💥'))
        if rbi>=110 and games>=120: awards.append(('RBI_KING','타점왕','110타점 이상을 기록하며 타점왕을 차지했다.','🔥'))
        if field>=90 and games>=120 and strength>=78 and random.random()<.50: awards.append(('GOLD_GLOVE','골드글러브','수비력과 충분한 출장량을 인정받았다.','🧤'))
        if state.age<=22 and strength>=72 and games>=100 and pa>=400 and not any(a.get('award_id')=='ROY' for a in state.individual_awards): awards.append(('ROY','신인왕','신인왕을 차지했다.','🌟'))
    if _resolve_mvp(state,games,extra,champion): awards.append(('MVP','MVP','리그 전체 경쟁에서 가장 높은 평가를 받아 MVP에 선정됐다.','👑'))
    for aid,name,desc,icon in awards: state.individual_awards.append({'award_id':aid,'name':name,'desc':desc,'icon':icon,'year':state.year,'age':state.age})
    return awards

def _add_club_trophies(state, strength):
    tier = LEAGUE_TIER.get(state.league_id, 1)
    state.last_trophy = None
    # League title. Higher OVR + starter role + league tier = stronger chance.
    league_chance = max(.05, min(.48, .05 + strength / 300 + tier * .012 + (0.05 if state.role == 'starter' else 0)))
    if random.random() < league_chance:
        trophy = {'type':'league', 'category':'리그', 'name': {'KBO':'KBO 한국시리즈','NPB':'NPB 일본시리즈','MLB':'MLB 월드시리즈','CPBL':'CPBL 대만시리즈'}.get(state.league_id, f"{(league(state.league_id) or {}).get('name','리그')} 챔피언"), 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id), 'league_id':state.league_id, 'league_name':(league(state.league_id) or {}).get('name', state.league_id)}
        state.club_trophies.append(trophy); state.league_titles += 1; state.titles += 1; state.last_trophy = trophy
    # Domestic cup is rarer and separate from the league title.
    if random.random() < min(.18, .02 + strength / 480 + tier * .006):
        trophy = {'type':'cup', 'category':'국내 컵', 'name': {'KBO':'KBO 국내 컵','NPB':'NPB 국내 컵','MLB':'MLB 컵','CPBL':'CPBL 컵'}.get(state.league_id, '국내 컵') + ' 우승', 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id), 'league_id':state.league_id, 'league_name':(league(state.league_id) or {}).get('name', state.league_id)}
        state.club_trophies.append(trophy); state.cup_titles += 1; state.titles += 1; state.last_trophy = trophy
    # Continental titles are reserved for upper-level leagues.
    if tier >= 4 and random.random() < min(.12, .008 + strength / 900 + (tier-3)*.014):
        trophy = {'type':'continental', 'category':'대륙 대회', 'name':'대륙 클럽 대회 우승', 'year':state.year, 'team':canonical_team_name(state.team_id, state.team_id), 'league_id':state.league_id, 'league_name':(league(state.league_id) or {}).get('name', state.league_id)}
        state.club_trophies.append(trophy); state.continental_titles += 1; state.titles += 1; state.last_trophy = trophy
    return state.last_trophy


def simulate_season(state):
    """야구식 시즌 시뮬레이션. 난이도에 따라 성장/부상/성적 변동폭을 조절한다."""
    role_mult = ROLE_INFO.get(state.role, ROLE_INFO['rotation'])
    diff = DIFFICULTY_INFO.get(state.difficulty, DIFFICULTY_INFO['pro'])

    # Copero-like OVR curve: explosive development before the mid-20s,
    # then a long plateau. From 26 onward a season usually ends with no OVR
    # movement; decline becomes the main force in the mid/late 30s.
    if state.age <= 18:
        age_base = random.uniform(3.0, 5.0)
    elif state.age <= 21:
        age_base = random.uniform(2.0, 3.8)
    elif state.age <= 24:
        age_base = random.uniform(0.8, 2.4)
    elif state.age <= 25:
        age_base = random.uniform(0.0, 1.0)
    elif state.age <= 27:
        age_base = 0.0 if random.random() < 0.72 else random.uniform(-0.5, 0.6)
    elif state.age <= 30:
        age_base = 0.0 if random.random() < 0.78 else random.uniform(-0.6, 0.4)
    elif state.age <= 33:
        age_base = 0.0 if random.random() < 0.55 else random.uniform(-0.9, 0.2)
    elif state.age <= 36:
        age_base = random.uniform(-1.6, 0.0)
    else:
        age_base = random.uniform(-3.2, -1.2)

    potential_gap = state.potential - state.overall
    if potential_gap <= 0:
        age_base = min(age_base, -0.2 if state.age >= 28 else 0.0)
    elif potential_gap < 4:
        age_base *= 0.25
    elif potential_gap < 8:
        age_base *= 0.55

    role_bonus = {'starter': 0.35, 'rotation': 0.0, 'bench': -0.55}.get(state.role, 0)
    growth = age_base + diff['growth_bonus'] + role_bonus + random.uniform(-0.25, 0.25)
    if state.age >= 26 and random.random() < 0.18:
        growth = 0.0
    if state.age >= 29 and state.difficulty == 'hell':
        growth -= random.uniform(0.1, 0.5)
    old_ovr = state.overall
    state.overall = max(30, min(99, round(state.overall + growth)))
    actual_growth = state.overall - old_ovr
    state.last_ovr = old_ovr
    state.ovr_change = actual_growth
    state.peak_overall = max(state.peak_overall, state.overall)
    _update_abilities(state, actual_growth)

    strength = state.overall * diff.get('performance_mult', 1.0)

    if state.position in ('SP', 'RP'):
        # 선발은 시즌 20~34경기, 불펜은 35~75경기 정도가 현실적인 범위
        if state.position == 'SP':
            games = max(8, round(random.randint(20, 34) * role_mult['games_mult'] * (0.94 if state.difficulty == 'hell' else 1.0)))
            innings = max(35, round(games * random.uniform(4.2, 6.4)))
            wins = max(0, round(games * (0.15 + strength / 900) + random.randint(-3, 3)))
            saves = 0
        else:
            games = max(15, round(random.randint(38, 72) * role_mult['games_mult'] * (0.94 if state.difficulty == 'hell' else 1.0)))
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
        games = max(35, round(random.randint(100, 144) * role_mult['games_mult'] * (0.94 if state.difficulty == 'hell' else 1.0)))
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
