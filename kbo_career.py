import random, uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime

KBO_TEAMS = [
    ('LG','LG 트윈스'),('KT','KT 위즈'),('SSG','SSG 랜더스'),('NC','NC 다이노스'),
    ('두산','두산 베어스'),('KIA','KIA 타이거즈'),('롯데','롯데 자이언츠'),('삼성','삼성 라이온즈'),
    ('한화','한화 이글스'),('키움','키움 히어로즈')
]
POSITIONS = {'C':'포수','1B':'1루수','2B':'2루수','3B':'3루수','SS':'유격수','OF':'외야수','SP':'선발투수','RP':'불펜투수'}
# 가상의 선수 에이전시. 실제 회사/에이전트와 무관한 게임용 설정입니다.
AGENTS = {
    'han': ('하이브릿지 스포츠', '🧠', '신중하고 계산적인 성격. 선수의 가치를 장기적으로 분석하며 계약 조건을 하나씩 따져 가장 안정적인 선택을 추구합니다.'),
    'seo': ('넥스트베이스 매니지먼트', '🌎', '공격적이고 도전적인 성격. 해외 진출과 새로운 기회를 적극적으로 찾으며 위험을 감수해서라도 더 큰 무대를 노립니다.'),
    'park': ('퍼스트라인 스포츠', '📈', '차분하고 장기지향적인 성격. 선수의 성장과 몸 상태를 세밀하게 관리하고 당장의 큰 계약보다 커리어 전체의 가치를 중요하게 생각합니다.'),
    'choi': ('플레이메이커 스포츠', '🤝', '친화적이고 관계를 중시하는 성격. 구단과 지도자와의 신뢰를 중요하게 여기며 원만한 협상과 안정적인 커리어를 선호합니다.'),
    'kang': ('그랜드슬램 매니지먼트', '🔥', '승부욕이 강하고 야심찬 성격. 최고 수준의 연봉과 주전 보장을 적극적으로 요구하며 FA·이적·해외 도전에도 거침없이 나섭니다.'),
}

FAMILY_TYPES = ['가족 중심','커리어 중심','균형형']

@dataclass
class KBOState:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    player_name: str = '신인'
    position: str = 'SS'
    position_skills: dict = field(default_factory=dict)
    position_offer: dict = None
    bats: str = 'R'
    school: str = 'high'
    age: int = 18
    year: int = 2026
    team_id: str = ''
    team_name: str = ''
    jersey: int = 1
    ovr: int = 55
    potential: int = 85
    fame: int = 0
    money: int = 0
    stamina: int = 85
    family: int = 55
    reputation: int = 50
    loyalty: int = 55
    agent: str = ''
    agent_trust: int = 60
    spouse: bool = False
    relationship_status: str = 'none'  # none/meeting/dating/serious/engaged/married
    partner_name: str = ''
    relationship_years: int = 0
    engagement_year: int = 0
    children: int = 0
    child_birth_years: list = field(default_factory=list)
    military: str = '미필'
    military_choice: str = ''
    army_years: int = 0
    military_original_team_id: str = ''
    military_original_team_name: str = ''
    service_seasons: int = 0
    registered_days: int = 0
    fa_eligible: bool = False
    fa_count: int = 0
    contract_years_left: int = 1
    salary: int = 3000
    contract_total: int = 0
    posting_eligible: bool = False
    overseas: bool = False
    overseas_years: int = 0
    injuries: int = 0
    career_games: int = 0
    career_hr: int = 0
    career_rbi: int = 0
    career_wins: int = 0
    career_saves: int = 0
    career_war: float = 0.0
    championships: int = 0
    mvp: int = 0
    gg: int = 0
    allstar: int = 0
    national_caps: int = 0
    national_titles: int = 0
    season_stats: list = field(default_factory=list)
    history: list = field(default_factory=list)
    awards: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    pending_team_move: dict = None
    stage: str = 'dashboard'
    training_done: bool = False
    life_done: bool = False
    office_done: bool = False
    retired: bool = False
    last_intl: str = ''
    pending_event: dict = None
    event_done: bool = False
    career_stage: str = '신인'
    contract_history: list = field(default_factory=list)
    team_history: list = field(default_factory=list)
    number_history: list = field(default_factory=list)
    family_notes: list = field(default_factory=list)
    fa_grade: str = ''
    fa_offer: dict = None
    fa_negotiation_round: int = 0
    fa_service_target: int = 8
    fa_signed_this_cycle: bool = False
    fa_compensation: dict = None
    posting_stage: str = ''
    posting_offers: list = field(default_factory=list)
    posting_return_offers: list = field(default_factory=list)
    manager_role: str = '2군 경쟁'
    captain_role: str = ''
    personal_goal: str = ''
    personal_goal_progress: int = 0
    fan_popularity: int = 0
    sponsors: list = field(default_factory=list)
    sponsor_income: int = 0
    pending_special_event: dict = None
    national_offer: dict = None
    national_history: list = field(default_factory=list)
    draft_offers: list = field(default_factory=list)
    # v6 career-life systems
    injury_status: str = ''
    injury_name: str = ''
    injury_days: int = 0
    rehab_stage: str = ''
    rehab_count: int = 0
    rival_name: str = ''
    rival_team: str = ''
    rivalry_score: int = 0
    league_news: list = field(default_factory=list)
    assets: list = field(default_factory=list)
    asset_value: int = 0
    spending: int = 0
    permanent_number: bool = False
    permanent_number_team: str = ''
    permanent_number_reason: str = ''
    retirement_honor: str = ''
    dynamic_choices: dict = field(default_factory=dict)


def from_dict(raw):
    s=KBOState(**{k:v for k,v in (raw or {}).items() if k in KBOState.__dataclass_fields__})
    if not s.position_skills: s.position_skills={s.position: 100}
    return s

def team_name(team_id):
    return dict(KBO_TEAMS).get(team_id, team_id or '미정')

def _roll_stats(s):
    """KBO 현실 범위에 맞춘 단일 시즌 성적 생성.

    핵심 원칙
    - 야수 G <= 144, 타율은 일반적으로 .230~.330대, 최상위권만 .350 안팎.
    - 선발은 22~30경기/110~190이닝, 승수는 5~20승 수준.
    - 불펜은 35~75경기, 세이브/홀드는 역할에 따라 분리.
    - 1군 등록일수는 경기수와 별개인 '로스터에 있었던 날짜'라서 항상 경기수보다 충분히 크거나 같다.
    """
    age=s.age
    ovr=float(s.ovr)
    health=max(.45, min(1.05, s.stamina/100))
    luck=random.uniform(.94,1.06)
    injury_penalty=0.72 if s.injury_status else 1.0

    if s.position=='SP':
        # KBO 선발 로테이션: 건강한 풀시즌도 대체로 25~30경기.
        starts=int(random.gauss(26,3) * (0.70 + 0.30*health) * injury_penalty)
        if age < 21: starts=int(starts*.60)
        if age >= 35: starts=int(starts*.72)
        starts=max(8,min(32,starts))
        games=starts
        ip_per_start=random.uniform(4.6,6.4) * (0.90 + 0.10*health)
        ip=round(min(200.0, starts*ip_per_start),1)
        era=max(2.25, min(6.50, 5.05 - (ovr-55)*.050 + random.uniform(-.35,.35)))
        # 10승은 좋은 선발, 15승 이상은 에이스 시즌. 20승은 매우 희귀.
        win_rate=max(.18,min(.72,.30 + (ovr-55)*.007 + (3.8-era)*.035 + random.uniform(-.06,.06)))
        wins=min(starts, max(0, int(round(starts*win_rate))))
        losses=max(0, int(round(starts*random.uniform(.12,.34))))
        so=max(20,int(ip*(5.8 + (ovr-60)*.065 + random.uniform(-.6,.6))/9))
        walks=max(8,int(ip*(2.8 - (ovr-60)*.018 + random.uniform(-.25,.35))/9))
        war=max(-0.3, min(9.0, ip*(5.2-era)/30 + random.uniform(-.45,.45)))
        saves=0; holds=0
        primary=f'{wins}승 {losses}패'
        secondary=f'{era:.2f} ERA · {ip:.1f}이닝 · {so}K'
        days=min(172,max(45,int(150*health + random.randint(-12,10))))
        return {'year':s.year,'age':s.age,'team':s.team_name,'games':games,'primary':primary,'secondary':secondary,
                'war':round(war,1),'avg':None,'hr':0,'rbi':0,'wins':wins,'losses':losses,'saves':saves,'holds':holds,
                'era':round(era,2),'ip':ip,'strikeouts':so,'walks':walks,'registered_days':days}

    if s.position=='RP':
        games=int(random.gauss(58,9) * (0.72+0.28*health) * injury_penalty)
        if age<21: games=int(games*.65)
        if age>=35: games=int(games*.78)
        games=max(20,min(78,games))
        ip=round(games*random.uniform(0.75,1.25),1)
        era=max(2.35,min(6.30,5.00-(ovr-55)*.048+random.uniform(-.4,.4)))
        saves=0; holds=0
        # 마무리 역할은 저장된 manager_role/OVR을 바탕으로 일부 시즌만 부여.
        closer=(s.manager_role in ('핵심 주전','팀의 중심') and ovr>=78) or random.random()<.22
        if closer:
            saves=max(0,min(45,int(games*.40*(ovr/90)*random.uniform(.65,1.08))))
        else:
            holds=max(0,min(30,int(games*.28*(ovr/82)*random.uniform(.55,1.05))))
        wins=max(0,min(12,int(games*.10*(ovr/90)*random.uniform(.5,1.3))))
        losses=max(0,min(10,int(games*.08*random.uniform(.5,1.5))))
        so=max(10,int(ip*(6.0+(ovr-60)*.06+random.uniform(-.7,.7))/9))
        walks=max(4,int(ip*(3.0-(ovr-60)*.015+random.uniform(-.3,.4))/9))
        war=max(-0.2,min(5.0,ip*(4.8-era)/28+random.uniform(-.3,.3)))
        days=min(172,max(35,int(135*health+random.randint(-15,18))))
        primary=f'{wins}승 {losses}패'
        if saves: primary=f'{saves}세이브'
        elif holds: primary=f'{holds}홀드'
        secondary=f'{era:.2f} ERA · {ip:.1f}이닝 · {so}K'
        return {'year':s.year,'age':s.age,'team':s.team_name,'games':games,'primary':primary,'secondary':secondary,
                'war':round(war,1),'avg':None,'hr':0,'rbi':0,'wins':wins,'losses':losses,'saves':saves,'holds':holds,
                'era':round(era,2),'ip':ip,'strikeouts':so,'walks':walks,'registered_days':days}

    # 야수: 출장기회와 타석을 먼저 만들고 타율/안타를 계산한다.
    role_factor=0.52 + min(0.43,max(0.0,(ovr-55)/44))
    games=int(random.gauss(118,17)*role_factor*health*injury_penalty)
    if age<21: games=int(games*.58)
    elif age<23: games=int(games*.82)
    if age>=35: games=int(games*.78)
    games=max(25,min(144,games))
    pa=max(70,int(games*random.uniform(3.35,4.25)))
    ab=max(60,int(pa*random.uniform(.87,.93)))

    # OVR 99도 기본적으로 .330 전후가 상한에 가깝고, .350+는 희귀한 시즌으로 만든다.
    avg=max(.190,min(.355,.235 + (ovr-55)*.00175 + random.uniform(-.018,.018)))
    if ovr>=90 and random.random()<.045:
        avg=min(.365,avg+random.uniform(.015,.028))
    hits=min(ab,max(0,int(round(ab*avg))))
    power_rate=max(.025,min(.205,.045+(ovr-55)*.00235+random.uniform(-.012,.012)))
    hr=max(0,min(45,int(round(games*power_rate))))
    doubles=max(4,int(round(hits*random.uniform(.13,.21))))
    triples=max(0,int(round(hits*random.uniform(.012,.035))))
    rbi=max(0,min(130,int(round(hr*2.15 + hits*.18 + games*.14 + random.uniform(-8,10)))))
    runs=max(0,min(135,int(round(hits*.28+pa*.08+random.uniform(-6,7)))))
    sb=max(0,min(45,int(round(games*max(0,.035+(ovr-65)*.0025)*random.uniform(.45,1.15)))))
    war=max(-1.0,min(9.0,(ovr-58)*.105*(games/144)+random.uniform(-.55,.55)))
    days=min(172,max(games,int(games*random.uniform(1.18,1.65))))
    return {'year':s.year,'age':s.age,'team':s.team_name,'games':games,'primary':f'{avg:.3f} AVG',
            'secondary':f'{hr} HR · {rbi} RBI · {hits} H','war':round(war,1),'avg':round(avg,3),'hr':hr,'rbi':rbi,
            'hits':hits,'pa':pa,'ab':ab,'runs':runs,'sb':sb,'wins':0,'losses':0,'saves':0,'holds':0,'era':None,
            'ip':0,'strikeouts':0,'walks':0,'registered_days':days}

def generate_rival(s):
    if s.rival_name or s.age < 20 or random.random() > .28:
        return
    rivals=[('김도윤','LG 트윈스'),('박준혁','KIA 타이거즈'),('이현우','삼성 라이온즈'),('최민재','롯데 자이언츠'),('정우진','한화 이글스'),('한승민','SSG 랜더스')]
    pool=[x for x in rivals if x[1]!=s.team_name]
    if pool:
        s.rival_name,s.rival_team=random.choice(pool)
        s.notes.append(f'{s.year} {s.rival_name}({s.rival_team})와 포지션 라이벌 관계가 형성됐다.')

def generate_league_news(s, st):
    news=[
        f'📰 {s.year} KBO: {s.team_name}의 {s.player_name}이(가) 시즌 {st["games"]}경기에 출전했다.',
        f'📰 {s.year} KBO 이슈: FA 시장에서 베테랑들의 계약 협상이 본격화됐다.',
        random.choice([
            f'📰 {s.year} KBO: 신인 선수들이 1군 경쟁에 뛰어들고 있다.',
            f'📰 {s.year} KBO: 각 구단이 포스트시즌 전력 보강을 준비하고 있다.',
            f'📰 {s.year} KBO: 국가대표 후보군을 둘러싼 경쟁이 치열해지고 있다.',
            f'📰 {s.year} KBO: 외국인 선수 교체 여부가 여러 구단의 관심사로 떠올랐다.'
        ])
    ]
    if st.get('war',0)>=5: news.insert(0,f'🔥 {s.year} KBO: {s.player_name}, 리그 정상급 시즌으로 주목받다.')
    if s.rival_name and st.get('games',0)>=100:
        news.append(f'⚔️ 라이벌 뉴스: {s.rival_name}과(와) 다음 시즌 주전 경쟁이 더욱 뜨거워질 전망이다.')
    s.league_news=news[:4]

def apply_injury_rehab(s, choice):
    if not s.injury_status:
        return
    if choice=='rehab':
        s.rehab_count += 1
        s.injury_days=max(0,s.injury_days-random.randint(25,45))
        s.stamina=min(100,s.stamina+8)
        s.ovr=max(40,s.ovr + random.choice([0,0,1]))
    elif choice=='rest':
        s.injury_days=max(0,s.injury_days-random.randint(15,30))
        s.stamina=min(100,s.stamina+15)
    elif choice=='early':
        s.injury_days=max(0,s.injury_days-random.randint(35,60))
        s.stamina=max(35,s.stamina-8)
        s.ovr=max(40,s.ovr-1)
    if s.injury_days<=0:
        s.injury_status=''; s.injury_name=''; s.rehab_stage='복귀 완료'; s.notes.append(f'{s.year} 재활을 마치고 정상적으로 복귀했다.')
    else:
        s.rehab_stage='재활 중'

def evaluate_permanent_number(s):
    if s.permanent_number:
        return
    # 단순 은퇴가 아니라 '구단 역사에 남을 만한 선수'만 영구결번.
    seasons=len(s.season_stats)
    elite=(s.mvp>=1 or s.gg>=4 or s.championships>=3 or s.career_war>=45 or s.fame>=90)
    if seasons>=10 and elite and s.team_name and s.jersey:
        s.permanent_number=True
        s.permanent_number_team=s.team_name
        s.permanent_number_reason='장기간 활약과 우승·MVP·골든글러브·WAR 등 구단 역사급 업적'
        s.retirement_honor='영구결번'
        s.notes.append(f'{s.team_name}이(가) {s.jersey}번을 영구결번으로 지정했다.')
    elif seasons>=8 and (s.mvp>=1 or s.career_war>=35 or s.fame>=85):
        s.retirement_honor='구단 레전드'

def simulate_season(s):
    # 시즌이 새로 시작될 때마다 일반 이벤트 선택 상태를 초기화한다.
    # 이전 시즌의 event_done 값이 남아 있으면 다음 시즌 이벤트를 눌러도
    # /next가 이벤트를 건너뛰는 문제가 생길 수 있다.
    s.event_done = False
    if s.military_choice:
        st={'year':s.year,'age':s.age,'team':s.team_name,'games':0,'primary':'군 복무','secondary':'야구 경기 없음','war':0.0,'avg':None,'hr':0,'rbi':0,'wins':0,'saves':0,'era':None,'registered_days':0,'military':s.military_choice}
        s.season_stats.append(st); s.history.append(st)
        s.registered_days=0
        s.stamina=min(100,s.stamina+random.randint(2,8))
        if s.military_choice=='상무': s.ovr=min(99,s.ovr+random.choice([0,1,1,2]))
        else: s.ovr=max(40,s.ovr+random.choice([-2,-1,0]))
        if s.contract_years_left>0: s.contract_years_left-=1
        return st
    st=_roll_stats(s)
    # 시즌 중 부상 발생: 다음 나이로 넘어가기 전에 재활 선택을 요구한다.
    if not s.injury_status and random.random() < max(.035, min(.16, .075 + (100-s.stamina)*.0012)):
        s.injury_status='부상'
        s.injury_name=random.choice(['햄스트링 염좌','어깨 염증','허리 통증','발목 염좌','손목 부상','팔꿈치 염증'])
        s.injury_days=random.randint(20,120)
        s.rehab_stage='진단 완료'
        old_games=max(1,int(st['games']))
        new_games=max(1,int(old_games*random.uniform(.65,.88)))
        ratio=new_games/old_games
        st['games']=new_games
        for key in ('pa','ab','hits','hr','rbi','runs','sb'):
            if key in st: st[key]=max(0,int(round(st[key]*ratio)))
        st['registered_days']=max(st['games'],min(172,st['registered_days']+random.randint(0,15)))
        if st.get('avg') is not None:
            st['primary']='%.3f AVG' % st['avg']
            st['secondary']='%d HR · %d RBI · %d H' % (st.get('hr',0), st.get('rbi',0), st.get('hits',0))
        s.injuries += 1
    s.season_stats.append(st); s.history.append(st)
    s.career_games += st['games']; s.career_hr += st['hr']; s.career_rbi += st['rbi']; s.career_wins += st['wins']; s.career_saves += st['saves']; s.career_war += st['war']
    s.registered_days=st['registered_days']
    if st['registered_days']>=145: s.service_seasons += 1
    # awards / team result
    if st['war'] >= 5.5 and random.random()<.28: s.allstar += 1; s.awards.append(f"{s.year} 올스타")
    if st['war'] >= 7 and random.random()<.16: s.gg += 1; s.awards.append(f"{s.year} 골든글러브")
    if st['war'] >= 8 and random.random()<.10: s.mvp += 1; s.awards.append(f"{s.year} MVP")
    if random.random()<max(.04,min(.28,(st['war']+1)/40)):
        s.championships += 1; s.awards.append(f"{s.year} 한국시리즈 우승")
    s.fame=max(0,min(100,s.fame+int(st['war']*.8)+random.randint(-2,3)))
    s.money += int(s.salary/12*random.uniform(.85,1.15))
    # age-based OVR curve
    if s.age <= 21: delta=random.randint(1,4)
    elif s.age <= 24: delta=random.randint(0,3)
    elif s.age <= 27: delta=random.choice([0,0,1,2])
    elif s.age <= 30: delta=random.choice([-1,0,0,1])
    elif s.age <= 34: delta=random.choice([-1,0,0])
    elif s.age <= 37: delta=random.randint(-2,0)
    else: delta=random.randint(-4,-1)
    if s.agent=='park' and s.age<=27: delta += random.choice([0,0,1])
    if s.age>=32 and s.position in ('SP','RP'): delta -= 1
    if s.injuries and random.random()<.3: delta -= 1
    s.ovr=max(40,min(99,s.ovr+delta))
    s.potential=max(s.ovr,min(99,s.potential))
    if s.position=='SP':
        if st['games']>=25 and st['war']>=3: s.manager_role=random.choice(['주전','핵심 주전','팀의 중심'])
        elif st['games']>=18: s.manager_role=random.choice(['선발 경쟁','로테이션','백업'])
        else: s.manager_role=random.choice(['2군 경쟁','로테이션','재활/회복'])
    elif s.position=='RP':
        if st['games']>=55 and st['war']>=2: s.manager_role=random.choice(['주전','핵심 주전','팀의 중심'])
        elif st['games']>=35: s.manager_role=random.choice(['필승조 경쟁','불펜 로테이션','백업'])
        else: s.manager_role=random.choice(['2군 경쟁','불펜 로테이션','재활/회복'])
    else:
        if st['games'] >= 120 and st['war'] >= 3: s.manager_role=random.choice(['주전','핵심 주전','팀의 중심'])
        elif st['games'] >= 70: s.manager_role=random.choice(['플래툰/로테이션','주전 경쟁','백업'])
        else: s.manager_role=random.choice(['2군 경쟁','백업','재활/회복'])
    s.stamina=max(45,min(100,s.stamina+random.randint(-4,7)))
    # First FA: 8 qualifying seasons. After that, the next FA clock follows
    # the length of the previous FA contract negotiated by the player.
    target=max(1, int(s.fa_service_target or 8))
    s.fa_eligible=(s.service_seasons>=target and s.contract_years_left<=0 and not s.overseas)
    s.posting_eligible=(s.age>=25 and s.ovr>=78 and s.service_seasons>=7 and not s.overseas)
    generate_rival(s)
    if s.rival_name and st.get('games',0)>=80:
        s.rivalry_score=max(-10,min(10,s.rivalry_score+random.choice([-1,0,1])))
    generate_league_news(s, st)
    update_life_systems(s, st)
    generate_special_event(s, st)
    # salary growth
    if s.contract_years_left>0: s.contract_years_left-=1
    if s.contract_years_left<=0 and not s.fa_eligible:
        s.salary=max(3300 if s.year>=2027 else 3000,int(s.salary*(1+max(-.15,min(.35,st['war']/25+random.uniform(-.08,.08))))))
        s.contract_years_left=1
    return st

POSITION_LINKS = {
    'C':['1B'], '1B':['3B','DH'], '2B':['SS','3B'], '3B':['SS','1B'],
    'SS':['2B','3B'], 'OF':['CF','LF','RF'], 'SP':['RP'], 'RP':['SP']
}

PERSONAL_GOALS = [
    ('주전 자리 확보', '주전 경쟁에서 살아남는다'),
    ('올스타 선정', '올스타에 선정된다'),
    ('골든글러브', '골든글러브를 수상한다'),
    ('커리어 WAR 30', '커리어 WAR 30을 달성한다'),
    ('홈런 20개 시즌', '한 시즌 20홈런을 기록한다'),
    ('두 자릿수 승리', '한 시즌 10승을 달성한다'),
    ('FA 대박', 'FA 계약을 체결한다'),
    ('국가대표', '국가대표에 선발된다'),
]

SPONSOR_POOL = ['야구용품 브랜드','스포츠웨어 브랜드','음료 브랜드','금융 브랜드','지역 대표 기업']

def prepare_early_position_offer(s):
    if s.age > 23 or s.position_offer or len(s.position_skills) >= 3: return
    if random.random() > (0.48 if s.age <= 21 else 0.25): return
    choices=POSITION_LINKS.get(s.position, [])
    choices=[x for x in choices if x not in s.position_skills and x != s.position]
    if not choices: return
    target=random.choice(choices)
    s.position_offer={'target':target,'from':s.position,'type':'확장','expires_age':s.age}

def generate_personal_goal(s):
    if not s.personal_goal:
        goal,desc=random.choice(PERSONAL_GOALS)
        s.personal_goal=goal
        s.personal_goal_progress=0

def update_life_systems(s, st):
    s.fan_popularity=max(0,min(100,int(s.fame*0.72 + s.reputation*0.28)))
    if s.age>=27 and s.reputation>=68 and not s.captain_role and random.random()<0.10:
        s.captain_role='부주장'
        s.notes.append(f'{s.year} 시즌 부주장 선임')
    if s.captain_role=='부주장' and s.age>=29 and s.reputation>=78 and random.random()<0.18:
        s.captain_role='주장'
        s.notes.append(f'{s.year} 시즌 주장 선임')
    if s.fan_popularity>=65 and len(s.sponsors)<2 and random.random()<0.18:
        brand=random.choice([x for x in SPONSOR_POOL if x not in s.sponsors])
        s.sponsors.append(brand); s.sponsor_income += random.randint(500,1800)
        s.notes.append(f'{s.year} {brand} 광고 계약')
    if s.sponsors:
        s.money += s.sponsor_income
    if s.personal_goal=='올스타 선정' and st.get('war',0)>=5.5: s.personal_goal_progress=1
    elif s.personal_goal=='골든글러브' and s.gg>0: s.personal_goal_progress=1
    elif s.personal_goal=='커리어 WAR 30': s.personal_goal_progress=min(30,int(s.career_war))
    elif s.personal_goal=='홈런 20개 시즌' and st.get('hr',0)>=20: s.personal_goal_progress=1
    elif s.personal_goal=='두 자릿수 승리' and st.get('wins',0)>=10: s.personal_goal_progress=1
    elif s.personal_goal=='FA 대박' and s.fa_count>=1: s.personal_goal_progress=1
    elif s.personal_goal=='국가대표' and s.national_caps>=1: s.personal_goal_progress=1
    elif s.personal_goal=='주전 자리 확보' and st.get('games',0)>=120: s.personal_goal_progress=1


def generate_special_event(s, st):
    if s.pending_special_event: return
    pool=[]
    if st.get('war',0)>=5:
        pool.append({'title':'끝내기 승리','text':'경기 막판 결정적인 활약으로 팀의 승리를 이끌었습니다.','choices':[('celebrate','팬들과 함께한다','팬 인기 +6'),('focus','조용히 다음 경기를 준비한다','평판 +3')]})
    if st.get('hr',0)>=2:
        pool.append({'title':'멀티 홈런 경기','text':'한 경기에서 두 개 이상의 홈런을 기록했습니다.','choices':[('media','인터뷰에 응한다','팬 인기 +5 / 인지도 +4'),('rest','휴식을 택한다','컨디션 +5')]})
    if st.get('games',0)>=110 and s.age<=24:
        pool.append({'title':'첫 주전 기회','text':'감독이 다음 시즌 주전 경쟁의 중심으로 보겠다고 밝혔습니다.','choices':[('accept','도전한다','평판 +4 / OVR +1'),('manage','몸 관리 우선','컨디션 +6')]})
    if st.get('war',0)>=6 and s.age>=25:
        pool.append({'title':'MVP 후보 급부상','text':'리그 MVP 후보 명단에 당신의 이름이 올랐습니다.','choices':[('media','주목을 즐긴다','팬 인기 +7 / 인지도 +4'),('focus','끝까지 야구에 집중한다','OVR +1 / 평판 +3')]})
    if st.get('games',0)>=130:
        pool.append({'title':'철인 시즌','text':'시즌 대부분의 경기에 출전하며 팀의 중심이 됐습니다.','choices':[('rest','회복을 최우선으로 한다','컨디션 +8'),('lead','후배들을 이끈다','평판 +6 / 팬 인기 +3')]})
    if s.captain_role:
        pool.append({'title':'선수단 리더십','text':'후배들이 중요한 순간에 당신의 조언을 구했습니다.','choices':[('lead','앞장선다','평판 +5 / 팬 인기 +3'),('quiet','조용히 돕는다','가족 +2 / 평판 +2')]})
    if s.spouse:
        pool.append({'title':'가족의 깜짝 방문','text':'긴 원정길에 가족이 몰래 찾아와 응원했습니다.','choices':[('family','함께 시간을 보낸다','가족 +8 / 컨디션 +5'),('focus','경기에 집중한다','OVR +1 / 가족 -3')]})
    if s.age>=30 and s.fame>=60:
        pool.append({'title':'레전드의 평가','text':'구단의 전설적인 선수가 당신의 커리어를 공개적으로 칭찬했습니다.','choices':[('accept','조언을 듣는다','OVR +1 / 평판 +5'),('media','인터뷰로 화답한다','팬 인기 +6 / 인지도 +3')]})
    if s.age>=35:
        pool.append({'title':'후배에게 넘기는 자리','text':'구단은 당신에게 선수단의 중심 역할을 후배에게 넘길지 물었습니다.','choices':[('lead','베테랑 리더로 남는다','평판 +6 / 컨디션 -3'),('manage','출장을 줄인다','컨디션 +8 / OVR -1')]})
    if pool: s.pending_special_event=random.choice(pool)

def age_up(s):
    s.year+=1; s.age+=1; s.training_done=s.life_done=s.office_done=False; s.stage='dashboard'; s.dynamic_choices={}
    if s.age<=23:
        prepare_early_position_offer(s)
    generate_personal_goal(s)
    if s.age>=41: s.retired=True

def draft_offers(s):
    teams=list(KBO_TEAMS); random.shuffle(teams)
    n=5 if s.ovr>=60 else 4
    return [{'team_id':tid,'name':name,'round':i+1,'signing_bonus':max(3000,int((s.ovr-45)*900+random.randint(-1000,2000)))} for i,(tid,name) in enumerate(teams[:n])]


def calculate_fa_grade(s):
    # Game approximation of the current KBO A/B/C salary-rank system.
    # Re-FA rules are retained for compensation grade, while the eligibility clock
    # after the first FA follows the negotiated contract length.
    if s.fa_count >= 2 or s.age >= 35:
        return 'C'
    if s.fa_count == 1:
        return 'B'
    value = s.salary + int(max(0, s.career_war) * 2200) + s.fame * 120
    if value >= 105000 or (s.ovr >= 90 and s.salary >= 30000): return 'A'
    if value >= 65000 or s.ovr >= 82: return 'B'
    return 'C'


def fa_compensation(s, grade):
    sal=s.salary
    if grade=='A': return {'cash':sal*2,'player':True,'protected':20,'summary':f'직전 연봉 200% + 보호선수 20명 외 보상선수 1명'}
    if grade=='B': return {'cash':sal,'player':True,'protected':25,'summary':f'직전 연봉 100% + 보호선수 25명 외 보상선수 1명'}
    return {'cash':int(sal*1.5),'player':False,'protected':0,'summary':f'직전 연봉 150% 금전 보상(보상선수 없음)'}


def generate_fa_offer(s):
    grade=calculate_fa_grade(s)
    teams=[x for x in KBO_TEAMS if x[0]!=s.team_id]
    random.shuffle(teams)
    count=random.randint(2,4)
    offers=[]
    for tid,name in teams[:count]:
        multiplier=random.uniform(1.20,2.30) + (0.15 if grade=='A' else 0.05 if grade=='B' else 0)
        years=random.choice([2,3,4]) if s.age<34 else random.choice([1,2,3])
        offers.append({'team_id':tid,'name':name,'salary':int(max(3000,s.salary*multiplier)),'years':years,'role':random.choice(['주전','핵심 전력','베테랑 리더'])})
    # original club always gets a retention option
    offers.append({'team_id':s.team_id,'name':s.team_name,'salary':int(max(3000,s.salary*random.uniform(1.15,2.05))),'years':random.choice([2,3,4]),'role':'핵심 전력','original':True})
    offers.sort(key=lambda x:x['salary'], reverse=True)
    s.fa_grade=grade; s.fa_compensation=fa_compensation(s,grade); s.fa_offer={'offers':offers}; s.fa_negotiation_round=1
    return offers


def negotiate_fa(s, team_id=None, counter=False):
    if not s.fa_offer: generate_fa_offer(s)
    offers=s.fa_offer['offers']
    offer=next((o for o in offers if o['team_id']==team_id), offers[0])
    if counter and s.fa_negotiation_round<3:
        bump=1.09 if s.agent=='kang' else 1.07 if s.agent=='han' else 1.04
        offer['salary']=int(offer['salary']*bump); s.fa_negotiation_round+=1
        return False, offer
    s.fa_signed_this_cycle=True
    s.office_done=True
    s.fa_count+=1; s.fa_eligible=False; s.service_seasons=0
    # First FA uses the initial 8-season requirement. Every later FA uses the
    # number of years just negotiated in the previous FA contract.
    s.fa_service_target=max(1,int(offer.get('years',1)))
    old=s.team_name
    s.team_id=offer['team_id']; s.team_name=offer['name']; s.salary=offer['salary']; s.contract_years_left=offer['years']; s.contract_total=s.salary*offer['years']
    s.contract_history.append({'year':s.year,'team':s.team_name,'type':f"FA {s.fa_grade}등급",'years':offer['years'],'total':s.contract_total,'compensation':s.fa_compensation['summary']})
    if old!=s.team_name:
        s.team_history.append({'year':s.year,'from':old,'to':s.team_name,'type':f"FA {s.fa_grade}등급 이적"})
        s.loyalty=max(0,s.loyalty-10)
    s.notes.append(f"{s.year} FA {s.fa_grade}등급 계약: {s.team_name} {offer['years']}년")
    s.fa_offer=None
    return True, offer


def _mlb_salary_range(s):
    # 연봉 단위는 게임 전체에서 '만원'으로 통일한다.
    # KBO 연봉을 단순 배수로 환산하면 저연봉 선수의 MLB 연봉이 지나치게 낮아지고,
    # 반대로 고연봉 KBO 선수는 과도하게 높아지는 문제가 있어 OVR/성과 기반으로 산정한다.
    ovr=int(s.ovr)
    war=max(0.0, float((s.season_stats[-1] if s.season_stats else {}).get('war', 0)))
    if ovr >= 96: low, high = 140000, 280000   # $10M~20M
    elif ovr >= 92: low, high = 85000, 180000  # $6M~13M
    elif ovr >= 88: low, high = 50000, 110000  # $3.5M~8M
    elif ovr >= 84: low, high = 28000, 65000   # $2M~4.6M
    elif ovr >= 80: low, high = 16000, 38000   # $1.1M~2.7M
    else: low, high = 10000, 22000             # $0.7M~1.6M
    performance=max(0.0,min(1.0, war/8.0))
    mid=low+(high-low)*(0.35+0.65*performance)
    return int(max(low, min(high, mid*random.uniform(.88,1.12))))

def generate_posting_offers(s):
    mlb_base=_mlb_salary_range(s)
    return [
        {'team':'MLB 구단 A','level':'MLB 26인 경쟁','salary':int(mlb_base*random.uniform(1.00,1.18)),'years':random.choice([2,3,4])},
        {'team':'MLB 구단 B','level':'MLB/AAA 경쟁','salary':int(mlb_base*random.uniform(.78,1.02)),'years':random.choice([2,3])},
        {'team':'AAA 구단 C','level':'AAA 주전','salary':int(max(5500,mlb_base*random.uniform(.28,.48))),'years':1},
    ]

def generate_kbo_return_offers(s):
    pool=[x for x in KBO_TEAMS if x[0] != s.team_id]
    random.shuffle(pool)
    count=min(4,len(pool))
    offers=[]
    base=max(3000,int(s.salary*.65))
    for tid,name in pool[:count]:
        mult=random.uniform(.85,1.35) + (0.10 if s.ovr>=85 else 0)
        offers.append({'team_id':tid,'name':name,'salary':max(3000,int(base*mult)),
                       'years':random.choice([1,2,3]),
                       'role':random.choice(['주전 경쟁','주전','핵심 전력'])})
    offers.append({'team_id':'RETURN_CURRENT','name':'기존 KBO 구단과 재협상','salary':max(3000,int(base*random.uniform(.9,1.2))),
                   'years':2,'role':'안정적인 복귀'})
    return offers

# =========================================================
# 연도별 환경형 선택지 시스템
# 각 카테고리 100개(25개 상황 × 4개 대응)를 미리 보유하고,
# 나이/컨디션/성적/가족/계약 상황에 맞는 후보 중 4개만 노출한다.
# =========================================================
TRAINING_BANK = []
LIFE_BANK = []
OFFICE_BANK = []

def _build_choice_bank(bank, prefix, situations, styles):
    n=1
    for situation in situations:
        for style in styles:
            label, desc, effects, tags = style
            bank.append({'id':f'{prefix}{n:03d}', 'label':f'{situation[0]} — {label}',
                         'desc':f'{situation[1]} {desc}', 'effects':dict(effects), 'tags':list(situation[2])+list(tags)})
            n+=1

_training_situations=[
 ('비시즌 개인훈련 제안','코치가 다음 시즌을 대비한 계획을 제시했다.',['young','normal']),
 ('최근 타격폼 점검','영상 분석에서 작은 문제점이 발견됐다.',['hitter','normal']),
 ('최근 구속 하락','불펜에서 평소보다 구속이 떨어졌다.',['pitcher','normal']),
 ('체력 저하','시즌 막판 피로가 누적됐다.',['tired']),
 ('베테랑의 루틴 공유','선배가 자신의 훈련 루틴을 알려줬다.',['veteran']),
 ('데이터팀의 분석','구단 데이터팀이 약점을 분석해 왔다.',['normal']),
 ('2군 훈련 제안','코치가 짧은 기간 집중훈련을 권했다.',['young','normal']),
 ('웨이트 프로그램 변경','트레이너가 새로운 프로그램을 제안했다.',['normal']),
 ('수비 실책 증가','최근 수비에서 실수가 조금 늘었다.',['fielder']),
 ('주루 훈련 강화','주루코치가 스타트를 교정하자고 했다.',['fielder']),
 ('투구폼 수정','투수코치가 팔 각도 수정을 제안했다.',['pitcher']),
 ('변화구 연마','새 구종을 연습할 기회가 생겼다.',['pitcher']),
 ('컨택 훈련','타격코치가 배트 컨트롤 훈련을 제안했다.',['hitter']),
 ('장타력 강화','파워를 늘리는 특화훈련을 제안받았다.',['hitter']),
 ('회복 프로그램','재활 트레이너가 회복 루틴을 추천했다.',['tired','normal']),
 ('해외 캠프','스프링캠프에서 추가 훈련 기회가 생겼다.',['normal']),
 ('새 장비 테스트','새 장비를 사용한 훈련이 가능해졌다.',['normal']),
 ('개인 코치 영입','비시즌에 개인 코치를 둘 수 있다.',['normal']),
 ('멘탈 코칭','스포츠 심리상담 프로그램을 권유받았다.',['normal']),
 ('훈련량 논쟁','훈련량을 늘릴지 줄일지 의견이 갈렸다.',['tired','normal']),
 ('포지션 전환 훈련','다른 포지션 적응 훈련 기회가 생겼다.',['fielder','young']),
 ('구속 회복 루틴','트레이너가 어깨 관리 루틴을 제시했다.',['pitcher','tired']),
 ('장거리 이동 후 훈련','원정 후 회복과 훈련 중 하나를 우선해야 한다.',['tired']),
 ('신인 시절 복기','코치가 과거의 문제를 다시 점검하자고 했다.',['normal']),
 ('전성기 유지 계획','전성기 선수에게 맞춘 유지 프로그램이 나왔다.',['veteran','normal']),
]
_training_styles=[
 ('공격적으로 밀어붙인다','성장을 우선한다.',{'ovr':1,'stamina':-10},['aggressive']),
 ('데이터대로 조정한다','효율과 안정성을 우선한다.',{'ovr':1,'stamina':-4},['balanced']),
 ('몸부터 관리한다','회복과 부상 방지를 우선한다.',{'stamina':9},['recovery']),
 ('새로운 방법을 시험한다','성공하면 큰 도움이 되지만 변수가 있다.',{'ovr':0,'stamina':-6,'reputation':1},['risk'])
]
_build_choice_bank(TRAINING_BANK,'T',_training_situations,_training_styles)

_life_situations=[
 ('구단 휴식일','하루의 시간을 어떻게 보낼지 정해야 한다.',['normal']),('가족의 연락','가족이 오랜만에 함께 시간을 보내자고 했다.',['family']),('친구의 초대','오랜 친구가 식사 자리를 제안했다.',['normal']),('팬들의 관심','팬들이 개인적인 만남을 요청하고 있다.',['fame']),('SNS 화제','최근 게시물이 예상보다 크게 퍼졌다.',['fame']),
 ('광고 제안','짧은 광고 촬영 제안이 들어왔다.',['fame','money']),('지역 행사','지역 유소년 행사에 초청받았다.',['family','fame']),('비시즌 여행','짧은 여행을 떠날 기회가 생겼다.',['normal']),('집 정리','생활 환경을 바꿀 시기가 됐다.',['money','family']),('차량 교체','차량을 바꿀지 고민하고 있다.',['money']),
 ('재정 상담','재무 전문가가 상담을 제안했다.',['money']),('투자 기회','새로운 투자 정보를 받았다.',['money','risk']),('저축 계획','에이전트가 장기 저축을 권했다.',['money']),('취미 생활','오프시즌에 새로운 취미를 시작할 수 있다.',['normal']),('팬미팅','소규모 팬미팅 일정이 잡혔다.',['fame']),
 ('방송 출연','예능 프로그램 출연 요청이 왔다.',['fame']),('인터뷰 요청','긴 인터뷰를 할지 짧게 끝낼지 선택해야 한다.',['fame']),('선배의 식사 초대','선배가 후배들과 함께 식사하자고 했다.',['veteran']),('후배의 부탁','후배가 개인적인 조언을 구했다.',['veteran']),('연애 중 데이트','파트너와 시간을 보낼 기회가 생겼다.',['relationship']),
 ('약혼 준비','결혼 준비와 시즌 준비가 겹쳤다.',['relationship']),('배우자의 걱정','배우자가 최근 생활 패턴을 걱정한다.',['relationship','family']),('자녀와의 약속','아이와 보내기로 한 시간이 경기 일정과 겹쳤다.',['relationship','family']),('원정 후 가족 시간','긴 원정 뒤 가족이 기다리고 있다.',['family','tired']),('은퇴 후 준비','장기적으로 어떤 삶을 준비할지 고민한다.',['veteran','money']),
]
_life_styles=[
 ('가족에게 투자한다','관계와 휴식을 우선한다.',{'family':8,'stamina':4},['family']),
 ('커리어를 선택한다','현재의 기회를 우선한다.',{'ovr':1,'fame':2,'family':-4},['career']),
 ('재정적으로 움직인다','장기 자산을 늘리는 쪽을 택한다.',{'money':1800,'asset_value':900,'spending':300},['money']),
 ('조용히 쉰다','사람들의 시선에서 벗어나 재충전한다.',{'stamina':10,'fame':-1},['rest'])
]
_build_choice_bank(LIFE_BANK,'L',_life_situations,_life_styles)

_office_situations=[
 ('연봉 협상','현재 성적을 바탕으로 구단과 협상할 수 있다.',['contract']),('주전 보장','감독이 다음 시즌 역할에 대한 의견을 묻는다.',['manager']),('구단 잔류','단장이 장기적으로 함께하자고 제안한다.',['gm']),('트레이드 소문','다른 구단의 관심이 있다는 소문이 돈다.',['gm']),('FA 시장 탐색','에이전트가 시장 상황을 정리했다.',['agent','contract']),
 ('해외 관심','해외 구단 스카우트가 경기를 지켜보고 있다.',['agent','overseas']),('광고 계약','새 스폰서가 계약을 제안했다.',['agent','money']),('팬 인기 상승','최근 활약으로 인기가 크게 올랐다.',['manager','fame']),('부진 이후 면담','감독과 최근 성적을 이야기해야 한다.',['manager']),('후배 육성','감독이 후배에게 조언해 달라고 요청했다.',['manager']),
 ('선수단 투표','선수단에서 리더 역할을 맡길지 의견을 묻는다.',['manager','veteran']),('주장 후보','구단이 차기 주장 후보를 검토하고 있다.',['manager','veteran']),('2군행 위기','최근 출전 감소로 보직이 흔들리고 있다.',['manager']),('포지션 경쟁','유망주가 같은 포지션에 합류했다.',['manager','young']),('장기계약 제안','구단이 다년계약 가능성을 타진했다.',['contract','gm']),
 ('에이전트 변경 고민','현재 에이전트와 방향이 달라지고 있다.',['agent']),('계약 만료 임박','계약 만료가 가까워졌다.',['contract']),('팀 리빌딩','구단이 젊은 선수 중심으로 팀을 바꾸고 있다.',['gm']),('우승 도전','구단이 당장 우승을 노리고 있다.',['gm','manager']),('베테랑 역할','젊은 선수들을 이끌어 달라는 요청을 받았다.',['veteran','manager']),
 ('국가대표 차출','대표팀과 구단 일정 조율이 필요하다.',['national','manager']),('포스팅 고민','해외 도전을 구체적으로 검토할 시점이다.',['overseas','agent']),('FA 잔류 고민','원소속팀과 다른 팀의 조건을 비교한다.',['contract','gm']),('은퇴 후 진로','구단이 지도자 역할을 제안할 수 있다.',['veteran','gm']),('구단 홍보대사','은퇴를 앞두고 구단과 관계가 깊어지고 있다.',['veteran','fame']),
]
_office_styles=[
 ('강하게 요구한다','조건과 역할을 적극적으로 주장한다.',{'salary_pct':0.07,'agent_trust':2,'reputation':-1},['aggressive']),
 ('관계를 우선한다','구단과 감독의 신뢰를 지킨다.',{'loyalty':7,'reputation':4,'agent_trust':2},['loyal']),
 ('에이전트에게 맡긴다','시장 가치와 장기적인 선택을 맡긴다.',{'agent_trust':7,'salary_pct':0.04},['agent']),
 ('새로운 도전을 택한다','이적·해외·새 역할의 가능성을 열어 둔다.',{'fame':3,'loyalty':-5,'reputation':1},['risk']),
]
_build_choice_bank(OFFICE_BANK,'O',_office_situations,_office_styles)

# 100개씩 생성됐는지 보장
assert len(TRAINING_BANK)==100 and len(LIFE_BANK)==100 and len(OFFICE_BANK)==100
# 에이전트 / 단장 / 감독도 각각 100개 후보를 보유한다. 실제 화면에서는
# 현재 상황에 맞는 세 역할의 후보를 합쳐 4개만 보여준다.
AGENT_BANK=[dict(x, id=f'A{x["id"][1:]}', label='에이전트 · '+x['label']) for x in OFFICE_BANK]
GM_BANK=[dict(x, id=f'G{x["id"][1:]}', label='단장 · '+x['label']) for x in OFFICE_BANK]
MANAGER_BANK=[dict(x, id=f'M{x["id"][1:]}', label='감독 · '+x['label']) for x in OFFICE_BANK]
assert len(AGENT_BANK)==100 and len(GM_BANK)==100 and len(MANAGER_BANK)==100

def _eligible_dynamic(s, bank, category):
    # 포지션/나이/상태에 따라 너무 어색한 선택을 제거하고, 환경 태그가 맞는 것을 우선한다.
    out=[]
    for x in bank:
        tags=set(x.get('tags',[]))
        if 'hitter' in tags and s.position in ('SP','RP'): continue
        if 'pitcher' in tags and s.position not in ('SP','RP'): continue
        if 'young' in tags and s.age>31 and random.random()<.75: continue
        if 'veteran' in tags and s.age<27 and random.random()<.75: continue
        if 'family' in tags and s.family<25 and random.random()<.35: continue
        if 'relationship' in tags and s.relationship_status=='none': continue
        if 'overseas' in tags and s.age<23: continue
        if 'contract' in tags and s.contract_years_left>2 and random.random()<.70: continue
        if 'national' in tags and s.age<20: continue
        if 'money' in tags and s.money<1000 and random.random()<.30: continue
        if 'recovery' in tags and s.stamina>88 and random.random()<.65: continue
        if 'tired' in tags and s.stamina>80 and random.random()<.55: continue
        if 'fame' in tags and s.fame<15 and random.random()<.25: continue
        out.append(x)
    random.shuffle(out)
    # 카테고리마다 성격이 다른 4개가 나오도록 앞쪽에서 최대한 style 다양성 확보
    chosen=[]; seen=[]
    for x in out:
        style=x['id'][-3:]
        if style not in seen or len(chosen)<2:
            chosen.append(x); seen.append(style)
        if len(chosen)>=4: break
    if len(chosen)<4:
        for x in out:
            if x not in chosen: chosen.append(x)
            if len(chosen)>=4: break
    return chosen[:4]

def dynamic_choices(s, category, refresh=False):
    key=str(category)
    if not refresh and s.dynamic_choices.get(key):
        return s.dynamic_choices[key]
    bank={'training':TRAINING_BANK,'life':LIFE_BANK,'office':AGENT_BANK+GM_BANK+MANAGER_BANK}[key]
    choices=_eligible_dynamic(s,bank,key)
    s.dynamic_choices[key]=choices
    return choices

def _apply_dynamic_effects(s, choice):
    e=choice.get('effects',{}) if choice else {}
    if 'ovr' in e: s.ovr=max(40,min(99,s.ovr+int(e['ovr'])))
    if 'stamina' in e: s.stamina=max(20,min(100,s.stamina+int(e['stamina'])))
    if 'family' in e: s.family=max(0,min(100,s.family+int(e['family'])))
    if 'fame' in e: s.fame=max(0,min(100,s.fame+int(e['fame'])))
    if 'reputation' in e: s.reputation=max(0,min(100,s.reputation+int(e['reputation'])))
    if 'loyalty' in e: s.loyalty=max(0,min(100,s.loyalty+int(e['loyalty'])))
    if 'agent_trust' in e: s.agent_trust=max(0,min(100,s.agent_trust+int(e['agent_trust'])))
    if 'money' in e: s.money=max(0,s.money+int(e['money']))
    if 'asset_value' in e: s.asset_value=max(0,s.asset_value+int(e['asset_value']))
    if 'spending' in e: s.spending=max(0,s.spending+int(e['spending']))
    if 'salary_pct' in e: s.salary=max(3000,int(s.salary*(1+float(e['salary_pct']))))

def apply_training(s, choice):
    selected=next((x for x in s.dynamic_choices.get('training',[]) if x['id']==choice),None)
    if selected: _apply_dynamic_effects(s,selected)
    else:
        # legacy choices 호환
        if choice=='bat': s.ovr=min(99,s.ovr+random.choice([0,1,1,2])); s.stamina-=7
        elif choice=='def': s.ovr=min(99,s.ovr+random.choice([0,1,1])); s.stamina-=4
        elif choice=='strength': s.ovr=min(99,s.ovr+random.choice([0,1,2])); s.stamina-=12
        else: s.stamina=min(100,s.stamina+15)
    s.stamina=max(25,s.stamina); s.training_done=True
    s.notes.append(f'{s.year} 훈련 선택: {selected["label"] if selected else choice}')

def _partner_pool():
    return ['서연','민지','지우','수빈','하린','예린','채원','다은','유나','소연']

def apply_life(s, choice):
    selected=next((x for x in s.dynamic_choices.get('life',[]) if x['id']==choice),None)
    if selected:
        _apply_dynamic_effects(s,selected)
        if 'relationship' in selected.get('tags',[]) and s.relationship_status!='none':
            s.relationship_years += 1
        s.family_notes.append(f'{s.year} 생활 선택: {selected["label"]}')
    elif choice=='family':
        s.family=min(100,s.family+10); s.stamina=min(100,s.stamina+5); s.fame=max(0,s.fame-1)
    elif choice=='media':
        s.fame=min(100,s.fame+7); s.family=max(0,s.family-3)
    elif choice=='rest': s.stamina=min(100,s.stamina+12)
    elif choice=='invest':
        gain=random.randint(500,2500); s.money+=gain; s.asset_value+=gain; s.family=max(0,s.family-2)
    elif choice=='car' and s.money>=8000:
        s.money-=8000; s.spending+=8000; s.assets.append(f'{s.year} 차량'); s.asset_value+=8000; s.fame=min(100,s.fame+2)
    elif choice=='home' and s.money>=30000:
        s.money-=30000; s.spending+=30000; s.assets.append(f'{s.year} 주거 자산'); s.asset_value+=30000; s.family=min(100,s.family+8)
    elif choice=='sponsor_spend' and s.money>=3000:
        s.money-=3000; s.spending+=3000; s.fame=min(100,s.fame+3); s.reputation=min(100,s.reputation+2)
    elif choice=='meet' and s.relationship_status=='none' and s.age>=21:
        s.partner_name=random.choice(_partner_pool()); s.relationship_status='meeting'; s.relationship_years=0; s.family=min(100,s.family+2); s.family_notes.append(f'{s.year} 새로운 인연을 만났다: {s.partner_name}')
    elif choice=='date' and s.relationship_status in ('meeting','dating'):
        s.relationship_status='dating'; s.relationship_years+=1; s.family=min(100,s.family+4); s.family_notes.append(f'{s.year} {s.partner_name}와 교제를 이어갔다.')
    elif choice=='serious' and s.relationship_status=='dating':
        s.relationship_status='serious'; s.relationship_years+=1; s.family=min(100,s.family+6); s.family_notes.append(f'{s.year} {s.partner_name}와 진지한 관계로 발전했다.')
    elif choice=='propose' and s.relationship_status=='serious':
        if random.random()<.86: s.relationship_status='engaged'; s.engagement_year=s.year; s.family=min(100,s.family+8); s.family_notes.append(f'{s.year} {s.partner_name}에게 프로포즈했고 약혼했다.')
        else: s.relationship_status='dating'; s.family=max(0,s.family-4); s.family_notes.append(f'{s.year} 프로포즈가 받아들여지지 않았다.')
    elif choice=='marry' and s.relationship_status=='engaged':
        s.spouse=True; s.relationship_status='married'; s.family=min(100,s.family+15); s.family_notes.append(f'{s.year} {s.partner_name}와 결혼했다.')
    s.life_done=True

def family_choices(s):
    # 새 100개 선택지가 중심이고, 연애/결혼 단계가 진행 중이면 기존 관계 버튼도 추가한다.
    out=dynamic_choices(s,'life')
    if s.age>=21 and s.relationship_status=='none': out=out[:3]+[{'id':'meet','label':'새로운 인연 만나기','desc':'소개·모임·우연한 만남으로 관계를 시작한다.','effects':{},'tags':['relationship']}]
    elif s.relationship_status=='meeting': out=out[:3]+[{'id':'date','label':'데이트를 이어간다','desc':'서로 알아가는 시간을 보낸다.','effects':{},'tags':['relationship']}]
    elif s.relationship_status=='dating': out=out[:3]+[{'id':'serious','label':'진지한 관계로 발전한다','desc':'결혼을 생각할 정도로 관계를 깊게 만든다.','effects':{},'tags':['relationship']}]
    elif s.relationship_status=='serious': out=out[:3]+[{'id':'propose','label':'프로포즈한다','desc':'약혼을 제안한다.','effects':{},'tags':['relationship']}]
    elif s.relationship_status=='engaged': out=out[:3]+[{'id':'marry','label':'결혼식을 올린다','desc':'약혼을 마치고 결혼한다.','effects':{},'tags':['relationship']}]
    return out[:4]

def office_choices(s):
    return dynamic_choices(s,'office')

def apply_dynamic_office(s, choice):
    selected=next((x for x in s.dynamic_choices.get('office',[]) if x['id']==choice),None)
    if selected:
        _apply_dynamic_effects(s,selected)
        s.notes.append(f'{s.year} 구단/에이전트 선택: {selected["label"]}')
    else:
        apply_office(s,choice)
    s.office_done=True


def career_stage(age):
    if age<=20: return '신인'
    if age<=24: return '주전 경쟁'
    if age<=29: return '전성기'
    if age<=34: return '베테랑'
    return '황혼기'

def random_event(s):
    pool=[]
    if s.age<=24:
        pool += [
            {'title':'감독의 기대','text':'감독이 다음 시즌 주전 경쟁을 예고했습니다.','choices':[('focus','주전 경쟁에 집중','OVR +1'),('rest','몸 관리 우선','컨디션 +8')]},
            {'title':'선배의 조언','text':'베테랑 선수가 타격/투구 루틴을 알려줬습니다.','choices':[('learn','배운다','평판 +3 / OVR +1'),('decline','내 방식 유지','컨디션 +3')]},
            {'title':'첫 팬미팅','text':'팬들이 작은 팬미팅을 열어 달라고 요청했습니다.','choices':[('media','팬들과 만난다','인지도 +6 / 가족 -1'),('skip','훈련을 택한다','OVR +1 / 컨디션 +2')]}]
    if s.age>=22:
        pool += [
            {'title':'룸메이트 갈등','text':'선수단 안에서 사소한 갈등이 생겼습니다.','choices':[('talk','먼저 대화한다','에이전트 신뢰 +4 / 평판 +2'),('wait','시간이 해결하게 둔다','컨디션 +3')]},
            {'title':'장비 업체의 제안','text':'새 장비의 테스트 선수로 선정됐습니다.','choices':[('focus','테스트한다','OVR +1 / 인지도 +2'),('decline','익숙한 장비를 쓴다','평판 +2')]},
            {'title':'구단 SNS 화제','text':'당신의 경기 영상이 갑자기 화제가 됐습니다.','choices':[('media','적극적으로 소통한다','인지도 +8 / 컨디션 -2'),('skip','관심을 끄고 훈련한다','OVR +1')]},
            {'title':'새로운 경쟁자','text':'당신의 포지션에 유망주가 합류했습니다.','choices':[('focus','경쟁을 받아들인다','OVR +2 / 컨디션 -8'),('talk','후배를 돕는다','평판 +7 / 충성도 +3')]}]
    if s.age>=25:
        pool += [
            {'title':'장기계약 제안','text':'구단이 장기계약 가능성을 타진했습니다.','choices':[('talk','협상 테이블에 앉는다','에이전트 신뢰 +5'),('wait','FA까지 기다린다','평판 +2')]},
            {'title':'지역사회 봉사','text':'구단이 지역 유소년 야구 행사에 초대했습니다.','choices':[('family','참여한다','가족 +8 / 평판 +3'),('baseball','경기에 집중한다','OVR +1')]},
            {'title':'부진 탈출법','text':'최근 한 달간 성적이 흔들리고 있습니다.','choices':[('focus','훈련량을 늘린다','OVR +2 / 컨디션 -12'),('rest','휴식과 재정비','컨디션 +15 / OVR -1')]},
            {'title':'후배의 고민','text':'후배가 당신에게 야구와 인생에 대한 조언을 구했습니다.','choices':[('talk','시간을 내준다','평판 +6 / 가족 +2'),('skip','훈련을 우선한다','OVR +1')]},
            {'title':'광고 촬영','text':'광고 모델 제안이 들어왔습니다.','choices':[('media','촬영에 참여한다','인지도 +7 / 가족 -2'),('decline','거절하고 야구에 집중한다','OVR +1 / 평판 +2')]}]
    if s.spouse:
        pool += [
            {'title':'긴 원정과 가족','text':'가족이 긴 원정 기간을 걱정합니다.','choices':[('family','가족과 시간을 확보한다','가족 +8 / 컨디션 +3'),('baseball','야구에 집중한다','OVR +1 / 가족 -5')]},
            {'title':'배우자의 응원','text':'배우자가 슬럼프를 겪는 당신에게 진심 어린 조언을 건넸습니다.','choices':[('family','함께 시간을 보낸다','가족 +10 / 컨디션 +4'),('focus','조언을 마음에 새긴다','OVR +1 / 평판 +2')]}]
    if not pool:
        pool=[{'title':'작은 선택','text':'이번 시즌의 루틴을 정해야 합니다.','choices':[('focus','훈련 강화','OVR +1'),('rest','휴식','컨디션 +6')]}]
    return random.choice(pool)

def apply_event(s, choice):
    effects={
        'focus': lambda: setattr(s,'ovr',min(99,s.ovr+1)),
        'rest': lambda: setattr(s,'stamina',min(100,s.stamina+7)),
        'learn': lambda: (setattr(s,'ovr',min(99,s.ovr+1)), setattr(s,'reputation',min(100,s.reputation+3))),
        'decline': lambda: setattr(s,'stamina',min(100,s.stamina+3)),
        'media': lambda: (setattr(s,'fame',min(100,s.fame+6)), setattr(s,'family',max(0,s.family-2))),
        'skip': lambda: (setattr(s,'stamina',min(100,s.stamina+5)), setattr(s,'ovr',min(99,s.ovr+1))),
        'talk': lambda: setattr(s,'agent_trust',min(100,s.agent_trust+4)),
        'wait': lambda: setattr(s,'reputation',min(100,s.reputation+1)),
        'family': lambda: (setattr(s,'family',min(100,s.family+8)), setattr(s,'stamina',min(100,s.stamina+3))),
        'baseball': lambda: (setattr(s,'ovr',min(99,s.ovr+1)), setattr(s,'family',max(0,s.family-5))),
    }
    fn=effects.get(choice)
    if fn: fn()
    s.event_done=True; s.pending_event=None

def agent_options(s):
    return [
        ('ask_market','시장가치 분석','현재 FA/연봉 시장에서의 예상 가치를 확인합니다.'),
        ('negotiate','구단 협상','연봉·역할 협상에 에이전트를 투입합니다.'),
        ('overseas','해외 탐색','포스팅/MLB 관심 구단을 탐색합니다.'),
        ('relationship','구단 관계 관리','감독·단장과의 관계를 개선합니다.'),
    ]

def apply_office(s, choice):
    if choice=='ask_market': s.agent_trust=min(100,s.agent_trust+3); s.reputation=min(100,s.reputation+2)
    elif choice=='negotiate': s.salary=int(s.salary*(1+(.08 if s.agent=='kang' else .06 if s.agent=='han' else .03))); s.agent_trust=min(100,s.agent_trust+5)
    elif choice=='overseas': s.posting_eligible=s.posting_eligible or (s.age>=25 and s.ovr>=78 and s.service_seasons>=7); s.agent_trust=min(100,s.agent_trust+2)
    elif choice=='relationship': s.loyalty=min(100,s.loyalty+7)
    s.office_done=True
