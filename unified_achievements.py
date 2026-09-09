"""Account-wide achievements for non-Career modes.
Keeps the exact Career card shape: id/tier/name/desc/icon.
"""
from career_storage import unlock_custom, list_game_records

MODES = {
    'scout': ('Scout', '🔎', [
        ('첫 정찰 보고서','1회 완료','count',1),('감 잡았다','3회 완료','count',3),('유망주 사냥꾼','5회 완료','count',5),('정찰 일지','10회 완료','count',10),('첫 포디움','TOP3 1회','top3',1),
        ('최고의 안목','1위 1회','wins',1),('숨은 보석','70점 이상','best_score',70),('분석가의 시작','80점 이상','best_score',80),('정찰반장','TOP2 3회','top2',3),('스카우트 루틴','25회 완료','count',25),
        ('포디움 단골','TOP3 10회','top3',10),('발굴왕','1위 5회','wins',5),('천리안','90점 이상','best_score',90),('연속 안목','TOP3 20회','top3',20),('스카우트 베테랑','50회 완료','count',50),
        ('우승 제조기','1위 10회','wins',10),('완벽 분석','95점 이상','best_score',95),('정찰 중독','100회 완료','count',100),('상위권 전문가','TOP2 25회','top2',25),('명장 스카우터','1위 25회','wins',25),
        ('기록의 눈','100점 이상','best_score',100),('300회 정찰','300회 완료','count',300),('불패의 안목','1위 50회','wins',50),('500회 정찰','500회 완료','count',500),('전설의 스카우터','1000회 완료','count',1000)]),
    'dynasty': ('Dynasty', '👑', [
        ('첫 시즌','1시즌 완료','count',1),('프런트 데뷔','3시즌 완료','count',3),('장기 집권','5시즌 완료','count',5),('첫 가을야구','TOP3 1회','top3',1),('첫 정규 1위','1위 1회','wins',1),
        ('한국시리즈 진출','우승 1회','champion',1),('왕조의 씨앗','우승 2회','champion',2),('10년 감독','10시즌 완료','season',10),('강팀의 조건','TOP3 5회','top3',5),('우승 경쟁자','TOP2 5회','top2',5),
        ('첫 왕조','우승 3회','champion',3),('명문 구단','TOP3 10회','top3',10),('20년 집권','20시즌 완료','season',20),('연패 없는 팀','TOP2 15회','top2',15),('우승 단골','우승 5회','champion',5),
        ('30년 왕조','30시즌 완료','season',30),('가을의 지배자','TOP3 25회','top3',25),('왕조 건설자','우승 8회','champion',8),('40년 전설','40시즌 완료','season',40),('리그의 얼굴','1위 20회','wins',20),
        ('불멸의 프런트','50시즌 완료','season',50),('10회 우승','우승 10회','champion',10),('완벽한 왕조','우승 15회','champion',15),('세기의 명장','75시즌 완료','season',75),('다이너스티','우승 25회','champion',25)]),
    'trait': ('Trait', '🧬', [
        ('첫 조합','1회 완료','count',1),('특성 입문','3회 완료','count',3),('조합 연구가','5회 완료','count',5),('실험 노트','10회 완료','count',10),('첫 S급','70점 이상','best_score',70),
        ('첫 SS급','80점 이상','best_score',80),('시너지 발견','TOP3 3회','top3',3),('특성 전문가','25회 완료','count',25),('상위 조합','TOP2 10회','top2',10),('완성형','90점 이상','best_score',90),
        ('조합 마니아','50회 완료','count',50),('1위 빌드','1위 5회','wins',5),('최적화','95점 이상','best_score',95),('실험실장','100회 완료','count',100),('SS 수집가','1위 10회','wins',10),
        ('완벽한 설계','100점 이상','best_score',100),('특성 지배자','TOP3 50회','top3',50),('조합의 신','1위 25회','wins',25),('200회 실험','200회 완료','count',200),('불꽃 시너지','110점 이상','best_score',110),
        ('특성 백과사전','500회 완료','count',500),('완벽주의자','1위 50회','wins',50),('전설 조합','120점 이상','best_score',120),('끝없는 연구','1000회 완료','count',1000),('궁극의 특성','1위 100회','wins',100)]),
    'classic': ('Classic', '⚾', [
        ('첫 클래식','1회 완료','count',1),('과거로의 여행','3회 완료','count',3),('올드스쿨','5회 완료','count',5),('역사 탐험가','10회 완료','count',10),('첫 우승','1위 1회','wins',1),
        ('명경기','70점 이상','best_score',70),('클래식 강자','TOP3 5회','top3',5),('전통의 계승자','25회 완료','count',25),('첫 전설','80점 이상','best_score',80),('역사적 승리','1위 5회','wins',5),
        ('레트로 스타','50회 완료','count',50),('명예의 세대','TOP2 15회','top2',15),('불멸의 경기','90점 이상','best_score',90),('클래식 챔피언','1위 10회','wins',10),('100경기 회상','100회 완료','count',100),
        ('역사 지배자','TOP3 50회','top3',50),('시대 초월','95점 이상','best_score',95),('고전의 왕','1위 25회','wins',25),('200경기 기록','200회 완료','count',200),('영원한 명작','100점 이상','best_score',100),
        ('500경기 전설','500회 완료','count',500),('클래식 불패','1위 50회','wins',50),('시대의 전설','110점 이상','best_score',110),('천 번의 기억','1000회 완료','count',1000),('역사 그 자체','1위 100회','wins',100)]),
    'gauntlet': ('Gauntlet', '🔥', [
        ('첫 관문','1회 완료','count',1),('도전자','3회 완료','count',3),('연전의 시작','5회 완료','count',5),('10연전','10회 완료','count',10),('첫 돌파','TOP3 1회','top3',1),
        ('첫 제패','1위 1회','wins',1),('강철 멘탈','70점 이상','best_score',70),('연전 전문가','25회 완료','count',25),('벽을 넘다','80점 이상','best_score',80),('연승가도','1위 5회','wins',5),
        ('50번의 도전','50회 완료','count',50),('상위권 생존자','TOP2 20회','top2',20),('지옥의 관문','90점 이상','best_score',90),('건틀릿 챔피언','1위 10회','wins',10),('100번의 도전','100회 완료','count',100),
        ('끝없는 전투','TOP3 50회','top3',50),('강철의 손','95점 이상','best_score',95),('파괴자','1위 25회','wins',25),('200회 생존','200회 완료','count',200),('절대 돌파','100점 이상','best_score',100),
        ('500회 도전','500회 완료','count',500),('지옥의 지배자','1위 50회','wins',50),('불멸의 생존자','110점 이상','best_score',110),('천 번의 관문','1000회 완료','count',1000),('건틀릿의 신','1위 100회','wins',100)]),
    'auction': ('Auction', '💰', [
        ('첫 입찰','1회 완료','count',1),('시장 입문','3회 완료','count',3),('첫 낙찰','5회 완료','count',5),('경매 일지','10회 완료','count',10),('첫 포디움','TOP3 1회','top3',1),
        ('최고 낙찰가','1위 1회','wins',1),('가치 발견','70점 이상','best_score',70),('시장 분석가','25회 완료','count',25),('상위권 낙찰','TOP2 10회','top2',10),('대박 거래','80점 이상','best_score',80),
        ('50회 경매','50회 완료','count',50),('낙찰왕','1위 5회','wins',5),('시장 읽기','90점 이상','best_score',90),('경매 전문가','100회 완료','count',100),('승자의 가격','1위 10회','wins',10),
        ('완벽한 투자','95점 이상','best_score',95),('시장 지배자','TOP3 50회','top3',50),('경매의 왕','1위 25회','wins',25),('200회 입찰','200회 완료','count',200),('초대형 거래','100점 이상','best_score',100),
        ('500회 경매','500회 완료','count',500),('불패의 단장','1위 50회','wins',50),('전설의 감정사','110점 이상','best_score',110),('천 번의 입찰','1000회 완료','count',1000),('시장 그 자체','1위 100회','wins',100)]),
}

# Exactly 100 per mode: 25 per difficulty, using increasingly strict variants of the 25 base goals.
TIER_INFO = [('easy',0,'🟢'),('normal',1,'🔵'),('hard',2,'🟠'),('hell',3,'☠️')]
MULT = [1, 2, 5, 10]

def _scaled(kind, value, level):
    if kind in {'count','wins','top2','top3','champion'}:
        return max(value, int(value * MULT[level]))
    if kind == 'season': return value + [0,10,30,60][level]
    if kind == 'best_score': return value + [0,10,25,40][level]
    return value

def _defs():
    out={}
    for mode,(label,icon,base) in MODES.items():
        arr=[]
        for tier,level,ticon in TIER_INFO:
            for i,(name,_,kind,val) in enumerate(base,1):
                target=_scaled(kind,val,level)
                suffix=['',' II',' III',' ∞'][level]
                if kind=='count': desc=f'{label}에서 {target}회 완료하세요.'
                elif kind=='wins': desc=f'{label}에서 1위를 {target}회 달성하세요.'
                elif kind=='top2': desc=f'{label}에서 TOP2를 {target}회 달성하세요.'
                elif kind=='top3': desc=f'{label}에서 TOP3를 {target}회 달성하세요.'
                elif kind=='best_score': desc=f'{label}에서 한 번이라도 {target}점 이상 기록하세요.'
                elif kind=='champion': desc=f'{label}에서 우승을 {target}회 달성하세요.'
                elif kind=='season': desc=f'{label}에서 {target}시즌까지 운영하세요.'
                else: desc=f'{label} 특별 목표를 달성하세요.'
                arr.append({'id':f'{mode}_{tier}{i:02d}','tier':tier,'name':name+suffix,'desc':desc,'icon':ticon if level else icon,'criteria':{'kind':kind,'target':target}})
        out[mode]=arr
    return out
MODE_ACHIEVEMENTS=_defs()

def _records(account_id, mode):
    rows=list_game_records(account_id,5000) or []
    return [r for r in rows if str(r.get('mode','')).lower()==mode]

def _parse_rank(row):
    import re
    m=re.search(r'(\d+)위',str(row.get('result','')))
    return int(m.group(1)) if m else 99

def _score(row):
    try:return float(row.get('score',0) or 0)
    except:return 0.0

def unlock_mode_achievements(account_id, mode, result=None):
    if not account_id:return []
    mode=str(mode).lower()
    if mode not in MODE_ACHIEVEMENTS:return []
    result=result or {}
    rows=_records(account_id,mode)
    synthetic={'result':f"{result.get('rank',result.get('place',99))}위",'score':result.get('score',result.get('total',0))}
    all_rows=rows+[synthetic]
    ranks=[_parse_rank(r) for r in all_rows]
    scores=[_score(r) for r in all_rows]
    count=len(all_rows); wins=sum(x==1 for x in ranks); top2=sum(x<=2 for x in ranks); top3=sum(x<=3 for x in ranks)
    champions=sum(1 for r in rows if '우승' in str(r.get('result','')))+ (1 if result.get('champion') else 0)
    season=int(result.get('season',0) or 0)
    metrics={'count':count,'wins':wins,'top2':top2,'top3':top3,'champion':champions,'season':season,'best_score':max(scores or [0])}
    unlocked=[]
    for a in MODE_ACHIEVEMENTS[mode]:
        c=a.get('criteria',{}); kind=c.get('kind'); target=c.get('target',999999)
        if metrics.get(kind,0)>=target:
            unlocked.append({k:a[k] for k in ('id','name','desc','icon')})
    return unlock_custom(account_id,unlocked)

def mode_achievement_defs(mode): return MODE_ACHIEVEMENTS.get(str(mode).lower(),[])
