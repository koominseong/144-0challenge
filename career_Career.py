import random
import uuid
from datetime import datetime


class CareerPlayer:

    def __init__(
        self,
        name,
        nationality,
        position,
        age,
        league_id,
        team_id,
        mode="normal"
    ):

        self.player_id = str(uuid.uuid4())

        self.name = name
        self.nationality = nationality
        self.position = position

        self.age = int(age)

        self.league_id = league_id
        self.team_id = team_id

        self.mode = mode

        # -------------------------
        # 능력
        # -------------------------

        self.ovr = random.randint(48, 60)
        self.potential = random.randint(65, 90)

        self.contact = random.randint(35, 65)
        self.power = random.randint(35, 65)
        self.eye = random.randint(35, 65)
        self.speed = random.randint(35, 65)
        self.fielding = random.randint(35, 65)
        self.arm = random.randint(35, 65)

        self.velocity = random.randint(35, 65)
        self.command = random.randint(35, 65)
        self.breaking = random.randint(35, 65)
        self.stamina = random.randint(35, 65)

        # -------------------------
        # 커리어
        # -------------------------

        self.season = 0

        self.reputation = 0

        self.market_value = 1000000

        self.contract_years = 1
        self.contract_salary = 0

        self.national_team_caps = 0

        self.injured = False

        self.retired = False

        # -------------------------
        # 기록
        # -------------------------

        self.seasons = []

        self.transfers = []

        self.contracts = []

        self.international = []

        self.events = []

        self.awards = []

        self.trophies = []

    # ==================================================
    # 시즌 시작
    # ==================================================

    def start_season(self):

        if self.retired:
            return None

        self.season += 1

        return {
            "season": self.season,
            "age": self.age,
            "league_id": self.league_id,
            "team_id": self.team_id
        }

    # ==================================================
    # 성장
    # ==================================================

    def development(self):

        if self.retired:
            return

        # 젊을수록 성장 확률 증가
        if self.age <= 21:
            growth = random.randint(2, 7)

        elif self.age <= 24:
            growth = random.randint(1, 5)

        elif self.age <= 28:
            growth = random.randint(0, 3)

        elif self.age <= 32:
            growth = random.randint(-1, 2)

        else:
            growth = random.randint(-4, 0)

        # 잠재력
        if self.ovr < self.potential:
            growth += random.choice([0, 1, 1, 2])

        self.ovr += growth

        self.ovr = max(
            40,
            min(99, self.ovr)
        )

        return growth

    # ==================================================
    # 타자 시즌 성적
    # ==================================================

    def simulate_batting(self):

        games = random.randint(
            40,
            150
        )

        avg_base = (
            self.contact / 100
        )

        avg = (
            0.160 +
            avg_base * 0.190 +
            random.uniform(-0.025, 0.025)
        )

        avg = round(
            max(.150, min(.380, avg)),
            3
        )

        hr = int(
            self.power *
            random.uniform(.20, .65)
        )

        rbi = int(
            hr * random.uniform(1.5, 3.2)
            +
            games *
            random.uniform(.15, .45)
        )

        runs = int(
            games *
            random.uniform(.25, .65)
        )

        sb = int(
            self.speed *
            random.uniform(.05, .35)
        )

        return {
            "G": games,
            "AVG": avg,
            "HR": hr,
            "RBI": rbi,
            "R": runs,
            "SB": sb
        }

    # ==================================================
    # 투수 시즌 성적
    # ==================================================

    def simulate_pitching(self):

        games = random.randint(
            15,
            65
        )

        era = (
            6.5 -
            self.command * 0.035 -
            self.breaking * 0.015
            +
            random.uniform(-.5, .5)
        )

        era = round(
            max(1.20, min(8.00, era)),
            2
        )

        wins = max(
            0,
            int(
                self.ovr *
                random.uniform(.03, .18)
            )
        )

        strikeouts = int(
            self.velocity *
            random.uniform(.7, 2.2)
            +
            self.breaking *
            random.uniform(.5, 1.5)
        )

        saves = 0

        if self.position in [
            "RP",
            "CP",
            "마무리"
        ]:

            saves = random.randint(
                0,
                min(45, games)
            )

        return {
            "G": games,
            "W": wins,
            "ERA": era,
            "SO": strikeouts,
            "SV": saves
        }

    # ==================================================
    # 시즌 시뮬레이션
    # ==================================================

    def simulate_season(self):

        if self.retired:
            return None

        self.start_season()

        self.injured = (
            random.random() < 0.04
        )

        if self.injured:

            games_penalty = random.randint(
                10,
                60
            )

        else:

            games_penalty = 0

        if self.position in [
            "SP",
            "RP",
            "CP",
            "투수",
            "선발",
            "불펜",
            "마무리"
        ]:

            stats = self.simulate_pitching()

        else:

            stats = self.simulate_batting()

        stats["G"] = max(
            1,
            stats["G"] - games_penalty
        )

        development = self.development()

        self.update_value(stats)

        self.reputation_update(stats)

        season_data = {

            "season": self.season,

            "age": self.age,

            "league_id": self.league_id,

            "team_id": self.team_id,

            "ovr": self.ovr,

            "stats": stats,

            "development": development,

            "injured": self.injured,

            "awards": [],

            "team_result": None

        }

        self.seasons.append(
            season_data
        )

        self.age += 1

        return season_data

    # ==================================================
    # 가치
    # ==================================================

    def update_value(self, stats):

        performance = self.ovr

        if "AVG" in stats:

            performance += (
                stats["AVG"] - .250
            ) * 100

            performance += (
                stats["HR"] * .08
            )

        else:

            performance += (
                4.00 - stats["ERA"]
            ) * 3

            performance += (
                stats["SO"] * .02
            )

        performance = max(
            30,
            performance
        )

        self.market_value = int(
            max(
                100000,
                performance *
                performance *
                10000
            )
        )

    # ==================================================
    # 명성
    # ==================================================

    def reputation_update(self, stats):

        gain = 0

        if "AVG" in stats:

            if stats["AVG"] >= .300:
                gain += 5

            if stats["HR"] >= 30:
                gain += 5

            if stats["RBI"] >= 100:
                gain += 4

        else:

            if stats["ERA"] <= 3.00:
                gain += 6

            if stats["W"] >= 12:
                gain += 4

            if stats["SO"] >= 150:
                gain += 4

        self.reputation += gain

    # ==================================================
    # 이적
    # ==================================================

    def transfer(
        self,
        new_league,
        new_team,
        reason="transfer"
    ):

        old_league = self.league_id
        old_team = self.team_id

        self.league_id = new_league
        self.team_id = new_team

        self.transfers.append({

            "season": self.season,

            "from_league": old_league,

            "from_team": old_team,

            "to_league": new_league,

            "to_team": new_team,

            "reason": reason

        })

    # ==================================================
    # 계약
    # ==================================================

    def sign_contract(
        self,
        years,
        salary
    ):

        self.contract_years = years

        self.contract_salary = salary

        self.contracts.append({

            "season": self.season,

            "team": self.team_id,

            "years": years,

            "salary": salary

        })

    # ==================================================
    # 국가대표
    # ==================================================

    def national_team_callup(
        self,
        competition
    ):

        self.national_team_caps += 1

        self.international.append({

            "season": self.season,

            "competition": competition,

            "team": self.nationality

        })

        self.reputation += 3

    # ==================================================
    # 수상
    # ==================================================

    def add_award(self, award):

        if award not in self.awards:

            self.awards.append(
                award
            )

    # ==================================================
    # 트로피
    # ==================================================

    def add_trophy(self, trophy):

        self.trophies.append({

            "season": self.season,

            "name": trophy

        })

    # ==================================================
    # 은퇴
    # ==================================================

    def retire(self):

        self.retired = True

        return self.summary()

    # ==================================================
    # 최종 요약
    # ==================================================

    def summary(self):

        batting = {

            "G": 0,
            "HR": 0,
            "RBI": 0,
            "R": 0,
            "SB": 0

        }

        pitching = {

            "G": 0,
            "W": 0,
            "SO": 0,
            "SV": 0

        }

        for season in self.seasons:

            stats = season["stats"]

            for key in batting:

                if key in stats:

                    batting[key] += stats[key]

            for key in pitching:

                if key in stats:

                    pitching[key] += stats[key]

        return {

            "player_id": self.player_id,

            "name": self.name,

            "nationality": self.nationality,

            "position": self.position,

            "age": self.age,

            "seasons": len(self.seasons),

            "ovr": self.ovr,

            "market_value": self.market_value,

            "reputation": self.reputation,

            "trophies": self.trophies,

            "awards": self.awards,

            "transfers": self.transfers,

            "contracts": self.contracts,

            "international": self.international,

            "batting": batting,

            "pitching": pitching

        }

    # ==================================================
    # Flask/Session용
    # ==================================================

    def to_dict(self):

        return {

            "player_id": self.player_id,

            "name": self.name,

            "nationality": self.nationality,

            "position": self.position,

            "age": self.age,

            "league_id": self.league_id,

            "team_id": self.team_id,

            "mode": self.mode,

            "ovr": self.ovr,

            "potential": self.potential,

            "reputation": self.reputation,

            "market_value": self.market_value,

            "contract_years": self.contract_years,

            "contract_salary": self.contract_salary,

            "national_team_caps":
                self.national_team_caps,

            "injured": self.injured,

            "retired": self.retired,

            "season": self.season,

            "seasons": self.seasons,

            "transfers": self.transfers,

            "contracts": self.contracts,

            "international":
                self.international,

            "events": self.events,

            "awards": self.awards,

            "trophies": self.trophies

        }
