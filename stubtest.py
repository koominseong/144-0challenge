import sys, types, os, traceback, time

flask=types.ModuleType('flask')
class Obj:
    def __init__(self,*a,**kw): pass
    def route(self,*a,**kw): return lambda f:f
    def get(self,*a,**kw): return lambda f:f
    def post(self,*a,**kw): return lambda f:f
    def __getattr__(self,n): return lambda *a,**kw: None
class Flask(Obj):
    def __init__(self,*a,**kw): self.secret_key=None
    def register_blueprint(self,*a,**kw): pass
    def before_request(self,*a,**kw): return lambda f:f
class Blueprint(Obj):
    pass
flask.Flask=Flask; flask.Blueprint=Blueprint
flask.render_template=lambda *a,**kw: ''
flask.request=types.SimpleNamespace(path='/',method='GET',form={},args={},get_json=lambda:None)
flask.session={}
flask.redirect=lambda *a,**kw: None
flask.url_for=lambda *a,**kw: '/'
flask.flash=lambda *a,**kw: None
flask.jsonify=lambda *a,**kw: {}
sys.modules['flask']=flask

sup=types.ModuleType('supabase'); sup.create_client=lambda *a,**kw: object(); sys.modules['supabase']=sup
werk=types.ModuleType('werkzeug'); sec=types.ModuleType('werkzeug.security'); sec.generate_password_hash=lambda x:x; sec.check_password_hash=lambda a,b:a==b; werk.security=sec; sys.modules['werkzeug']=werk; sys.modules['werkzeug.security']=sec

start=time.time()
try:
 import app
 print('IMPORT OK', time.time()-start)
except Exception:
 print('IMPORT FAIL', time.time()-start)
 traceback.print_exc()
