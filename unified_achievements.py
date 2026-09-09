"""Unified account achievements for all non-Career modes.
Each mode has 100 achievements. Achievements are intentionally cumulative and
use only data already stored in game_records plus the current result payload.
"""
from career_storage import unlock_custom, list_game_records

MODE_LABELS = {
    'scout':'SCOUT', 'dynasty':'DYNASTY', 'trait':'TRAIT',
    'classic':'CLASSIC', 'gauntlet':'GAUNTLET', 'auction':'AUCTION',
    '144-0':'144-0 CHALLENGE', 'pvp':'PVP', 'draft':'DRAFT'
}

ICONS = ['🏅','🔥','⚾','🎯','👑','💎','🧠','🚀','🛡️','💥']


def _make_defs(mode):
    """Exactly 100 achievements, tuned to each mode's natural metrics."""
    label = MODE_LABELS.get(mode, mode.upper())
    defs=[]
    # 1-20: participation
    counts=[1,2,3,5,7,10,12,15,20,25,30,35,40,50,60,70,80,90,100,120]
    for i,n in enumerate(counts,1):
        defs.append({'id':f'{mode}_play_{i:02d}','name':f'{label} {n}회','desc':f'{label}을 총 {n}회 완료하세요.','icon':ICONS[i%10],'kind':'count','value':n})

    # 21-40: mode-specific cumulative progression
    progress={
      'scout':[25,40,55,70,85,100,120,140,160,180,200,225,250,275,300,325,350,400,450,500],
      'auction':[20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100,110,120,150],
      'dynasty':[1,2,3,4,5,6,7,8,10,12,15,18,20,25,30,35,40,50,60,75],
      'gauntlet':[1,2,3,4,5,6,7,8,10,12,15,18,20,25,30,35,40,50,60,75],
      'trait':[50,60,70,80,85,90,95,100,105,110,115,120,125,130,135,140,141,142,143,144],
      'classic':[50,60,70,80,85,90,95,100,105,110,115,120,125,130,135,140,141,142,143,144],
    }[mode]
    progress_names={
      'scout':'발굴 점수','auction':'경매 점수','dynasty':'시즌 수','gauntlet':'총 승수','trait':'승수','classic':'승수'
    }
    for i,n in enumerate(progress,21):
        defs.append({'id':f'{mode}_progress_{i:02d}','name':f'{label} {progress_names[mode]} {n}','desc':f'{label}에서 {progress_names[mode]} {n} 이상을 달성하세요.','icon':ICONS[i%10],'kind':'progress','value':n})

    # 41-60: rank/grade/performance
    excellence=[
      ('S 등급','grade','S'),('A 등급','grade','A'),('B 등급','grade','B'),('1위','rank',1),('2위 이내','rank',2),('3위 이내','rank',3),
      ('5위 이내','rank',5),('10위 이내','rank',10),('우승','champion',1),('무패','unbeaten',1),
      ('최고 기록 1회','pb',1),('최고 기록 3회','pb_count',3),('최고 기록 5회','pb_count',5),('상위권 5회','top_count',5),('상위권 10회','top_count',10),
      ('1위 3회','win_count',3),('1위 5회','win_count',5),('1위 10회','win_count',10),('S급 3회','s_count',3),('S급 5회','s_count',5)
    ]
    for i,(title,kind,val) in enumerate(excellence,41):
        defs.append({'id':f'{mode}_elite_{i:02d}','name':f'{label} · {title}','desc':f'{label}에서 {title}을 달성하세요.','icon':ICONS[i%10],'kind':kind,'value':val})

    # 61-80: longevity / cumulative milestones
    longevity=[
      ('누적 5회','count',5),('누적 10회','count',10),('누적 15회','count',15),('누적 20회','count',20),('누적 30회','count',30),
      ('누적 40회','count',40),('누적 50회','count',50),('누적 60회','count',60),('누적 75회','count',75),('누적 100회','count',100),
      ('상위권 비율 25%','top_ratio',.25),('상위권 비율 40%','top_ratio',.40),('상위권 비율 50%','top_ratio',.50),('1위 비율 10%','win_ratio',.10),('1위 비율 20%','win_ratio',.20),
      ('최고 기록 갱신 5회','pb_count',5),('최고 기록 갱신 10회','pb_count',10),('S급 10회','s_count',10),('상위권 25회','top_count',25),('1위 25회','win_count',25)
    ]
    for i,(title,kind,val) in enumerate(longevity,61):
        defs.append({'id':f'{mode}_long_{i:02d}','name':f'{label} · {title}','desc':f'{label}에서 누적 기록으로 {title}을 달성하세요.','icon':ICONS[i%10],'kind':kind,'value':val})

    # 81-100: flavor titles; these are difficult composite milestones.
    flavor=['첫 발자국','감각을 깨우다','한계 돌파','두 번째 전성기','꾸준함의 증명','정상을 노리다','정상에 서다','기록 사냥꾼','완벽주의자','야구 박사',
             '판을 읽는 자','결정적 한 수','숨은 강자','고수의 영역','극한 적응','철인 도전','불가능에 도전','전설의 발자취','명예의 전당','마지막 시험']
    for i,title in enumerate(flavor,81):
        defs.append({'id':f'{mode}_special_{i:03d}','name':f'{label} · {title}','desc':f'{label}에서 플레이 {i-80}단계의 누적 성과와 고점 기록을 만족하세요.','icon':ICONS[i%10],'kind':'special','value':i-80})
    return defs


MODE_ACHIEVEMENTS = {m:_make_defs(m) for m in ['scout','dynasty','trait','classic','gauntlet','auction']}
ALL_MODE_ACHIEVEMENTS = [a for m in MODE_ACHIEVEMENTS.values() for a in m]


def _records(account_id, mode=None):
    rows = list_game_records(account_id, 1000)
    if mode:
        rows = [r for r in rows if str(r.get('mode','')).lower() == mode.lower()]
    return rows


def _num(v, default=0):
    try: return float(v)
    except Exception: return default


def _rank(r):
    try: return int(r.get('rank', r.get('place', 99)) or 99)
    except Exception: return 99


def _score(r):
    return _num(r.get('score', r.get('total', 0)))


def _is_top(r): return _rank(r) <= 3


def _special_ok(mode, result, rows, count, best):
    text = str(result.get('result','')).lower()
    grade = str(result.get('grade','')).upper()
    rank = _rank(result)
    if result.get('champion') or '우승' in text or 'champion' in text: return True
    if result.get('perfect') or result.get('comeback') or result.get('extreme') or result.get('streak'): return True
    if mode == 'dynasty' and (result.get('season',0) >= 10 or rank == 1): return True
    if mode == 'gauntlet' and (result.get('finished') or result.get('stage',0) >= 5): return True
    if mode in ('classic','trait') and (result.get('wins',0) >= 100 or grade in ('SS','S')): return True
    if mode == 'scout' and (grade == 'S' or rank == 1): return True
    if mode == 'auction' and (grade == 'S' or rank == 1): return True
    return count >= 80 and best >= 500


def unlock_mode_achievements(account_id, mode, result=None):
    if not account_id or mode not in MODE_ACHIEVEMENTS:
        return []
    result=result or {}
    rows=_records(account_id, mode)
    current_score=_score(result)
    # game record is normally written immediately before this call
    already_current = bool(rows and _score(rows[0]) == current_score and str(rows[0].get('result','')) == str(result.get('result','')))
    count=len(rows) if already_current else len(rows)+1
    all_rows=rows if already_current else rows+[result]
    scores=[_score(r) for r in all_rows]
    best=max(scores or [0])
    ranks=[_rank(r) for r in all_rows]
    top_count=sum(1 for r in all_rows if _rank(r)<=3)
    win_count=sum(1 for r in all_rows if _rank(r)==1 or r.get('champion') or '우승' in str(r.get('result','')) or str(r.get('result','')).upper()=='CLEAR')
    s_count=sum(1 for r in all_rows if str(r.get('grade','')).upper()=='S')
    # A record may encode wins directly (Classic/Trait/Gauntlet) or score as the score.
    total_progress=0
    if mode in ('trait','classic'):
        total_progress=sum(int(_num(r.get('wins', _score(r)))) for r in all_rows)
    elif mode=='dynasty':
        total_progress=sum(int(_num(r.get('season',0))) for r in all_rows)
        total_progress=max(total_progress, max([int(_num(result.get('season',0)))] + [0]))
    elif mode=='gauntlet':
        total_progress=sum(int(_num(r.get('wins',_score(r)))) for r in all_rows)
        total_progress=max(total_progress, int(_num(result.get('wins',0))))
    else:
        total_progress=int(sum(scores))
    top_ratio=top_count/max(1,count)
    win_ratio=win_count/max(1,count)
    # approximate PB count by counting records that equal the running maximum
    running=0; pb_count=0
    for r in reversed(all_rows):
        sc=_score(r)
        if sc>=running:
            running=sc; pb_count+=1
    special_base=max(best,total_progress)
    unlocked=[]
    for a in MODE_ACHIEVEMENTS[mode]:
        k,v=a['kind'],a['value']; ok=False
        if k=='count': ok=count>=v
        elif k=='progress': ok=total_progress>=v or _score(result)>=v
        elif k=='score': ok=current_score>=v or best>=v
        elif k=='grade': ok=str(result.get('grade','')).upper()==v or any(str(r.get('grade','')).upper()==v for r in all_rows)
        elif k=='rank': ok=_rank(result)<=v or any(_rank(r)<=v for r in all_rows)
        elif k=='champion': ok=win_count>=1
        elif k=='unbeaten': ok=_num(result.get('losses',1))==0 or '무패' in str(result.get('result',''))
        elif k=='pb': ok=current_score>=best
        elif k=='pb_count': ok=pb_count>=v
        elif k=='top_count': ok=top_count>=v
        elif k=='win_count': ok=win_count>=v
        elif k=='s_count': ok=s_count>=v
        elif k=='top_ratio': ok=top_ratio>=v and count>=10
        elif k=='win_ratio': ok=win_ratio>=v and count>=10
        elif k=='special':
            # progressively harder composite: enough games plus either a high point,
            # top finishes, or a major mode milestone.
            ok=count>=v and (best>=max(100, v*10) or top_count>=max(3,v) or win_count>=max(2,v//2) or total_progress>=v*5)
        if ok:
            unlocked.append({'id':a['id'],'name':a['name'],'desc':a['desc'],'icon':a['icon']})
    return unlock_custom(account_id, unlocked)

