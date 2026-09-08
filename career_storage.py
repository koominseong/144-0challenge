"""Supabase-backed storage for Career Mode.

Career Mode deliberately uses independent career-slot IDs.  An account may have
multiple careers, and each browser/device keeps its own active slot in Flask's
session.  This prevents one device from opening the exact same active game as
another device unless the player explicitly selects that save.
"""
import os
import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from dynasty_utils import get_supabase


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sb():
    return get_supabase()


def create_account(username, password):
    username = (username or '').strip()
    if len(username) < 2 or len(username) > 24:
        return None, 'username'
    if len(password or '') < 4 or len(password or '') > 72:
        return None, 'password'
    sb = _sb()
    exists = sb.table('career_accounts').select('id').eq('username', username).limit(1).execute().data
    if exists:
        return None, 'exists'
    row = {
        'id': str(uuid.uuid4()),
        'username': username,
        'password_hash': generate_password_hash(password),
    }
    result = sb.table('career_accounts').insert(row).execute()
    return (result.data[0] if result.data else row), None


def authenticate(username, password):
    username = (username or '').strip()
    sb = _sb()
    rows = sb.table('career_accounts').select('*').eq('username', username).limit(1).execute().data
    if not rows:
        return None
    account = rows[0]
    if not check_password_hash(account.get('password_hash', ''), password or ''):
        return None
    try:
        sb.table('career_accounts').update({'last_login_at': _now()}).eq('id', account['id']).execute()
    except Exception:
        pass
    return account


def list_careers(account_id):
    sb = _sb()
    return sb.table('career_saves').select(
        'id,player_name,nationality,position,status,current_age,overall,peak_ovr,career_score,updated_at'
    ).eq('account_id', account_id).order('updated_at', desc=True).execute().data or []


def create_career(account_id, state_dict):
    sb = _sb()
    career_id = str(uuid.uuid4())
    row = {
        'id': career_id,
        'account_id': account_id,
        'player_name': state_dict.get('player_name', '신인'),
        'nationality': state_dict.get('nationality', ''),
        'position': state_dict.get('position', ''),
        'status': state_dict.get('status', 'active'),
        'current_age': state_dict.get('age', 16),
        'overall': state_dict.get('overall', 50),
        'peak_ovr': state_dict.get('overall', 50),
        'career_score': 0,
        'state': state_dict,
    }
    result = sb.table('career_saves').insert(row).execute()
    return (result.data[0]['id'] if result.data else career_id)


def load_career(account_id, career_id):
    sb = _sb()
    rows = sb.table('career_saves').select('state').eq('id', career_id).eq('account_id', account_id).limit(1).execute().data
    if not rows:
        return None
    return rows[0].get('state')


def save_career(account_id, career_id, state_dict, career_score=0):
    sb = _sb()
    row = {
        'player_name': state_dict.get('player_name', '신인'),
        'nationality': state_dict.get('nationality', ''),
        'position': state_dict.get('position', ''),
        'status': state_dict.get('status', 'active'),
        'current_age': state_dict.get('age', 16),
        'overall': state_dict.get('overall', 50),
        'peak_ovr': max(state_dict.get('overall', 50), max([r.get('rating', 0) for r in state_dict.get('history', [])] or [0])),
        'career_score': career_score,
        'state': state_dict,
        'updated_at': _now(),
    }
    sb.table('career_saves').update(row).eq('id', career_id).eq('account_id', account_id).execute()
    if state_dict.get('status') == 'retired':
        record = {
            'id': career_id,
            'account_id': account_id,
            'player_name': state_dict.get('player_name', '신인'),
            'nationality': state_dict.get('nationality', ''),
            'position': state_dict.get('position', ''),
            'peak_ovr': row['peak_ovr'],
            'career_score': career_score,
            'club_titles': state_dict.get('titles', 0),
            'international_titles': state_dict.get('international_titles', 0),
            'state': state_dict,
        }
        sb.table('career_records').upsert(record, on_conflict='id').execute()


def unlocked_ids(account_id):
    sb = _sb()
    rows = sb.table('career_achievements').select('achievement_id').eq('account_id', account_id).execute().data or []
    return {r['achievement_id'] for r in rows}


def unlock(account_id, achievements):
    if not achievements:
        return []
    existing = unlocked_ids(account_id)
    new_items = [a for a in achievements if a.get('id') not in existing]
    if not new_items:
        return []
    sb = _sb()
    rows = [
        {'id': str(uuid.uuid4()), 'account_id': account_id, 'achievement_id': a['id'], 'achievement_name': a['name']}
        for a in new_items
    ]
    sb.table('career_achievements').insert(rows).execute()
    return new_items


def list_achievements(account_id):
    sb = _sb()
    rows = sb.table('career_achievements').select('achievement_id,achievement_name,unlocked_at').eq('account_id', account_id).order('unlocked_at', desc=True).execute().data or []
    return rows


def leaderboard(limit=50):
    sb = _sb()
    return sb.table('career_records').select(
        'player_name,nationality,position,peak_ovr,career_score,club_titles,international_titles'
    ).order('career_score', desc=True).limit(limit).execute().data or []


def unlock_custom(account_id, achievements):
    """Unlock account-wide achievements shared by all game modes."""
    if not account_id or not achievements:
        return []
    existing = unlocked_ids(account_id)
    new_items = [a for a in achievements if a.get('id') not in existing]
    if not new_items:
        return []
    sb = _sb()
    rows=[{'id':str(uuid.uuid4()),'account_id':account_id,'achievement_id':a['id'],'achievement_name':a['name']} for a in new_items]
    sb.table('career_achievements').insert(rows).execute()
    return new_items


def save_game_record(account_id, mode, result, score=0, opponent=None):
    if not account_id:
        return
    sb=_sb()
    row={'id':str(uuid.uuid4()),'account_id':account_id,'mode':mode,'result':result,'score':score,'opponent':opponent}
    try: sb.table('game_records').insert(row).execute()
    except Exception: pass

def list_game_records(account_id, limit=100):
    if not account_id: return []
    try:
        return _sb().table('game_records').select('*').eq('account_id',account_id).order('created_at',desc=True).limit(limit).execute().data or []
    except Exception: return []
