from flask import Blueprint, render_template, session, redirect, url_for
from career_storage import list_achievements
from career import ACHIEVEMENT_DEFS
from unified_achievements import MODE_ACHIEVEMENTS

all_achievements_bp=Blueprint('all_achievements',__name__)

@all_achievements_bp.get('/achievements')
def all_achievements():
    aid=session.get('account_id') or session.get('career_account_id')
    if not aid: return redirect(url_for('account.login'))
    try: unlocked={r['achievement_id'] for r in list_achievements(aid)}
    except Exception: unlocked=set()
    groups=[]
    career=[dict(a,unlocked=a['id'] in unlocked) for a in ACHIEVEMENT_DEFS]
    groups.append(('career','CAREER','⚾',career))
    for mode,defs in MODE_ACHIEVEMENTS.items():
        groups.append((mode,mode.upper(),{'scout':'🔎','dynasty':'👑','trait':'🧬','classic':'⚾','gauntlet':'🔥','auction':'💰'}[mode],[dict(a,unlocked=a['id'] in unlocked) for a in defs]))
    total=sum(len(x[3]) for x in groups); done=sum(sum(1 for a in x[3] if a['unlocked']) for x in groups)
    return render_template('all_achievements.html',groups=groups,total=total,done=done)
