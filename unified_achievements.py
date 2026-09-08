"""Account-wide achievements for non-Career modes."""
from career_storage import unlock_custom, list_game_records


def _records(account_id, mode=None):
    rows = list_game_records(account_id, 500)
    if mode:
        rows = [r for r in rows if str(r.get('mode', '')).lower() == mode.lower()]
    return rows


def unlock_mode_achievements(account_id, mode, result=None):
    """Unlock account-wide achievements based on completed game milestones."""
    if not account_id:
        return []
    mode = mode.lower()
    result = result or {}
    rows = _records(account_id, mode)
    count = len(rows) + 1  # current game is about to be saved / may already be saved
    unlocked = []

    def add(aid, name, desc, icon='🏅'):
        unlocked.append({'id': f'{mode}_{aid}', 'name': name, 'desc': desc, 'icon': icon})

    if mode == 'pvp':
        wins = sum(1 for r in rows if '승리' in str(r.get('result', '')))
        score = float(result.get('score', 0) or 0)
        winner = str(result.get('winner', '')).upper()
        if count >= 1: add('first', '첫 PVP', 'PVP를 처음 완료하세요.', '⚔️')
        if winner in {'A', 'B'}: add('victory', '승부사', 'PVP에서 승리하세요.', '🔥')
        if count >= 5: add('five', 'PVP 단골', 'PVP를 5회 완료하세요.', '🎮')
        if count >= 10: add('ten', '라이벌', 'PVP를 10회 완료하세요.', '🥊')
        if score >= 50: add('fifty', '압도적 승리', 'PVP에서 50점 이상을 기록하세요.', '💥')
        if wins >= 5: add('five_wins', 'PVP 강자', 'PVP에서 5승을 기록하세요.', '👑')
        if wins >= 10: add('ten_wins', 'PVP 지배자', 'PVP에서 10승을 기록하세요.', '🏆')
        if count >= 25: add('twentyfive', '끝나지 않는 라이벌전', 'PVP를 25회 완료하세요.', '☠️')

    elif mode == 'draft':
        rank = int(result.get('rank', 99) or 99)
        score = float(result.get('score', 0) or 0)
        if count >= 1: add('first', '첫 드래프트', 'Draft를 처음 완료하세요.', '🃏')
        if rank == 1: add('win', '드래프트 챔피언', 'Draft에서 1위를 차지하세요.', '🏆')
        if rank == 1 and score >= 600: add('dominant', '압도적 지명', 'Draft에서 1위와 높은 점수를 동시에 기록하세요.', '💎')
        if count >= 5: add('five', '지명 중독', 'Draft를 5회 완료하세요.', '🎯')
        if count >= 10: add('ten', '드래프트 전문가', 'Draft를 10회 완료하세요.', '🧠')
        if rank <= 2: add('podium', '포디움', 'Draft에서 2위 이상을 기록하세요.', '🥈')
        if score >= 500: add('fivehundred', '500점 클럽', 'Draft에서 500점 이상을 기록하세요.', '🔥')
        if count >= 25: add('twentyfive', '역대급 스카우터', 'Draft를 25회 완료하세요.', '☠️')

    elif mode == 'auction':
        rank = int(result.get('rank', 99) or 99)
        grade = str(result.get('grade', '')).upper()
        score = float(result.get('score', 0) or 0)
        if count >= 1: add('first', '첫 경매', 'Auction을 처음 완료하세요.', '💰')
        if rank == 1: add('win', '최고 낙찰가', 'Auction에서 1위를 차지하세요.', '🏆')
        if grade == 'S': add('s_grade', '완벽한 경매', 'Auction에서 S 등급을 받으세요.', '💎')
        if rank <= 3: add('podium', '경매 명가', 'Auction에서 3위 안에 드세요.', '🥇')
        if score >= 90: add('ninety', '선수 보는 눈', 'Auction에서 90점 이상을 기록하세요.', '👁️')
        if count >= 5: add('five', '단골 단장', 'Auction을 5회 완료하세요.', '📋')
        if count >= 10: add('ten', '경매의 전설', 'Auction을 10회 완료하세요.', '👑')
        if count >= 25: add('twentyfive', '시장 지배자', 'Auction을 25회 완료하세요.', '☠️')

    elif mode == 'scout':
        grade = str(result.get('grade', '')).upper()
        place = int(result.get('place', 99) or 99)
        total = float(result.get('total', 0) or 0)
        if count >= 1: add('first', '첫 스카우팅', 'Scout를 처음 완료하세요.', '🔎')
        if place == 1: add('first_place', '최고의 안목', 'Scout에서 1위를 차지하세요.', '👁️')
        if grade == 'S': add('s_grade', '천리안', 'Scout에서 S 등급을 받으세요.', '💎')
        if place <= 2: add('podium', '스카우팅 명문', 'Scout에서 2위 안에 드세요.', '🥇')
        if total >= 350: add('threefifty', '대박 발굴', 'Scout에서 350점 이상을 기록하세요.', '💰')
        if count >= 5: add('five', '베테랑 스카우터', 'Scout를 5회 완료하세요.', '📋')
        if count >= 10: add('ten', '스카우팅 전문가', 'Scout를 10회 완료하세요.', '🧠')
        if count >= 25: add('twentyfive', '전설의 스카우터', 'Scout를 25회 완료하세요.', '☠️')

    elif mode == 'dynasty':
        season = int(result.get('season', 0) or 0)
        rank = int(result.get('rank', 99) or 99)
        champion = bool(result.get('champion'))
        if season >= 1: add('first_season', '첫 시즌', 'Dynasty에서 첫 시즌을 완료하세요.', '📅')
        if champion: add('champion', '왕조의 시작', 'Dynasty에서 한국시리즈 우승을 차지하세요.', '🏆')
        if rank == 1: add('regular_season', '정규시즌 1위', 'Dynasty 정규시즌 1위를 기록하세요.', '🥇')
        if season >= 3: add('three_seasons', '3년차 단장', 'Dynasty를 3시즌 이상 진행하세요.', '📈')
        if season >= 5: add('five_seasons', '장기 집권', 'Dynasty를 5시즌 이상 진행하세요.', '👑')
        if season >= 10: add('ten_seasons', '왕조 건설자', 'Dynasty를 10시즌 이상 진행하세요.', '🏯')
        if season >= 15: add('fifteen_seasons', '불멸의 프런트', 'Dynasty를 15시즌 이상 진행하세요.', '🔥')
        if champion and season >= 5: add('dynasty', '진짜 왕조', '5시즌 이상 진행하며 한국시리즈 우승을 차지하세요.', '☠️')

    return unlock_custom(account_id, unlocked)
