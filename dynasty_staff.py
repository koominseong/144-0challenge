# dynasty_staff.py - 전면 재작성 Part1
# =========================================
# KBO Dynasty - 감독/코칭스태프 (단체 시너지판)
# 역할: MANAGER / HEAD / HITTING / PITCHING / DEFENSE / BULLPEN / BASERUN / BATTERY
# 고유 특성 + 듀오 시너지 + 단체(3~5인) 시너지 + 방출
# =========================================

import random
from dynasty_utils import get_supabase

# ---- 감독 풀 (이름, 등급, 스타일) ----
MANAGER_POOL = [
    ("김응용", "S", "승부사"), ("김성근", "S", "지장"),
    ("김인식", "S", "덕장"),   ("김태형", "S", "승부사"),
    ("이강철", "S", "지장"),
    ("김영덕", "A", "승부사"), ("강병철", "A", "덕장"),
    ("이광환", "A", "데이터"), ("김재박", "A", "지장"),
    ("선동열", "A", "지장"),   ("김경문", "A", "승부사"),
    ("류중일", "A", "덕장"),   ("제리 로이스터", "A", "승부사"),
    ("트레이 힐만", "A", "데이터"), ("김원형", "A", "지장"),
    ("백인천", "B", "승부사"), ("조범현", "B", "데이터"),
    ("염경엽", "B", "데이터"), ("이만수", "B", "육성가"),
    ("한용덕", "B", "육성가"), ("김기태", "B", "덕장"),
    ("이승엽", "B", "승부사"), ("박진만", "B", "지장"),
    ("최원호", "B", "육성가"), ("이순철", "B", "승부사"),
    ("카를로스 수베로", "B", "데이터"), ("이범호", "B", "승부사"),
    ("이동욱", "B", "데이터"), ("맷 윌리엄스", "B", "데이터"),
    ("조원우", "B", "지장"),   ("양승호", "B", "육성가"),
    ("어우홍", "B", "덕장"),   ("김동엽", "B", "승부사"),
    ("김진영", "B", "승부사"), ("김성한", "B", "승부사"),
    ("이희수", "B", "덕장"),
    ("허문회", "C", "데이터"), ("박영길", "C", "승부사"),
    ("유백만", "C", "육성가"), ("정동진", "C", "덕장"),
    ("홍원기", "C", "육성가"), ("강인권", "C", "덕장"),
    ("김진욱", "C", "육성가"), ("래리 서튼", "C", "덕장"),
    ("류지현", "C", "지장"),   ("김종국", "C", "지장"),
    ("허삼영", "C", "데이터"), ("서영무", "C", "지장"),
    ("강태정", "C", "덕장"),   ("천보성", "C", "지장"),
    ("이광은", "C", "승부사"), ("유남호", "C", "덕장"),
    ("서정환", "C", "지장"),   ("김명성", "C", "덕장"),
    ("우용득", "C", "육성가"), ("박종훈", "C", "육성가"),
    ("공필성", "C", "승부사"), ("배성서", "C", "덕장"),
    ("한동화", "C", "지장"),   ("박현식", "C", "승부사"),
    ("김용철", "C", "육성가"), ("신용균", "C", "덕장"),
]

# ---- 코치 풀 (이름, 역할, 등급, 특성) ----
COACH_POOL = [
    # 수석코치
    ("김광수", "HEAD", "A", "감독의 오른팔"),
    ("조원우2", "HEAD", "B", "덕아웃 안정"),
    ("김평호", "HEAD", "B", "감독의 오른팔"),
    ("최태원", "HEAD", "B", "덕아웃 안정"),
    ("박승호", "HEAD", "C", "덕아웃 안정"),
    ("김광림", "HEAD", "C", "감독의 오른팔"),
    ("이종운", "HEAD", "C", "덕아웃 안정"),
    # 타격코치
    ("장효조", "HITTING", "S", "타격의 달인"),
    ("양준혁", "HITTING", "S", "타격의 달인"),
    ("김용희", "HITTING", "A", "장타 혁명"),
    ("이정훈", "HITTING", "A", "정교한 타격"),
    ("장종훈", "HITTING", "A", "장타 혁명"),
    ("이병규", "HITTING", "A", "정교한 타격"),
    ("정경배", "HITTING", "A", "선구안 전도사"),
    ("이호준", "HITTING", "A", "장타 혁명"),
    ("이대호", "HITTING", "A", "장타 혁명"),
    ("김동주", "HITTING", "A", "장타 혁명"),
    ("박흥식", "HITTING", "B", "선구안 전도사"),
    ("김무관", "HITTING", "B", "정교한 타격"),
    ("김한수", "HITTING", "B", "장타 혁명"),
    ("박정태", "HITTING", "B", "정교한 타격"),
    ("박용택", "HITTING", "B", "타격의 달인"),
    ("홍성흔", "HITTING", "B", "장타 혁명"),
    ("박한이", "HITTING", "B", "정교한 타격"),
    ("서용빈", "HITTING", "B", "정교한 타격"),
    ("유한준", "HITTING", "B", "선구안 전도사"),
    ("김태균", "HITTING", "B", "장타 혁명"),
    ("장성호", "HITTING", "B", "선구안 전도사"),
    ("마해영", "HITTING", "B", "장타 혁명"),
    ("박재홍", "HITTING", "B", "장타 혁명"),
    ("심정수", "HITTING", "B", "장타 혁명"),
    ("김재현", "HITTING", "C", "선구안 전도사"),
    ("강동우", "HITTING", "C", "정교한 타격"),
    ("정성훈", "HITTING", "C", "선구안 전도사"),
    ("이택근", "HITTING", "C", "정교한 타격"),
    # 투수코치
    ("최동원", "PITCHING", "S", "에이스 메이커"),
    ("김시진", "PITCHING", "A", "제구 마스터"),
    ("양상문", "PITCHING", "A", "에이스 메이커"),
    ("정민철", "PITCHING", "A", "강철 어깨"),
    ("송진우", "PITCHING", "A", "강철 어깨"),
    ("정민태", "PITCHING", "A", "에이스 메이커"),
    ("정명원", "PITCHING", "A", "제구 마스터"),
    ("윤학길", "PITCHING", "A", "강철 어깨"),
    ("이상훈", "PITCHING", "A", "에이스 메이커"),
    ("김용수", "PITCHING", "A", "강철 어깨"),
    ("손혁", "PITCHING", "B", "제구 마스터"),
    ("이상군", "PITCHING", "B", "강철 어깨"),
    ("한희민", "PITCHING", "B", "제구 마스터"),
    ("조계현", "PITCHING", "B", "에이스 메이커"),
    ("배영수", "PITCHING", "B", "강철 어깨"),
    ("구대성", "PITCHING", "B", "에이스 메이커"),
    ("최일언", "PITCHING", "B", "제구 마스터"),
    ("김수경", "PITCHING", "B", "제구 마스터"),
    ("가득염", "PITCHING", "B", "강철 어깨"),
    ("이대진", "PITCHING", "B", "에이스 메이커"),
    ("손민한", "PITCHING", "B", "제구 마스터"),
    ("윤석민", "PITCHING", "B", "제구 마스터"),
    ("서재응", "PITCHING", "B", "제구 마스터"),
    ("김병현", "PITCHING", "B", "에이스 메이커"),
    ("임선동", "PITCHING", "B", "에이스 메이커"),
    ("주형광", "PITCHING", "B", "제구 마스터"),
    ("염종석", "PITCHING", "B", "강철 어깨"),
    ("오봉옥", "PITCHING", "C", "제구 마스터"),
    ("선우대식", "PITCHING", "C", "제구 마스터"),
    ("이상목", "PITCHING", "C", "강철 어깨"),
    ("박명환", "PITCHING", "C", "에이스 메이커"),
    ("박충식", "PITCHING", "C", "강철 어깨"),
    # 수비코치
    ("김민재", "DEFENSE", "A", "그물 수비"),
    ("류지현2", "DEFENSE", "A", "시프트 설계자"),
    ("유지훤", "DEFENSE", "B", "그물 수비"),
    ("김민호", "DEFENSE", "B", "그물 수비"),
    ("손시헌", "DEFENSE", "B", "시프트 설계자"),
    ("박진만2", "DEFENSE", "B", "그물 수비"),
    ("김재걸", "DEFENSE", "B", "그물 수비"),
    ("정근우", "DEFENSE", "B", "시프트 설계자"),
    ("김호", "DEFENSE", "B", "그물 수비"),
    ("이종열", "DEFENSE", "B", "시프트 설계자"),
    ("박기혁", "DEFENSE", "C", "그물 수비"),
    ("권용관", "DEFENSE", "C", "그물 수비"),
    ("오대석", "DEFENSE", "C", "그물 수비"),
    ("강석천", "DEFENSE", "C", "그물 수비"),
    # 불펜코치
    ("오승환", "BULLPEN", "S", "필승조 조련"),
    ("임창용", "BULLPEN", "A", "필승조 조련"),
    ("정우람", "BULLPEN", "A", "필승조 조련"),
    ("진필중", "BULLPEN", "B", "필승조 조련"),
    ("권오준", "BULLPEN", "B", "마당쇠 육성"),
    ("정재훈", "BULLPEN", "B", "필승조 조련"),
    ("조웅천", "BULLPEN", "B", "필승조 조련"),
    ("류택현", "BULLPEN", "B", "마당쇠 육성"),
    ("조규제", "BULLPEN", "B", "필승조 조련"),
    ("김현욱", "BULLPEN", "B", "마당쇠 육성"),
    ("강영식", "BULLPEN", "C", "마당쇠 육성"),
    ("이혜천", "BULLPEN", "C", "마당쇠 육성"),
    # 주루코치
    ("이종범", "BASERUN", "S", "그린라이트"),
    ("김일권", "BASERUN", "A", "그린라이트"),
    ("전준호", "BASERUN", "A", "그린라이트"),
    ("이종욱", "BASERUN", "B", "폭주 기관차"),
    ("정수성", "BASERUN", "B", "그린라이트"),
    ("김주찬", "BASERUN", "B", "그린라이트"),
    ("이용규", "BASERUN", "B", "폭주 기관차"),
    ("김종국2", "BASERUN", "B", "그린라이트"),
    ("이대형", "BASERUN", "C", "폭주 기관차"),
    ("최익성", "BASERUN", "C", "폭주 기관차"),
    # 배터리코치
    ("박경완", "BATTERY", "S", "볼배합 아티스트"),
    ("진갑용", "BATTERY", "A", "도루 저지 특화"),
    ("조인성", "BATTERY", "A", "볼배합 아티스트"),
    ("이만수2", "BATTERY", "A", "볼배합 아티스트"),
    ("김동수", "BATTERY", "B", "볼배합 아티스트"),
    ("김정민", "BATTERY", "B", "도루 저지 특화"),
    ("유승안", "BATTERY", "B", "도루 저지 특화"),
    ("장채근", "BATTERY", "B", "도루 저지 특화"),
    ("최기문", "BATTERY", "B", "도루 저지 특화"),
    ("강성우", "BATTERY", "C", "도루 저지 특화"),
    ("채상병", "BATTERY", "C", "볼배합 아티스트"),
]

# ---- 듀오 시너지 (감독, 코치) → (칭호, 설명, 효과) ----
PERSON_SYNERGY = {
    ("김응용", "조계현"): ("해태 왕조", "전력 +2%", {"sim": 0.02}),
    ("김응용", "김일권"): ("해태 기동력", "도루 +5%p", {"steal_bonus": 0.05}),
    ("김응용", "이종범"): ("바람의 시대", "도루 +5%p · 추가 진루 +4%p", {"steal_bonus": 0.05, "send_bonus": 0.04}),
    ("김응용", "김광수"): ("초대 사령탑 라인", "전력 +1%", {"sim": 0.01}),
    ("김성근", "박경완"): ("SK 왕조 배터리", "상대 도루 -6%p · 삼진 +0.6%p", {"opp_steal_cut": 0.06, "so_bonus": 0.006}),
    ("김성근", "정경배"): ("김성근 사단", "타자 성장 +1", {"bat_growth": 1}),
    ("김성근", "가득염"): ("벌떼 야구", "불펜 지속 +2 · 등판 보정 +1", {"rp_outs": 2, "rp_boost": 1}),
    ("김성근", "조웅천"): ("무한 불펜", "불펜 지속 +2", {"rp_outs": 2}),
    ("김성근", "김광림"): ("야신의 그림자", "전력 +1% · 투수 성장 +1", {"sim": 0.01, "pit_growth": 1}),
    ("김인식", "장종훈"): ("한화의 자존심", "타자 성장 +1 · 팬 +1%p", {"bat_growth": 1, "fan_bonus": 0.01}),
    ("김인식", "정민철"): ("국가대표 마운드", "선발 지속 +2", {"sp_outs": 2}),
    ("김인식", "구대성"): ("야생마와 국민감독", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("김태형", "조인성"): ("미러클 두산", "상대 도루 -5%p · 전력 +1%", {"opp_steal_cut": 0.05, "sim": 0.01}),
    ("김태형", "정재훈"): ("화수분 불펜", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("김태형", "이대호"): ("조선의 4번타자", "타격 보정 +0.6%", {"bat_mod": 0.006}),
    ("김태형", "김동주"): ("두목곰의 귀환", "타자 성장 +1", {"bat_growth": 1}),
    ("선동열", "진갑용"): ("삼성 왕조 배터리", "삼진 +0.8%p", {"so_bonus": 0.008}),
    ("선동열", "오승환"): ("끝판대장 시대", "불펜 등판 보정 +3", {"rp_boost": 3}),
    ("선동열", "이종범"): ("해태 레전드", "도루 +5%p · 전력 +0.5%", {"steal_bonus": 0.05, "sim": 0.005}),
    ("선동열", "윤석민"): ("에이스 계보", "삼진 +0.6%p · 선발 지속 +1", {"so_bonus": 0.006, "sp_outs": 1}),
    ("류중일", "김한수"): ("삼성 라이온즈 왕조", "전력 +1.5% · 타자 성장 +1", {"sim": 0.015, "bat_growth": 1}),
    ("류중일", "오승환"): ("왕조의 뒷문", "불펜 등판 보정 +3", {"rp_boost": 3}),
    ("류중일", "박한이"): ("꾸준함의 미학", "타자 성장 +1", {"bat_growth": 1}),
    ("류중일", "김평호"): ("디테일 야구", "도루 +3%p · 수비력 +2", {"steal_bonus": 0.03, "def_bonus": 2}),
    ("김경문", "전준호"): ("공격 야구", "도루 +5%p · 추가 진루 +5%p", {"steal_bonus": 0.05, "send_bonus": 0.05}),
    ("김경문", "이종욱"): ("두산 육상부", "도루 +6%p", {"steal_bonus": 0.06}),
    ("김경문", "오승환"): ("베이징의 끝판왕", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("김경문", "이대호"): ("베이징 4번타자", "타격 보정 +0.5%", {"bat_mod": 0.005}),
    ("이강철", "유한준"): ("마법 같은 KT", "전력 +1.5%", {"sim": 0.015}),
    ("염경엽", "정수성"): ("발야구 히어로즈", "도루 +6%p", {"steal_bonus": 0.06}),
    ("염경엽", "박흥식"): ("넥센 타선 부활", "타자 성장 +1", {"bat_growth": 1}),
    ("염경엽", "이택근"): ("히어로즈 주장", "전력 +0.5% · 팬 +1%p", {"sim": 0.005, "fan_bonus": 0.01}),
    ("김기태", "서용빈"): ("의리 야구", "팬 +2%p · 전력 +0.5%", {"fan_bonus": 0.02, "sim": 0.005}),
    ("김기태", "장성호"): ("KIA 타선 재건", "타자 성장 +1", {"bat_growth": 1}),
    ("김기태", "임창용"): ("2017 통합우승", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("이광환", "서용빈"): ("1994 신바람", "타격 보정 +0.5% · 팬 +1%p", {"bat_mod": 0.005, "fan_bonus": 0.01}),
    ("이광환", "류택현"): ("스타 시스템", "불펜 지속 +2", {"rp_outs": 2}),
    ("이광환", "김용수"): ("노송과 스타시스템", "선발 지속 +2", {"sp_outs": 2}),
    ("트레이 힐만", "박경완"): ("2018 비상", "전력 +1.5%", {"sim": 0.015}),
    ("조범현", "박경완"): ("배터리 교과서", "상대 도루 -6%p", {"opp_steal_cut": 0.06}),
    ("조범현", "이대진"): ("V10의 주역", "선발 지속 +2", {"sp_outs": 2}),
    ("한용덕", "송진우"): ("한화 레전드 마운드", "선발 지속 +2 · 투수 성장 +1", {"sp_outs": 2, "pit_growth": 1}),
    ("김진욱", "임창용"): ("애니콜 재림", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("강병철", "최동원"): ("1984년의 기적", "선발 지속 +3", {"sp_outs": 3}),
    ("강병철", "윤학길"): ("고독한 황태자", "선발 지속 +2", {"sp_outs": 2}),
    ("강병철", "염종석"): ("1992 롯데의 가을", "선발 지속 +2 · 팬 +1%p", {"sp_outs": 2, "fan_bonus": 0.01}),
    ("김영덕", "장효조"): ("삼성 황금타선", "타격 보정 +0.6%", {"bat_mod": 0.006}),
    ("백인천", "박정태"): ("롯데 자이언츠 혼", "타자 성장 +1", {"bat_growth": 1}),
    ("백인천", "마해영"): ("백인천 사단", "타격 보정 +0.5%", {"bat_mod": 0.005}),
    ("제리 로이스터", "가득염"): ("No Fear", "전력 +1% · 팬 +1%p", {"sim": 0.01, "fan_bonus": 0.01}),
    ("양승호", "이대호"): ("가을 DNA", "타격 보정 +0.5% · 팬 +1%p", {"bat_mod": 0.005, "fan_bonus": 0.01}),
    ("이순철", "이대형"): ("발끝의 예술", "도루 +5%p", {"steal_bonus": 0.05}),
    ("김성한", "이대진"): ("타이거즈 혼", "선발 지속 +2", {"sp_outs": 2}),
    ("서영무", "장효조"): ("원조 삼성", "타격 보정 +0.5%", {"bat_mod": 0.005}),
    ("김재박", "정명원"): ("현대 왕조 마운드", "선발 지속 +2 · 삼진 +0.4%p", {"sp_outs": 2, "so_bonus": 0.004}),
    ("김재박", "유지훤"): ("현대 왕조 내야", "수비력 +3", {"def_bonus": 3}),
    ("김재박", "전준호"): ("현대 기동력", "도루 +4%p", {"steal_bonus": 0.04}),
    ("이만수", "박경완"): ("포수 왕국", "상대 도루 -5%p", {"opp_steal_cut": 0.05}),
    ("허삼영", "오승환"): ("돌아온 끝판왕", "불펜 등판 보정 +2", {"rp_boost": 2}),
    ("이동욱", "손시헌"): ("NC 내야의 뿌리", "수비력 +2", {"def_bonus": 2}),
    ("이승엽", "김동주"): ("라이언킹과 두목곰", "타격 보정 +0.6%", {"bat_mod": 0.006}),
    ("김종국", "김종국2"): ("동명이인의 만남", "도루 +3%p · 팬 +1%p", {"steal_bonus": 0.03, "fan_bonus": 0.01}),
]

# ---- 단체 시너지 (3~5인, 같은 팀에 전원 소속 시 발동) ----
# members에는 감독/코치 이름 혼합 가능
GROUP_SYNERGY = [
    {"members": ["김응용", "조계현", "김일권", "이종범"],
     "title": "해태 왕조 완전체", "desc": "전력 +2% · 도루 +4%p",
     "fx": {"sim": 0.02, "steal_bonus": 0.04}},
    {"members": ["김성근", "박경완", "정경배", "가득염"],
     "title": "SK 와이번스 왕조", "desc": "전력 +2% · 불펜 지속 +2 · 상대 도루 -4%p",
     "fx": {"sim": 0.02, "rp_outs": 2, "opp_steal_cut": 0.04}},
    {"members": ["류중일", "김한수", "오승환", "진갑용"],
     "title": "삼성 왕조 완전체", "desc": "전력 +2% · 불펜 등판 보정 +2",
     "fx": {"sim": 0.02, "rp_boost": 2}},
    {"members": ["김태형", "조인성", "정재훈"],
     "title": "두산 미러클 트리오", "desc": "전력 +1.5% · 불펜 등판 보정 +1",
     "fx": {"sim": 0.015, "rp_boost": 1}},
    {"members": ["김재박", "정명원", "유지훤", "전준호"],
     "title": "현대 유니콘스 왕조", "desc": "전력 +2% · 수비력 +3",
     "fx": {"sim": 0.02, "def_bonus": 3}},
    {"members": ["김인식", "송진우", "정민철", "구대성", "장종훈"],
     "title": "한화 독수리 5인방", "desc": "전력 +2% · 선발 지속 +2 · 타자 성장 +1",
     "fx": {"sim": 0.02, "sp_outs": 2, "bat_growth": 1}},
    {"members": ["이광환", "서용빈", "김용수", "류택현"],
     "title": "1994 신바람 LG", "desc": "전력 +1.5% · 팬 +2%p",
     "fx": {"sim": 0.015, "fan_bonus": 0.02}},
    {"members": ["김경문", "오승환", "이대호", "진갑용"],
     "title": "2008 베이징 신화", "desc": "전력 +2% · 불펜 보정 +2 · 타격 +0.4%",
     "fx": {"sim": 0.02, "rp_boost": 2, "bat_mod": 0.004}},
    {"members": ["염경엽", "정수성", "박흥식", "이택근"],
     "title": "넥센 발야구단", "desc": "도루 +6%p · 추가 진루 +4%p",
     "fx": {"steal_bonus": 0.06, "send_bonus": 0.04}},
    {"members": ["강병철", "최동원", "염종석"],
     "title": "롯데 마운드 계보", "desc": "선발 지속 +3 · 삼진 +0.6%p",
     "fx": {"sp_outs": 3, "so_bonus": 0.006}},
    {"members": ["조범현", "이대진", "장성호"],
     "title": "2009 V10", "desc": "전력 +1.5%",
     "fx": {"sim": 0.015}},
]

ALL_ROLES = ["MANAGER", "HEAD", "HITTING", "PITCHING", "DEFENSE", "BULLPEN", "BASERUN", "BATTERY"]

GRADE_SALARY = {"S": 80, "A": 55, "B": 35, "C": 20}
GRADE_SIM = {"S": 0.03, "A": 0.02, "B": 0.01, "C": 0.0}
GRADE_GROWTH = {"S": 2, "A": 1, "B": 1, "C": 0}
GRADE_MULT = {"S": 2.0, "A": 1.5, "B": 1.0, "C": 0.5}

STYLE_DESC = {
    "승부사": "베테랑 팀(평균 7년차↑) 전력 +2.5%",
    "육성가": "4년차 이하 선수 성장 +1",
    "지장": "전력 +1.5%",
    "덕장": "시즌 팬 증가율 +3%p",
    "데이터": "전력 +1% · 접전 승부 유리",
}

TRAIT_DESC = {
    "감독의 오른팔": "팀 전력 보정 25% 증폭",
    "덕아웃 안정":   "전력 +0.5% · 팬 +0.5%p",
    "타격의 달인":   "팀 타격 +0.6%",
    "장타 혁명":     "타자 성장 시 파워 추가 +1",
    "정교한 타격":   "번트 성공률 +6%p",
    "선구안 전도사": "팀 출루 소폭 상승",
    "에이스 메이커": "선발 투구 지속력 +2아웃",
    "제구 마스터":   "팀 삼진 유도 +0.8%p",
    "강철 어깨":     "선발 피로 저하 완화",
    "그물 수비":     "호수비 확률 상승 (수비력 +3)",
    "시프트 설계자": "시프트 성공 +5%p / 역효과 -3%p",
    "필승조 조련":   "불펜 등판 시 능력 +2",
    "마당쇠 육성":   "불펜 투구 지속력 +3아웃",
    "그린라이트":    "도루 성공률 +5%p",
    "폭주 기관차":   "추가 진루(3루 도전) 성공 +7%p",
}

ROLE_KR = {
    "MANAGER": "감독", "HEAD": "수석코치", "HITTING": "타격코치",
    "PITCHING": "투수코치", "DEFENSE": "수비코치", "BULLPEN": "불펜코치",
    "BASERUN": "주루코치", "BATTERY": "배터리코치",
}


# =========================================
# 스태프 시장 초기화 + 신규 인물 증분 유입 (이름 diff)
# =========================================
def init_staff_market(save_id):
    sb = get_supabase()

    existing = (
        sb.table("dynasty_staff").select("name").eq("save_id", save_id).execute().data
    )
    have = {s["name"] for s in existing}

    rows = []
    for name, grade, style in MANAGER_POOL:
        if name in have:
            continue
        rows.append(
            {"save_id": save_id, "team_id": None, "name": name,
             "role": "MANAGER", "grade": grade, "style": style,
             "trait": None, "salary": GRADE_SALARY[grade], "hired_season": None}
        )
    for name, role, grade, trait in COACH_POOL:
        if name in have:
            continue
        rows.append(
            {"save_id": save_id, "team_id": None, "name": name,
             "role": role, "grade": grade, "style": None,
             "trait": trait, "salary": GRADE_SALARY[grade], "hired_season": None}
        )

    if rows:
        for i in range(0, len(rows), 100):
            sb.table("dynasty_staff").insert(rows[i : i + 100]).execute()
        print(f"[dynasty_staff] 신규 인물 추가={len(rows)}명")
    return len(rows)

# dynasty_staff.py - 전면 재작성 Part2

# =========================================
# 팀별 스태프 효과 계산 (특성 + 듀오 + 단체 시너지)
# effects 키:
#   sim, bat_growth, pit_growth, young_growth, fan_bonus, clutch
#   bat_mod, bunt_bonus, power_growth, so_bonus,
#   sp_outs, sp_fatigue_cut, def_bonus, shift_plus, shift_backfire_cut,
#   rp_boost, rp_outs, steal_bonus, send_bonus, opp_steal_cut,
#   synergies: [(칭호, 설명)]
# =========================================
def _empty_effects():
    return {
        "sim": 0.0, "bat_growth": 0, "pit_growth": 0, "young_growth": 0,
        "fan_bonus": 0.0, "clutch": False,
        "bat_mod": 0.0, "bunt_bonus": 0.0, "power_growth": 0,
        "so_bonus": 0.0, "sp_outs": 0, "sp_fatigue_cut": 0.0,
        "def_bonus": 0, "shift_plus": 0.0, "shift_backfire_cut": 0.0,
        "rp_boost": 0, "rp_outs": 0,
        "steal_bonus": 0.0, "send_bonus": 0.0, "opp_steal_cut": 0.0,
        "synergies": [],
    }


TRAIT_EFFECT = {
    "덕아웃 안정":   ("sim", 0.005),
    "타격의 달인":   ("bat_mod", 0.006),
    "장타 혁명":     ("power_growth", 1),
    "정교한 타격":   ("bunt_bonus", 0.06),
    "선구안 전도사": ("bat_mod", 0.004),
    "에이스 메이커": ("sp_outs", 2),
    "제구 마스터":   ("so_bonus", 0.008),
    "강철 어깨":     ("sp_fatigue_cut", 0.4),
    "그물 수비":     ("def_bonus", 3),
    "시프트 설계자": ("shift_plus", 0.05),
    "필승조 조련":   ("rp_boost", 2),
    "마당쇠 육성":   ("rp_outs", 3),
    "그린라이트":    ("steal_bonus", 0.05),
    "폭주 기관차":   ("send_bonus", 0.07),
}


def _merge_fx(e, fx):
    for k, v in fx.items():
        if isinstance(e.get(k), bool):
            e[k] = e[k] or bool(v)
        else:
            e[k] = e.get(k, 0) + v


def get_staff_effects(save_id):
    sb = get_supabase()

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .not_.is_("team_id", "null")
        .execute()
        .data
    )

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]
    season = save["season"]

    roster = (
        sb.table("dynasty_roster")
        .select("team_id, dynasty_player(appear_season)")
        .eq("save_id", save_id)
        .execute()
        .data
    )
    years_by_team = {}
    for r in roster:
        p = r["dynasty_player"]
        if p:
            years_by_team.setdefault(r["team_id"], []).append(
                season - p["appear_season"] + 1
            )

    manager_name = {}
    for s in staff:
        if s["role"] == "MANAGER":
            manager_name[s["team_id"]] = s["name"]

    # 팀별 소속 이름 집합 (단체 시너지용)
    names_by_team = {}
    for s in staff:
        names_by_team.setdefault(s["team_id"], set()).add(s["name"])

    effects = {}
    head_amp = set()

    for s in staff:
        tid = s["team_id"]
        e = effects.setdefault(tid, _empty_effects())
        grade = s["grade"]
        mult = GRADE_MULT[grade]

        # ----- 감독 -----
        if s["role"] == "MANAGER":
            e["sim"] += GRADE_SIM[grade]
            style = s["style"]
            if style == "지장":
                e["sim"] += 0.015
            elif style == "데이터":
                e["sim"] += 0.01
                e["clutch"] = True
            elif style == "덕장":
                e["fan_bonus"] += 0.03
            elif style == "육성가":
                e["young_growth"] += 1
            elif style == "승부사":
                ys = years_by_team.get(tid, [])
                avg = sum(ys) / len(ys) if ys else 0
                e["sim"] += 0.025 if avg >= 7 else 0.005
            continue

        # ----- 역할 기본 효과 -----
        if s["role"] == "HEAD":
            e["sim"] += 0.005 * mult
            if grade in ("S", "A"):
                e["young_growth"] += 1
            if s.get("trait") == "감독의 오른팔":
                head_amp.add(tid)
        elif s["role"] == "HITTING":
            e["bat_growth"] += GRADE_GROWTH[grade]
        elif s["role"] == "PITCHING":
            e["pit_growth"] += GRADE_GROWTH[grade]
        elif s["role"] == "DEFENSE":
            e["def_bonus"] += round(2 * mult)
            e["shift_backfire_cut"] += 0.01 * mult
        elif s["role"] == "BULLPEN":
            e["rp_outs"] += round(2 * mult)
            e["rp_boost"] += round(1 * mult)
        elif s["role"] == "BASERUN":
            e["steal_bonus"] += 0.03 * mult
            e["send_bonus"] += 0.03 * mult
        elif s["role"] == "BATTERY":
            e["opp_steal_cut"] += 0.04 * mult
            e["so_bonus"] += 0.004 * mult

        # ----- 고유 특성 -----
        trait = s.get("trait")
        if trait in TRAIT_EFFECT:
            key, base = TRAIT_EFFECT[trait]
            val = base * mult
            if isinstance(base, int):
                e[key] += round(val)
            else:
                e[key] += val

        # ----- 듀오 시너지 -----
        mname = manager_name.get(tid)
        duo = PERSON_SYNERGY.get((mname, s["name"])) if mname else None
        if duo:
            title, desc, fx = duo
            _merge_fx(e, fx)
            e["synergies"].append((title, f"{mname} × {s['name'].rstrip('2')} — {desc}"))

    # ----- 단체 시너지 (전원 같은 팀) -----
    for tid, names in names_by_team.items():
        e = effects.get(tid)
        if not e:
            continue
        for g in GROUP_SYNERGY:
            if set(g["members"]).issubset(names):
                _merge_fx(e, g["fx"])
                mem = " · ".join(n.rstrip("2") for n in g["members"])
                e["synergies"].append((g["title"], f"[{len(g['members'])}인] {mem} — {g['desc']}"))

    # ----- 수석코치 '감독의 오른팔': 팀 전력 보정 증폭 -----
    for tid in head_amp:
        if tid in effects:
            effects[tid]["sim"] *= 1.25

    return effects


# =========================================
# 방출 (유저)
# =========================================
def fire_staff(save_id, team_id, staff_id):
    sb = get_supabase()

    s = (
        sb.table("dynasty_staff")
        .select("*").eq("save_id", save_id).eq("id", staff_id).execute().data
    )
    if not s:
        return False, "해당 인물을 찾을 수 없습니다."
    s = s[0]

    if s["team_id"] != team_id:
        return False, "내 팀 소속이 아닙니다."

    sb.table("dynasty_staff").update(
        {"team_id": None, "hired_season": None}
    ).eq("id", staff_id).execute()

    return True, f"{s['name'].rstrip('2')} {ROLE_KR.get(s['role'], s['role'])} 방출. (지급한 연봉은 환불되지 않음)"


# =========================================
# 연봉 지급 (예산 부족 시 고연봉부터 자동 해임)
# =========================================
def pay_staff_salaries(save_id):
    sb = get_supabase()

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data

    staff = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .not_.is_("team_id", "null")
        .order("salary", desc=True)
        .execute()
        .data
    )

    budgets = {t["id"]: (t.get("budget") or 0) for t in teams}
    fired = []

    for s in staff:
        tid = s["team_id"]
        if budgets.get(tid, 0) >= s["salary"]:
            budgets[tid] -= s["salary"]
        else:
            fired.append(s["id"])

    if fired:
        for i in range(0, len(fired), 50):
            sb.table("dynasty_staff").update(
                {"team_id": None, "hired_season": None}
            ).in_("id", fired[i : i + 50]).execute()

    rows = []
    for t in teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budgets[t["id"]]
        rows.append(row)
    sb.table("dynasty_team").upsert(rows).execute()

    print(f"[dynasty_staff] 연봉 지급 완료, 해임={len(fired)}명")


# =========================================
# 고용 (유저)
# =========================================
def hire_staff(save_id, team_id, staff_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    s = (
        sb.table("dynasty_staff")
        .select("*").eq("save_id", save_id).eq("id", staff_id).execute().data
    )
    if not s:
        return False, "해당 인물을 찾을 수 없습니다."
    s = s[0]

    if s["team_id"] is not None:
        return False, f"{s['name'].rstrip('2')}은(는) 이미 다른 팀 소속입니다."

    current = (
        sb.table("dynasty_staff")
        .select("id, name")
        .eq("save_id", save_id)
        .eq("team_id", team_id)
        .eq("role", s["role"])
        .execute()
        .data
    )

    team = sb.table("dynasty_team").select("*").eq("id", team_id).execute().data[0]
    budget = team.get("budget") or 0

    if budget < s["salary"]:
        return False, f"예산 부족 (연봉 {s['salary']} / 보유 {budget})"

    if current:
        sb.table("dynasty_staff").update(
            {"team_id": None, "hired_season": None}
        ).eq("id", current[0]["id"]).execute()

    sb.table("dynasty_staff").update(
        {"team_id": team_id, "hired_season": save["season"]}
    ).eq("id", staff_id).execute()

    sb.table("dynasty_team").update(
        {"budget": budget - s["salary"]}
    ).eq("id", team_id).execute()

    return True, f"{s['name'].rstrip('2')} 영입! (연봉 {s['salary']} 즉시 지급, 이후 매 시즌 자동 차감)"


# =========================================
# AI 감독 경질 (오프시즌) — 하위 3팀 확률 경질, 부임 첫 시즌 면책
# =========================================
def ai_fire_managers(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]
    season = save["season"]

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    ranked = sorted(
        teams,
        key=lambda t: ((t["wins"] + 0.5 * t["ties"]) / max(1, t["wins"] + t["losses"] + t["ties"])),
        reverse=True,
    )

    fire_prob = {}
    n = len(ranked)
    for i, t in enumerate(ranked):
        rank = i + 1
        if rank == n:
            fire_prob[t["id"]] = 0.6
        elif rank == n - 1:
            fire_prob[t["id"]] = 0.45
        elif rank == n - 2:
            fire_prob[t["id"]] = 0.3

    managers = (
        sb.table("dynasty_staff")
        .select("*")
        .eq("save_id", save_id)
        .eq("role", "MANAGER")
        .not_.is_("team_id", "null")
        .execute()
        .data
    )

    team_map = {t["id"]: t for t in teams}
    events = []
    fired = 0

    for m in managers:
        t = team_map.get(m["team_id"])
        if not t or t["is_user"]:
            continue
        p = fire_prob.get(t["id"], 0.0)
        if p <= 0 or m.get("hired_season") == season:
            continue
        if random.random() < p:
            sb.table("dynasty_staff").update(
                {"team_id": None, "hired_season": None}
            ).eq("id", m["id"]).execute()
            fired += 1
            events.append(
                {"save_id": save_id, "season": season, "week": 99,
                 "icon": "🪑", "message": f"{t['team_name']}, 성적 부진으로 {m['name'].rstrip('2')} 감독 경질"}
            )

    if events:
        try:
            sb.table("dynasty_event").insert(events).execute()
        except Exception as ex:
            print(f"[dynasty_staff] 경질 뉴스 기록 skip: {ex}")

    print(f"[dynasty_staff] AI 감독 경질={fired}명")
    return fired


# =========================================
# AI 자동 고용 — 듀오/단체 시너지 후보 우선
# =========================================
def ai_hire_staff(save_id):
    sb = get_supabase()

    save = sb.table("dynasty_save").select("season").eq("id", save_id).execute().data[0]

    teams = sb.table("dynasty_team").select("*").eq("save_id", save_id).execute().data
    ai_teams = [t for t in teams if not t["is_user"]]

    staff = sb.table("dynasty_staff").select("*").eq("save_id", save_id).execute().data

    market = [s for s in staff if s["team_id"] is None]
    hired_count = 0
    budgets = {t["id"]: (t.get("budget") or 0) for t in ai_teams}

    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    market.sort(key=lambda s: grade_order[s["grade"]])

    CORE = ("MANAGER", "HITTING", "PITCHING")
    EXTRA = ("HEAD", "BULLPEN", "DEFENSE", "BATTERY", "BASERUN")

    for t in ai_teams:
        my_staff = [s for s in staff if s["team_id"] == t["id"]]
        have = {s["role"] for s in my_staff}
        my_names = {s["name"] for s in my_staff}
        mgr = next((s for s in my_staff if s["role"] == "MANAGER"), None)

        for role in CORE + EXTRA:
            if role in have:
                continue
            ratio = 0.15 if role in CORE else 0.08
            cap = budgets[t["id"]] * ratio
            candidates = [
                s for s in market if s["role"] == role and s["salary"] <= cap
            ]
            if not candidates:
                continue

            # 시너지 후보 우선: 듀오 > 단체 멤버 근접 > 최고 등급
            pick = None
            if mgr:
                for c in candidates:
                    if (mgr["name"], c["name"]) in PERSON_SYNERGY:
                        pick = c
                        break
            if pick is None:
                for c in candidates:
                    for g in GROUP_SYNERGY:
                        mem = set(g["members"])
                        if c["name"] in mem and len(mem & my_names) >= 2:
                            pick = c
                            break
                    if pick:
                        break
            if pick is None:
                pick = candidates[0]
            market.remove(pick)

            sb.table("dynasty_staff").update(
                {"team_id": t["id"], "hired_season": save["season"]}
            ).eq("id", pick["id"]).execute()

            budgets[t["id"]] -= pick["salary"]
            my_names.add(pick["name"])
            hired_count += 1

            if role == "MANAGER":
                mgr = pick

    rows = []
    for t in ai_teams:
        row = dict(t)
        row.pop("pct", None)
        row.pop("gb", None)
        row["budget"] = budgets[t["id"]]
        rows.append(row)
    if rows:
        sb.table("dynasty_team").upsert(rows).execute()

    print(f"[dynasty_staff] AI 고용={hired_count}명")
    return hired_count
