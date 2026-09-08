from flask import Blueprint, render_template, request, redirect, url_for, session
from career_storage import create_account, authenticate, list_careers, list_achievements, leaderboard, list_game_records

account_bp = Blueprint('account', __name__, url_prefix='/account')

@account_bp.route('/login', methods=['GET','POST'])
def login():
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        try: account=authenticate(username,password)
        except Exception: account=None
        if not account:
            error='아이디 또는 비밀번호가 올바르지 않습니다.'
        else:
            session['account_id']=account['id']; session['account_username']=account['username']
            session['career_account_id']=account['id']; session['career_username']=account['username']
            nxt=request.args.get('next') or '/'
            if not nxt.startswith('/') or nxt.startswith('//'): nxt='/'
            return redirect(nxt)
    return render_template('account_login.html', mode='login', error=error, next=request.args.get('next','/'))

@account_bp.route('/register', methods=['GET','POST'])
def register():
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password',''); password2=request.form.get('password2','')
        if password != password2: error='비밀번호가 서로 다릅니다.'
        else:
            try: account, code=create_account(username,password)
            except Exception: account,code=None,'db'
            if not account:
                error={'username':'아이디는 2~24자로 입력해 주세요.','password':'비밀번호는 4~72자로 입력해 주세요.','exists':'이미 사용 중인 아이디입니다.','db':'Supabase Career 테이블을 먼저 생성해 주세요.'}.get(code,'회원가입에 실패했습니다.')
            else:
                session['account_id']=account['id']; session['account_username']=account['username']
                session['career_account_id']=account['id']; session['career_username']=account['username']
                return redirect('/')
    return render_template('account_login.html', mode='register', error=error, next=request.args.get('next','/'))

@account_bp.get('/logout')
def logout():
    for k in ('account_id','account_username','career_account_id','career_username','career_id','career_state'):
        session.pop(k,None)
    return redirect('/account/login')

@account_bp.get('/mypage')
def mypage():
    account_id=session.get('account_id') or session.get('career_account_id')
    if not account_id: return redirect(url_for('account.login', next='/account/mypage'))
    try: careers=list_careers(account_id)
    except Exception: careers=[]
    try: achievements=list_achievements(account_id)
    except Exception: achievements=[]
    try: hall=leaderboard(100)
    except Exception: hall=[]
    try: game_records=list_game_records(account_id, 100)
    except Exception: game_records=[]
    return render_template('mypage.html', username=session.get('account_username') or session.get('career_username',''), careers=careers, achievements=achievements, hall=hall, game_records=game_records)
