# Career.py

import random
from datetime import datetime


class Career:
    def __init__(
        self,
        name,
        nationality,
        position,
        age,
        team,
        mode="normal"
    ):
        self.name = name
        self.nationality = nationality
        self.position = position
        self.age = age
        self.team = team
        self.mode = mode

        self.ovr = random.randint(48, 61)
        self.value = 1000000
        self.reputation = 0

        self.season = 0
        self.retired = False

        self.national_team = False
        self.trophies = []

        self.career_stats = []
        self.events = []

    # -------------------------
    # 시즌 진행
    # -------------------------

    def play_season(self):
        if self.retired:
            return None

        self.season += 1

        current_age = self.age

        if self.position == "투수":
            stats = {
                "G": random.randint(15, 60),
                "W": random.randint(0, 18),
                "ERA": round(random.uniform(2.0, 6.5), 2),
                "SO": random.randint(20, 180),
                "SV": random.randint(0, 35)
            }
        else:
            stats = {
                "G": random.randint(30, 150),
                "AVG": round(random.uniform(.180, .340), 3),
                "HR": random.randint(0, 40),
                "RBI": random.randint(0, 120)
            }

        # 나이에 따른 OVR 변화
        if current_age < 25:
            self.ovr += random.randint(1, 5)

        elif current_age < 30:
            self.ovr += random.randint(-1, 3)

        elif current_age < 35:
            self.ovr += random.randint(-2, 1)

        else:
            self.ovr += random.randint(-4, 0)

        self.ovr = max(40, min(self.ovr, 99))

        # 가치
        self.value = max(
            100000,
            int(self.value * (1 + random.uniform(-0.05, 0.25)))
        )

        # 명성
        self.reputation = max(
            0,
            self.reputation + random.randint(0, 8)
        )

        season_data = {
            "season": self.season,
            "age": current_age,
            "team": self.team,
            "ovr": self.ovr,
            "stats": stats
        }

        self.career_stats.append(season_data)

        # 시즌 종료 후 나이 증가
        self.age += 1

        return season_data

    # -------------------------
    # 이벤트 발생
    # -------------------------

    def check_event(self):
        if self.retired:
            return None

        probability = {
            "intense": 0.80,
            "normal": 0.45,
            "express": 0.20
        }.get(self.mode, 0.45)

        if random.random() > probability:
            return None

        possible_events = []

        if self.ovr >= 55:
            possible_events.append("breakout")

        if self.ovr <= 65:
            possible_events.append("slump")

        if self.ovr >= 70 and self.reputation >= 15:
            possible_events.append("overseas")

        if self.ovr >= 70 and self.reputation >= 10:
            possible_events.append("national")

        if self.ovr >= 78:
            possible_events.append("contract")

        if self.age >= 32:
            possible_events.append("veteran")

        if not possible_events:
            return None

        event = random.choice(possible_events)

        self.events.append({
            "season": self.season,
            "event": event
        })

        return event

    # -------------------------
    # 이벤트 선택
    # -------------------------

    def apply_event_choice(self, event, choice):
        if event == "breakout":

            if choice == "aggressive":
                self.ovr += 4
                self.reputation += 5

            else:
                self.ovr += 2
                self.reputation += 3

        elif event == "slump":

            if choice == "reset":
                self.ovr += 4
                self.reputation -= 1

            else:
                self.ovr += 1
                self.reputation += 2

        elif event == "overseas":

            if choice == "go":
                self.reputation += 7
                self.change_team("해외 구단")

            else:
                self.ovr += 2
                self.reputation += 3

        elif event == "national":

            if choice == "accept":
                self.national_team = True
                self.reputation += 6

            else:
                self.reputation += 2

        elif event == "contract":

            if choice == "security":
                self.ovr += 2
                self.reputation += 4
                self.value += 15000000

            else:
                self.ovr += 4
                self.reputation += 6
                self.value += 5000000

        elif event == "veteran":

            if choice == "mentor":
                self.ovr += 2
                self.reputation += 5

            else:
                self.ovr += 3
                self.reputation += 2

        self.ovr = max(40, min(self.ovr, 99))
        self.reputation = max(0, self.reputation)

    # -------------------------
    # 팀 변경
    # -------------------------

    def change_team(self, team):
        self.team = team

    # -------------------------
    # 은퇴
    # -------------------------

    def retire(self):
        self.retired = True

        return {
            "name": self.name,
            "age": self.age,
            "team": self.team,
            "ovr": self.ovr,
            "seasons": self.season,
            "value": self.value,
            "reputation": self.reputation,
            "trophies": self.trophies,
            "stats": self.career_stats
        }

    # -------------------------
    # 화면 출력용 데이터
    # -------------------------

    def to_dict(self):
        return {
            "name": self.name,
            "nationality": self.nationality,
            "position": self.position,
            "age": self.age,
            "team": self.team,
            "mode": self.mode,
            "ovr": self.ovr,
            "value": self.value,
            "reputation": self.reputation,
            "season": self.season,
            "national_team": self.national_team,
            "retired": self.retired,
            "trophies": self.trophies,
            "career_stats": self.career_stats,
            "events": self.events
        }
