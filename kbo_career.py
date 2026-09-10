import random, uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime

KBO_TEAMS = [
    ('LG','LG 트윈스'),('KT','KT 위즈'),('SSG','SSG 랜더스'),('NC','NC 다이노스'),
    ('두산','두산 베어스'),('KIA','KIA 타이거즈'),('롯데','롯데 자이언츠'),('삼성','삼성 라이온즈'),
    ('한화','한화 이글스'),('키움','키움 히어로즈')
]
POSITIONS = {'C':'포수','1B':'1루수','2B':'2루수','3B':'3루수','SS':'유격수','OF':'외야수','SP':'선발투수','RP':'불펜투수'}
AGENTS = {
    'negotiator': ('협상가','💰','계약·FA 협상력이 강합니다.'),
    'overseas': ('해외통','🌎','포스팅·해외 진출 기회를 더 잘 포착합니다.'),
    'development': ('육성형','📈','훈련 효율과 슬럼프 회복이 좋습니다.'),
    'relationship': ('관계형','🤝','감독·단장과의 관계와 잔류 가능성이 좋습니다.'),
    'ambitious': ('야심가','🔥','대형 계약·이적·해외 도전을 적극적으로 노립니다.'),
}
FAMILY_TYPES = ['가족 중심','커리어 중심','균형형']

@dataclass
class KBOState:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    player_name: str = '신인'
    position: str = 'SS'
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
    agent: str = 'development'
    agent_trust: int = 60
    spouse: bool = False
    children: int = 0
    military: str = '미필'
    military_choice: str = ''
    army_years: int = 0
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
    fa_signed_this_cycle: bool = False
    fa_compensation: dict = None
    posting_stage: str = ''
    posting_offers: list = field(default_factory=list)
    manager_role: str = '2군 경쟁'
    national_offer: dict = None
    national_history: list = field(default_factory=list)


def from_dict(raw):
    s=KBOState(**{k:v for k,v in (raw or {}).items() if k in KBOState.__dataclass_fields__})
    return s

def team_name(team_id):
    return dict(KBO_TEAMS).get(team_id, team_id or '미정')

def _roll_stats(s):
    age=s.age
    role=max(0.35, min(1.18, (s.ovr-45)/35))
    health=max(.55, s.stamina/100)
    luck=random.uniform(.88,1.12)
    games=int(55+105*role*health*luck)
    if age < 21: games=int(games*.70)
    if age >= 35: games=int(games*.78)
    if s.overseas: games=int(games*.72)
    if s.position in ('SP','RP'):
        if s.position=='SP':
            wins=max(0,int(games*.55*(s.ovr/85)*luck)-random.randint(0,5))
            era=max(1.8, 5.2-(s.ovr-55)*.055+random.uniform(-.35,.35))
            war=max(-0.3, (games/28)*(4.8-era)/1.5)
            saves=0
            primary=f'{wins}승'
            secondary=f'{era:.2f} ERA'
        else:
            saves=max(0,int(games*.22*(s.ovr/85)*luck))
            era=max(1.9,5.0-(s.ovr-55)*.05+random.uniform(-.35,.35))
            war=max(-.2,(games/60)*(4.4-era)/1.1)
            wins=0
            primary=f'{saves} SV'; secondary=f'{era:.2f} ERA'
        hr=rbi=hits=0
    else:
        avg=max(.180,min(.370,.235+(s.ovr-55)*.004+random.uniform(-.025,.025)))
        hr=max(0,int((s.ovr-55)*.62+random.uniform(-5,7)))
        rbi=max(0,int(hr*2.4+games*.17+random.uniform(-8,12)))
        hits=max(0,int(games*3.0*avg))
        war=max(-0.5,(s.ovr-52)/12*games/140+random.uniform(-.7,.8))
        wins=saves=0
        primary=f'{avg:.3f}'; secondary=f'{hr} HR'
    if random.random() < max(.02,.11-(s.ovr/1200)):
        s.injuries += 1; s.stamina=max(25,s.stamina-random.randint(8,25)); games=int(games*.7)
    days=min(170,max(20,int(games*1.05+random.randint(-8,12))))
    return {'year':s.year,'age':s.age,'team':s.team_name,'games':games,'primary':primary,'secondary':secondary,'war':round(war,1),'avg':round(avg,3) if s.position not in ('SP','RP') else None,'hr':hr,'rbi':rbi,'wins':wins,'saves':saves,'era':round(era,2) if s.position in ('SP','RP') else None,'registered_days':days}

def simulate_season(s):
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
    if s.agent=='development' and s.age<=27: delta += random.choice([0,0,1])
    if s.age>=32 and s.position in ('SP','RP'): delta -= 1
    if s.injuries and random.random()<.3: delta -= 1
    s.ovr=max(40,min(99,s.ovr+delta))
    s.potential=max(s.ovr,min(99,s.potential))
    if st['games'] >= 120 and st['war'] >= 3: s.manager_role=random.choice(['주전','핵심 주전','팀의 중심'])
    elif st['games'] >= 70: s.manager_role=random.choice(['플래툰/로테이션','주전 경쟁','백업'])
    else: s.manager_role=random.choice(['2군 경쟁','백업','재활/회복'])
    s.stamina=max(45,min(100,s.stamina+random.randint(-4,7)))
    # FA eligibility: current KBO framework uses 145-day qualifying seasons; high-school 8, college 7.
    target=7 if s.school=='college' else 8
    s.fa_eligible=s.service_seasons>=target and not s.overseas
    s.posting_eligible=(s.age>=25 and s.ovr>=78 and s.service_seasons>=4 and not s.overseas)
    # salary growth
    if s.contract_years_left>0: s.contract_years_left-=1
    if s.contract_years_left<=0 and not s.fa_eligible:
        s.salary=max(3300 if s.year>=2027 else 3000,int(s.salary*(1+max(-.15,min(.35,st['war']/25+random.uniform(-.08,.08))))))
        s.contract_years_left=1
    return st

def age_up(s):
    s.year+=1; s.age+=1; s.training_done=s.life_done=s.office_done=False; s.stage='dashboard'
    if s.age>=41: s.retired=True

def draft_offers(s):
    teams=list(KBO_TEAMS); random.shuffle(teams)
    n=5 if s.ovr>=60 else 4
    return [{'team_id':tid,'name':name,'round':i+1,'signing_bonus':max(3000,int((s.ovr-45)*900+random.randint(-1000,2000)))} for i,(tid,name) in enumerate(teams[:n])]


def calculate_fa_grade(s):
    # Game approximation of the current KBO A/B/C salary-rank system.
    # Re-FA rules: 2nd FA = B baseline, 3rd+ = C baseline; new FA age 35+ = C.
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
        bump=1.08 if s.agent=='negotiator' else 1.04
        offer['salary']=int(offer['salary']*bump); s.fa_negotiation_round+=1
        return False, offer
    s.fa_signed_this_cycle=True
    s.office_done=True
    s.fa_count+=1; s.fa_eligible=False; s.service_seasons=0
    old=s.team_name
    s.team_id=offer['team_id']; s.team_name=offer['name']; s.salary=offer['salary']; s.contract_years_left=offer['years']; s.contract_total=s.salary*offer['years']
    s.contract_history.append({'year':s.year,'team':s.team_name,'type':f"FA {s.fa_grade}등급",'years':offer['years'],'total':s.contract_total,'compensation':s.fa_compensation['summary']})
    if old!=s.team_name:
        s.team_history.append({'year':s.year,'from':old,'to':s.team_name,'type':f"FA {s.fa_grade}등급 이적"})
        s.loyalty=max(0,s.loyalty-10)
    s.notes.append(f"{s.year} FA {s.fa_grade}등급 계약: {s.team_name} {offer['years']}년")
    s.fa_offer=None
    return True, offer


def generate_posting_offers(s):
    base=max(4000,int(s.salary*2.2))
    return [
        {'team':'MLB 구단 A','level':'MLB 26인 경쟁','salary':int(base*random.uniform(1.3,2.1)),'years':3},
        {'team':'MLB 구단 B','level':'MLB/AAA 경쟁','salary':int(base*random.uniform(1.0,1.7)),'years':2},
        {'team':'AAA 구단 C','level':'AAA 주전','salary':int(base*random.uniform(.7,1.15)),'years':2},
    ]

def apply_training(s, choice):
    effects={
        'bat':'컨택/파워 집중: OVR 성장 가능성이 커집니다.',
        'def':'수비/주루 집중: 출장 안정성이 올라갑니다.',
        'strength':'웨이트: 파워/구속 잠재력이 좋아지지만 피로가 쌓입니다.',
        'recovery':'회복 훈련: 부상 위험을 낮추고 컨디션을 회복합니다.',
    }
    if choice=='bat': s.ovr=min(99,s.ovr+random.choice([0,1,1,2])); s.stamina-=7
    elif choice=='def': s.ovr=min(99,s.ovr+random.choice([0,1,1])); s.stamina-=4
    elif choice=='strength': s.ovr=min(99,s.ovr+random.choice([0,1,2])); s.stamina-=12
    else: s.stamina=min(100,s.stamina+15)
    s.stamina=max(25,s.stamina); s.training_done=True; return effects.get(choice,'')

def apply_life(s, choice):
    if choice=='family': s.family=min(100,s.family+10); s.stamina=min(100,s.stamina+5); s.fame=max(0,s.fame-1)
    elif choice=='media': s.fame=min(100,s.fame+7); s.family=max(0,s.family-3)
    elif choice=='rest': s.stamina=min(100,s.stamina+12)
    elif choice=='invest': s.money=max(0,s.money+random.randint(500,2500)); s.family=max(0,s.family-2)
    elif choice=='marry' and not s.spouse: s.spouse=True; s.family=min(100,s.family+15)
    elif choice=='child' and s.spouse and s.children<3: s.children+=1; s.family=min(100,s.family+12)
    s.life_done=True

def career_stage(age):
    if age<=20: return '신인'
    if age<=24: return '주전 경쟁'
    if age<=29: return '전성기'
    if age<=34: return '베테랑'
    return '황혼기'

def random_event(s):
    pool=[]
    if s.age<=24: pool += [
        {'title':'감독의 기대','text':'감독이 다음 시즌 주전 경쟁을 예고했습니다.','choices':[('focus','주전 경쟁에 집중','OVR +1'),('rest','몸 관리 우선','컨디션 +8')]},
        {'title':'선배의 조언','text':'베테랑 선수가 타격/투구 루틴을 알려줬습니다.','choices':[('learn','배운다','평판 +3 / OVR +1'),('decline','내 방식 유지','컨디션 +3')]}]
    if s.age>=25: pool += [
        {'title':'언론 집중','text':'최근 활약으로 인터뷰 요청이 몰렸습니다.','choices':[('media','응한다','인지도 +6 / 가족 -2'),('skip','훈련을 택한다','컨디션 +5 / OVR +1')]},
        {'title':'구단의 장기계획','text':'단장이 장기계약 가능성을 타진했습니다.','choices':[('talk','협상한다','에이전트 신뢰 +4'),('wait','FA까지 기다린다','FA 기대값 +1')]}]
    if s.spouse: pool.append({'title':'가족과 원정','text':'가족이 긴 원정 기간을 걱정합니다.','choices':[('family','가족을 우선한다','가족 +8 / 컨디션 +3'),('baseball','야구에 집중한다','OVR +1 / 가족 -5')]})
    if not pool: pool=[{'title':'작은 선택','text':'이번 시즌의 루틴을 정해야 합니다.','choices':[('focus','훈련 강화','OVR +1'),('rest','휴식','컨디션 +6')]}]
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
    elif choice=='negotiate': s.salary=int(s.salary*(1+(.08 if s.agent=='negotiator' else .03))); s.agent_trust=min(100,s.agent_trust+5)
    elif choice=='overseas': s.posting_eligible=s.posting_eligible or (s.age>=25 and s.ovr>=78); s.agent_trust=min(100,s.agent_trust+2)
    elif choice=='relationship': s.loyalty=min(100,s.loyalty+7)
    s.office_done=True
