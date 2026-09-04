"""Career mode engine for 144-0 Challenge."""
from pathlib import Path
import json, random
from flask import Blueprint, session

CAREER_BP = Blueprint("career", __name__)
BASE = Path(__file__).resolve().parent / "Data" / "Career"

def load(name, default=None):
    try:
        with open(BASE / name, encoding="utf-8") as f: return json.load(f)
    except (OSError, json.JSONDecodeError): return default if default is not None else []

def countries(): return load("career_countries.json", [])
def leagues(): return load("career_leagues.json", [])
def teams(): return load("career_teams.json", [])
def events(): return load("career_events.json", [])
def competitions(): return load("career_competitions.json", [])

def league_map(): return {x["league_id"]:x for x in leagues()}
def team_map(): return {x["team_id"]:x for x in teams()}

def team_list(league_id): return [x for x in teams() if x.get("league_id")==league_id]

def make_player(name, nationality, age=18, position="내야"):
    return {"name":name or "신인 선수", "nationality":nationality, "age":int(age), "position":position,
            "career_years":0, "games":0, "hits":0, "home_runs":0, "rbi":0, "wins":0, "saves":0,
            "championships":0, "all_star":0, "international_caps":0, "money":0, "reputation":0,
            "health":100, "form":50, "morale":70}

def start(name, nationality, league_id, team_id=None, age=18, position="내야", mode="default"):
    lm=league_map(); tm=team_map()
    if league_id not in lm: raise ValueError("존재하지 않는 리그입니다.")
    choices=team_list(league_id)
    if not team_id or team_id not in tm: team_id=random.choice(choices)["team_id"] if choices else None
    team=tm.get(team_id, {"team_id":team_id,"name":"FA","league_id":league_id})
    c={"active":True,"mode":mode,"season":1,"month":2,"phase":"spring","decision_used":False,
       "pending_event":None,"nationality":nationality,"league_id":league_id,"team_id":team_id,
       "team_name":team.get("name","FA"),"player":make_player(name,nationality,age,position),
       "history":[],"awards":[],"international":[],"season_log":[],"last_result":None}
    session["career"]=c; session.modified=True; return c

def state(): return session.get("career")

def _season_result(c, decision):
    p=c["player"]; league=league_map().get(c["league_id"],{}); level=str(league.get("level","1"))
    tier=max(1, min(10, int(level) if level.isdigit() else 5))
    base=random.randint(55,85) + p["form"]//8 + p["morale"]//12
    bonus={"훈련 집중":8,"휴식 우선":2,"이적 협상":0,"대표팀 도전":4}.get(decision,0)
    score=max(20, base+bonus-random.randint(0,12))
    games=random.randint(60,150) if tier<=3 else random.randint(40,110)
    hits=max(0,int(games*(0.18+score/700)))
    hr=max(0,int(games*(0.015+score/3500)))
    rbi=max(0,int(hr*2.8+hits*.18))
    wins=max(0,int(games*.02)) if p["position"] in ("선발","투수") else 0
    p["career_years"]+=1; p["games"]+=games; p["hits"]+=hits; p["home_runs"]+=hr; p["rbi"]+=rbi; p["wins"]+=wins
    p["reputation"] += max(1,score//12); p["money"] += max(1,score//3)*1000
    p["health"] = max(45,p["health"]-random.randint(0,18)); p["form"]=max(30,min(90,score)); p["morale"]=max(30,min(95,p["morale"]+random.randint(-8,10)))
    champ=random.random() < (0.10 if tier<=2 else 0.05)
    if champ: p["championships"]+=1; c["awards"].append({"season":c["season"],"award":"리그 우승"})
    if score>=82: p["all_star"]+=1; c["awards"].append({"season":c["season"],"award":"올스타 선정"})
    result={"season":c["season"],"decision":decision,"games":games,"hits":hits,"home_runs":hr,"rbi":rbi,"wins":wins,"score":score,"championship":champ}
    c["season_log"].append(result); c["last_result"]=result
    return result

def season_decision(c, decision):
    if c.get("decision_used"): raise ValueError("이번 시즌의 결정은 이미 사용했습니다.")
    allowed={x for e in events() if e.get("event_id")=="season_choice" for x in e.get("choices",[])}
    if allowed and decision not in allowed: raise ValueError("허용되지 않은 선택입니다.")
    c["decision_used"]=True
    # international chance is nationality-driven; choice can unlock a representative appearance
    if decision=="대표팀 도전" and c["player"]["age"]>=18:
        c["pending_event"]={"type":"international","title":"대표팀 제안","message":"국적을 기준으로 국제대회 대표팀 후보에 이름이 올랐습니다."}
    else: c["pending_event"]=None
    return _season_result(c,decision)

def advance(c):
    p=c["player"]; p["age"]+=1
    c["season"]+=1; c["decision_used"]=False; c["phase"]="spring"; c["month"]=2
    c["pending_event"]={"type":"season","title":"새 시즌 시작","message":f"{c['season']}년차 시즌이 시작되었습니다."}
    # small chance of transfer/retirement pressure after 12+ years
    if p["career_years"]>=12 and random.random()<0.18:
        c["pending_event"]={"type":"retirement","title":"커리어의 갈림길","message":"베테랑이 된 선수에게 은퇴 또는 마지막 도전의 선택지가 열렸습니다."}
    return c

def choose_transfer(c, target_league):
    opts=team_list(target_league)
    if not opts: raise ValueError("이적 가능한 팀이 없습니다.")
    t=random.choice(opts); c["league_id"]=target_league; c["team_id"]=t["team_id"]; c["team_name"]=t["name"]
    c["history"].append({"season":c["season"],"type":"transfer","team":t["name"]}); return c

def international_status(c):
    eligible={x.get("country_id"):x for x in countries()}.get(c.get("nationality"),{}).get("international_eligible",False)
    return {"eligible":bool(eligible),"age":c["player"]["age"],"nationality":c.get("nationality"),"competitions":competitions() if eligible else []}
