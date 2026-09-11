from flask import Blueprint, render_template, request, redirect, url_for, session
import uuid
import threading
from kbo_career import *
from dynasty_utils import get_supabase

kbo_bp=Blueprint('kbo',__name__,url_prefix='/kbo')

def _aid(): return session.get('account_id') or session.get('career_account_id')
def _guard():
    if not _aid(): return redirect(url_for('account.login',next=request.path))

# KBO 상태는 Flask signed-cookie에 절대 넣지 않는다.
# Render/Gunicorn 한 프로세스에서 Supabase가 잠시 실패하더라도
# 신규 게임 직후 draft 화면까지는 이어지도록 메모리 fallback을 둔다.
_KBO_RUNTIME = {}
_KBO_ACTION_LOCKS = {}

def _action_lock(key):
    return _KBO_ACTION_LOCKS.setdefault(str(key), threading.Lock())

def _save(s):
    _KBO_RUNTIME[s.id] = asdict(s)
    # 쿠키에는 UUID 하나만 남긴다.
    session['kbo_state_id'] = s.id
    session.pop('kbo_state', None)
    session.pop('kbo_state_z', None)
    session.modified = True
    try:
        sb=get_supabase()
        sb.table('kbo_career_saves').upsert({
            'id':s.id,
            'account_id':_aid(),
            'player_name':s.player_name,
            'age':s.age,
            'team_id':s.team_id,
            'status':'retired' if s.retired else 'active',
            'state':asdict(s)
        },on_conflict='id').execute()
        return True
    except Exception as e:
        print('KBO SAVE FALLBACK:', e)
        return False

def _load():
    sid=session.get('kbo_state_id')
    if not sid:
        return None
    try:
        sb=get_supabase()
        rows=(sb.table('kbo_career_saves')
                .select('state')
                .eq('id',sid)
                .eq('account_id',_aid())
                .limit(1).execute().data or [])
        if rows and rows[0].get('state'):
            return from_dict(rows[0]['state'])
    except Exception as e:
        print('KBO LOAD FALLBACK:', e)
    raw=_KBO_RUNTIME.get(sid)
    return from_dict(raw) if raw else None


def _clear_large_legacy_session():
    # 기존 Career/144-0/PVP에서 남은 대형 signed-cookie 데이터를 제거한다.
    # 계정 인증 정보는 건드리지 않는다.
    keep = {
        'account_id','account_username','career_account_id','career_username',
        'kbo_state_id'
    }
    for key in list(session.keys()):
        if key not in keep:
            session.pop(key, None)
    session.modified = True

def _redirect_home(): return redirect(url_for('kbo.home'))

@kbo_bp.get('')
def home():
    g=_guard()
    if g:return g
    s=_load(); return render_template('kbo_home.html',state=s)

@kbo_bp.route('/new',methods=['GET','POST'])
def new():
    g=_guard()
    if g:return g
    if request.method=='POST':
        try:
            jersey=max(1,min(99,int(request.form.get('jersey','1') or 1)))
        except (TypeError, ValueError):
            jersey=1
        s=KBOState(
            player_name=request.form.get('name','신인').strip()[:20] or '신인',
            position=request.form.get('position','SS'),
            bats=request.form.get('bats','R'),
            school=request.form.get('school','high'),
            agent='',
            jersey=jersey,
            ovr=random.randint(52,59)
        )
        s.potential=random.randint(78,92)
        # Keep the rookie draft inside the player state instead of a second
        # session key. This avoids losing the draft when the session is
        # refreshed/serialized and fixes /kbo/new -> /kbo fallback.
        s.draft_offers=draft_offers(s)
        # 다른 모드가 남긴 대형 session 데이터를 먼저 비운다.
        _clear_large_legacy_session()
        session['kbo_state_id']=s.id
        _save(s)
        session.pop('kbo_draft',None)
        return redirect(url_for('kbo.draft'))
    return render_template('kbo_new.html',positions=POSITIONS)

@kbo_bp.get('/draft')
def draft():
    g=_guard()
    if g:return g
    s=_load()
    offers=(s.draft_offers if s else None)
    if not s or not offers:
        return _redirect_home()
    return render_template('kbo_draft.html',state=s,offers=offers)

@kbo_bp.post('/draft')
def draft_choose():
    g=_guard()
    if g:return g
    s=_load(); offers=(s.draft_offers if s else None) or []; tid=request.form.get('team_id'); chosen=next((x for x in offers if x['team_id']==tid),None)
    if not s or not chosen:
        return redirect(url_for('kbo.draft'))
    s.team_id=chosen['team_id']; s.team_name=chosen['name']; s.money+=chosen['signing_bonus']; s.salary=3000 if s.year>=2027 else 2700; s.fa_service_target=7 if s.school=='college' else 8; s.notes.append(f"{s.year} 신인드래프트 {chosen['round']}라운드 {s.team_name}"); s.draft_offers=[]; session.pop('kbo_draft',None); _save(s); return redirect(url_for('kbo.dashboard'))

@kbo_bp.get('/dashboard')
def dashboard():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if s.retired:return redirect(url_for('kbo.retire'))
    return render_template('kbo_dashboard.html',state=s,agent=AGENTS.get(s.agent) if s.agent else None,team_name=s.team_name,can_fa=s.fa_eligible,can_post=s.posting_eligible)

@kbo_bp.route('/training',methods=['GET','POST'])
def training():
    g=_guard()
    if g:return g
    s=_load()
    if not s: return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'training:{s.id}'):
            if s.training_done:
                return redirect(url_for('kbo.dashboard'))
            apply_training(s,request.form.get('choice','recovery')); _save(s)
        return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_training.html',state=s)

@kbo_bp.route('/life',methods=['GET','POST'])
def life():
    g=_guard()
    if g:return g
    s=_load()
    if not s: return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'life:{s.id}'):
            # 이미 이번 나이의 생활 행동을 완료했으면 재전송을 무시한다.
            if s.life_done:
                return redirect(url_for('kbo.dashboard'))
            apply_life(s,request.form.get('choice','rest')); _save(s)
        return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_life.html',state=s,choices=family_choices(s))

@kbo_bp.route('/office',methods=['GET','POST'])
def office():
    g=_guard()
    if g:return g
    s=_load()
    if request.method=='POST':
        choice=request.form.get('choice','ask_market')
        if choice=='accept_trade' and s.pending_team_move:
            old=s.team_name; s.team_id=s.pending_team_move['team_id']; s.team_name=s.pending_team_move['name']; s.loyalty=max(0,s.loyalty-8)
            s.team_history.append({'year':s.year,'from':old,'to':s.team_name,'type':'트레이드'}); s.notes.append(f"{s.year} 단장 트레이드 수용: {s.team_name}"); s.pending_team_move=None
        elif choice=='decline_trade':
            s.loyalty=min(100,s.loyalty+5); s.notes.append(f'{s.year} 트레이드 제안 거절'); s.pending_team_move=None
        elif choice in ('fa_open','fa_generate') and s.fa_eligible:
            generate_fa_offer(s)
            return redirect(url_for('kbo.fa'))
        elif choice=='posting_start' and s.posting_eligible:
            s.posting_stage='구단 동의'; s.office_done=True; s.notes.append(f'{s.year} 포스팅 도전 의사 전달')
            return redirect(url_for('kbo.posting'))
        elif choice=='military_sangmu' and s.military=='미필':
            s.military='상무 복무'; s.military_choice='상무'; s.army_years=1; s.stamina=90; s.office_done=True
        elif choice=='military_active' and s.military=='미필':
            s.military='현역 복무'; s.military_choice='현역'; s.army_years=1; s.ovr=max(40,s.ovr-2); s.office_done=True
        else:
            apply_office(s,choice)
        _save(s); return redirect(url_for('kbo.dashboard'))
    # Trade is generated only as a visible GM event; opening the page no longer mutates state repeatedly.
    return render_template('kbo_office.html',state=s,agent=AGENTS.get(s.agent) if s.agent else None,trade=s.pending_team_move,fa=s.fa_eligible,posting=s.posting_eligible)


@kbo_bp.post('/trade/refresh')
def trade_refresh():
    g=_guard()
    if g:return g
    s=_load()
    if s.age<22 or s.pending_team_move: return redirect(url_for('kbo.office'))
    teams=[x for x in KBO_TEAMS if x[0]!=s.team_id]; tid,name=random.choice(teams)
    s.pending_team_move={'team_id':tid,'name':name,'reason':random.choice(['감독의 전력 구상','단장의 리빌딩 계획','우승을 위한 전력 보강','선수단 균형 조정'])}
    _save(s); return redirect(url_for('kbo.office'))


@kbo_bp.route('/fa',methods=['GET','POST'])
def fa():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if not s.fa_offer and s.fa_eligible: generate_fa_offer(s)
    if request.method=='POST':
        with _action_lock(f'fa:{s.id}'):
            action=request.form.get('action'); tid=request.form.get('team_id')
            if action=='counter':
                negotiate_fa(s,tid,True); _save(s); return redirect(url_for('kbo.fa'))
            if action=='sign':
                negotiate_fa(s,tid,False); _save(s); return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_fa.html',state=s,offers=(s.fa_offer or {}).get('offers',[]),grade=s.fa_grade,comp=s.fa_compensation)

@kbo_bp.route('/posting',methods=['GET','POST'])
def posting():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'posting:{s.id}'):
            action=request.form.get('action')
            if action=='consent':
                s.posting_stage='포스팅 완료'; s.posting_offers=generate_posting_offers(s); _save(s); return redirect(url_for('kbo.posting'))
            if action=='reject':
                s.posting_stage='포스팅 철회'; s.posting_offers=[]; s.posting_eligible=False; s.notes.append(f'{s.year} 포스팅 철회'); _save(s); return redirect(url_for('kbo.dashboard'))
            if action=='accept':
                idx=int(request.form.get('idx','0'));
                if not (0 <= idx < len(s.posting_offers)): return redirect(url_for('kbo.posting'))
                offer=s.posting_offers[idx]
                s.overseas=True; s.office_done=True; s.overseas_years=offer['years']; s.posting_stage='해외 도전 중'; s.team_history.append({'year':s.year,'from':s.team_name,'to':offer['team'],'type':'포스팅 해외 진출'}); s.team_id='OVERSEAS'; s.team_name=offer['team']; s.salary=offer['salary']; s.posting_eligible=False; s.notes.append(f"{s.year} 포스팅 성공: {offer['team']}")
                _save(s); return redirect(url_for('kbo.dashboard'))
            if action=='return':
                idx=int(request.form.get('idx','-1'))
                offers=s.posting_return_offers or []
                if not (0 <= idx < len(offers)): return redirect(url_for('kbo.posting'))
                offer=offers[idx]
                old=s.team_name
                s.overseas=False; s.overseas_years=0; s.posting_stage='KBO 복귀 완료'; s.team_id=offer['team_id']; s.team_name=offer['name']; s.salary=offer['salary']; s.contract_years_left=offer['years']; s.posting_return_offers=[]; s.team_history.append({'year':s.year,'from':old,'to':s.team_name,'type':'포스팅 후 KBO 복귀'}); s.fame=min(100,s.fame+5); s.notes.append(f'{s.year} 해외 도전 후 {s.team_name} 복귀')
                _save(s); return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_posting.html',state=s,offers=s.posting_offers,return_offers=s.posting_return_offers)

@kbo_bp.route('/agent',methods=['GET','POST'])
def agent():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        key=request.form.get('agent','')
        if key in AGENTS:
            old=s.agent
            s.agent=key
            s.agent_trust=60
            s.notes.append(f"{s.year} 에이전트 변경: {AGENTS[key][0]}")
            if old and old != key:
                s.reputation=min(100,s.reputation+1)
            _save(s)
        return redirect(url_for('kbo.agent'))
    return render_template('kbo_agent.html',state=s,agents=AGENTS,current=s.agent)


@kbo_bp.route('/position',methods=['GET','POST'])
def position():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        action=request.form.get('action')
        target=(s.position_offer or {}).get('target')
        if target:
            if action=='expand':
                s.position_skills[target]=25
                s.notes.append(f'{s.year} {target} 수비 포지션 추가 습득')
            elif action=='switch':
                old=s.position
                s.position_skills[target]=60
                s.position_skills[old]=max(10,s.position_skills.get(old,100)-25)
                s.position=target
                s.notes.append(f'{s.year} 주 포지션 변경: {old} → {target}')
            s.position_offer=None
            _save(s)
        return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_position.html',state=s,offer=s.position_offer)

@kbo_bp.route('/special',methods=['GET','POST'])
def special():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'special:{s.id}'):
            if not s.pending_special_event:
                return redirect(url_for('kbo.result'))
            a=request.form.get('choice')
            eff={
                'celebrate':lambda:(setattr(s,'fan_popularity',min(100,s.fan_popularity+6))),
                'focus':lambda:(setattr(s,'reputation',min(100,s.reputation+3))),
                'media':lambda:(setattr(s,'fan_popularity',min(100,s.fan_popularity+5)),setattr(s,'fame',min(100,s.fame+4))),
                'rest':lambda:setattr(s,'stamina',min(100,s.stamina+5)),
                'accept':lambda:(setattr(s,'reputation',min(100,s.reputation+4)),setattr(s,'ovr',min(99,s.ovr+1))),
                'manage':lambda:setattr(s,'stamina',min(100,s.stamina+6)),
                'lead':lambda:(setattr(s,'reputation',min(100,s.reputation+5)),setattr(s,'fan_popularity',min(100,s.fan_popularity+3))),
                'quiet':lambda:(setattr(s,'family',min(100,s.family+2)),setattr(s,'reputation',min(100,s.reputation+2))),
            }
            if a in eff: eff[a]()
            s.pending_special_event=None
            _save(s)
        return redirect(url_for('kbo.result'))
    return render_template('kbo_special.html',state=s,event=s.pending_special_event)

@kbo_bp.route('/manager',methods=['GET','POST'])
def manager():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    roles=[('starter','주전 고정','출장 기회↑ · 체력 소모↑'),('core','핵심 전력','성적 기대↑ · 부담↑'),('rotation','로테이션','컨디션 균형'),('development','육성/관리','출장↓ · 성장/회복↑')]
    if request.method=='POST':
        role=request.form.get('role','rotation'); s.manager_role=dict((k,v) for k,v,_ in roles).get(role,'로테이션')
        if role=='starter': s.stamina=max(25,s.stamina-4); s.reputation=min(100,s.reputation+2)
        elif role=='core': s.fame=min(100,s.fame+4); s.stamina=max(25,s.stamina-3)
        elif role=='rotation': s.stamina=min(100,s.stamina+3)
        else: s.ovr=min(99,s.ovr+random.choice([0,0,1])); s.stamina=min(100,s.stamina+5)
        s.office_done=True; s.notes.append(f'{s.year} 감독과 역할 협의: {s.manager_role}'); _save(s); return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_manager.html',state=s,roles=roles)


@kbo_bp.get('/achievements')
def achievements():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    cards=[
      ('데뷔','18세 시즌을 완주'),('첫 안타','통산 1호 안타 기록'),('첫 홈런','통산 첫 홈런'),('첫 승','투수로 통산 첫 승'),('첫 세이브','통산 첫 세이브'),
      ('올스타','올스타 선정'),('골든글러브','골든글러브 수상'),('MVP','MVP 수상'),('우승','한국시리즈 우승'),('국가대표','대표팀 첫 발탁'),
      ('FA','첫 FA 계약'),('FA 2회','두 번째 FA 계약'),('FA 3회','세 번째 FA 계약'),('해외도전','포스팅 해외 진출'),('KBO 복귀','해외 도전 후 복귀'),
      ('베테랑','35세 시즌 완주'),('40대','40세 시즌 완주'),('장수선수','통산 15시즌 이상'),('100 WAR','통산 WAR 100 달성'),('레전드','통산 WAR 70 달성')]
    unlocked=[]
    for title,desc in cards:
        u=False
        if title=='데뷔': u=len(s.history)>=1
        elif title=='첫 안타': u=s.career_games>0 and any((h.get('avg') or 0)>0 for h in s.history if h.get('avg') is not None)
        elif title=='첫 홈런': u=s.career_hr>=1
        elif title=='첫 승': u=s.career_wins>=1
        elif title=='첫 세이브': u=s.career_saves>=1
        elif title=='올스타': u=s.allstar>=1
        elif title=='골든글러브': u=s.gg>=1
        elif title=='MVP': u=s.mvp>=1
        elif title=='우승': u=s.championships>=1
        elif title=='국가대표': u=s.national_caps>=1
        elif title=='FA': u=s.fa_count>=1
        elif title=='FA 2회': u=s.fa_count>=2
        elif title=='FA 3회': u=s.fa_count>=3
        elif title=='해외도전': u=any(h.get('type')=='포스팅 해외 진출' for h in s.team_history)
        elif title=='KBO 복귀': u=any(h.get('type')=='포스팅 해외 진출' for h in s.team_history) and not s.overseas
        elif title=='베테랑': u=s.age>=35
        elif title=='40대': u=s.age>=40 or s.retired
        elif title=='장수선수': u=len(s.history)>=15
        elif title=='100 WAR': u=s.career_war>=100
        elif title=='레전드': u=s.career_war>=70
        unlocked.append({'title':title,'desc':desc,'unlocked':u})
    return render_template('kbo_achievements.html',state=s,cards=unlocked)


@kbo_bp.route('/number',methods=['GET','POST'])
def number():
    g=_guard()
    if g:return g
    s=_load()
    if request.method=='POST':
        try: n=max(1,min(99,int(request.form.get('jersey','1'))))
        except: n=s.jersey
        s.jersey=n; s.notes.append(f'{s.year} 시즌 등번호 {n}번 선택'); s.number_history.append({'year':s.year,'number':n}); _save(s); return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_number.html',state=s)

@kbo_bp.get('/profile')
def profile():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    return render_template('kbo_profile.html',state=s)

@kbo_bp.get('/contract')
def contract():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    return render_template('kbo_contract.html',state=s,can_fa=s.fa_eligible,can_post=s.posting_eligible)

@kbo_bp.get('/family')
def family():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    return render_template('kbo_family.html',state=s)

@kbo_bp.get('/military')
def military():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    return render_template('kbo_military.html',state=s)

@kbo_bp.get('/history')
def history():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    return render_template('kbo_history.html',state=s)

@kbo_bp.route('/event',methods=['GET','POST'])
def event():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'event:{s.id}'):
            # 이미 처리한 일반 이벤트의 재전송/더블클릭은 안전하게 무시한다.
            if s.event_done or not s.pending_event:
                return redirect(url_for('kbo.result'))
            apply_event(s,request.form.get('choice','rest'))
            _save(s)
        return redirect(url_for('kbo.result'))
    if not s.pending_event:
        s.pending_event=random_event(s)
        s.event_done=False
        _save(s)
    return render_template('kbo_event.html',state=s,event=s.pending_event)

@kbo_bp.route('/national',methods=['GET','POST'])
def national():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        action=request.form.get('action')
        if action=='accept' and s.national_offer:
            ev=s.national_offer; s.national_caps+=1
            result=random.choice(['선발 출전','교체 출전','대회 엔트리 포함'])
            s.national_history.append({'year':s.year,'event':ev['event'],'result':result})
            if ev['benefit']:
                success=random.random()<(.60 if s.ovr>=85 else .42)
                if success:
                    s.national_titles+=1; s.military='병역 혜택 획득'; s.notes.append(f"{s.year} {ev['event']} 우승·병역 혜택")
                else: s.notes.append(f"{s.year} {ev['event']} 참가")
            else:
                if random.random()<.18: s.national_titles+=1
                s.notes.append(f"{s.year} {ev['event']} 참가")
            s.last_intl=ev['event']; s.national_offer=None
        elif action=='decline':
            s.reputation=max(0,s.reputation-2); s.national_offer=None; s.notes.append(f'{s.year} 국가대표 차출 고사')
        _save(s); return redirect(url_for('kbo.national'))
    return render_template('kbo_national.html',state=s,offer=s.national_offer)


@kbo_bp.get('/season')
def season():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if not (s.training_done and s.life_done and s.office_done): return redirect(url_for('kbo.dashboard'))
    return render_template('kbo_season.html',state=s)

@kbo_bp.post('/season')
def season_play():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    with _action_lock(f'season:{s.id}'):
        # 시즌 버튼의 중복 클릭으로 같은 나이의 시즌이 두 번 진행되지 않도록 한다.
        if s.season_stats and s.season_stats[-1].get('year') == s.year:
            return redirect(url_for('kbo.result'))
        returned=False
        if s.overseas:
            s.overseas_years-=1
            if s.overseas_years<=0:
                s.overseas=False; s.posting_stage='KBO 복귀 오퍼'; s.posting_return_offers=generate_kbo_return_offers(s); s.team_id='KBO_RETURN'; s.team_name='KBO 복귀 오퍼 대기'; s.fame=min(100,s.fame+5); returned=True
        if s.military_choice:
            s.army_years-=1
            if s.army_years<=0: s.military='병역 완료';s.military_choice=''
        stats=simulate_season(s)
        intl=None
        if not s.national_offer and s.age in tuple(range(20,35)) and s.ovr>=72:
            p=.06 + max(0,s.ovr-72)*.018 + (0.08 if s.fame>=50 else 0)
            if random.random()<min(.72,p):
                event=random.choice(['WBC','프리미어12','아시안게임','올림픽','APBC'])
                if event=='올림픽' and s.age not in (21,25,29,33): event='WBC'
                s.national_offer={'event':event,'benefit':event in ('아시안게임','올림픽'),'reason':random.choice(['최근 성적과 OVR이 대표팀 기준을 충족했습니다.','포지션 경쟁에서 우위를 확보했습니다.','국가대표 코칭스태프의 호출을 받았습니다.'])}
                intl=event
        # 배우자/자녀는 별도의 인생 선택으로 만들고, 자녀는 결혼 후 확률적으로 자연스럽게 생긴다.
        if s.spouse and s.age>=27 and s.children<3 and random.random()<.16:
            s.children+=1; s.child_birth_years.append(s.year); s.family=min(100,s.family+7)
            s.family_notes.append(f'{s.year} 아이가 태어났다. 이제 {s.children}명의 자녀가 생겼다.')
        s.last_intl=intl
        _save(s)
    if returned:
        return redirect(url_for('kbo.posting'))
    return redirect(url_for('kbo.result'))

@kbo_bp.route('/injury',methods=['GET','POST'])
def injury():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    if request.method=='POST':
        with _action_lock(f'injury:{s.id}'):
            apply_injury_rehab(s, request.form.get('choice','rehab'))
            _save(s)
        return redirect(url_for('kbo.result'))
    return render_template('kbo_injury.html',state=s)

@kbo_bp.get('/result')
def result():
    g=_guard()
    if g:return g
    s=_load(); stats=s.season_stats[-1] if s and s.season_stats else None
    needs_event=bool(s and ((s.pending_event and not s.event_done) or s.national_offer or s.pending_special_event))
    # 특별 이벤트가 떠도 일반 이벤트를 별도로 선택할 수 있게 한다.
    # 둘 중 하나를 먼저 처리해도 나머지는 계속 남아 있다.
    general_available=bool(s and not s.event_done)
    return render_template('kbo_result.html',state=s,stats=stats,needs_event=needs_event,general_available=general_available)

@kbo_bp.post('/next')
def next_age():
    g=_guard()
    if g:return g
    s=_load()
    if not s:return _redirect_home()
    with _action_lock(f'next:{s.id}'):
        if s.injury_status: return redirect(url_for('kbo.injury'))
        if s.pending_event and not s.event_done: return redirect(url_for('kbo.event'))
        if s.national_offer: return redirect(url_for('kbo.national'))
        if s.pending_special_event: return redirect(url_for('kbo.special'))
        if s.age>=40:
            evaluate_permanent_number(s)
            s.retired=True;_save(s);return redirect(url_for('kbo.retire'))
        age_up(s);_save(s);return redirect(url_for('kbo.dashboard'))

@kbo_bp.get('/retire')
def retire():
    g=_guard()
    if g:return g
    s=_load(); return render_template('kbo_retire.html',state=s)
