import random


EVENTS = [

    {
        "id": "breakout",
        "title": "갑작스러운 성장",
        "condition": lambda p: p.ovr >= 60,
        "weight": 8,
        "choices": [
            {
                "text": "훈련에 집중한다",
                "effect": {
                    "ovr": 2,
                    "reputation": 4
                }
            },
            {
                "text": "경기 경험을 우선한다",
                "effect": {
                    "ovr": 1,
                    "reputation": 7
                }
            }
        ]
    },

    {
        "id": "slump",
        "title": "성적 하락",
        "condition": lambda p: p.ovr >= 50,
        "weight": 10,
        "choices": [
            {
                "text": "기본기 훈련",
                "effect": {
                    "ovr": 1,
                    "reputation": -2
                }
            },
            {
                "text": "휴식과 컨디션 회복",
                "effect": {
                    "ovr": 0,
                    "reputation": 1
                }
            }
        ]
    },

    {
        "id": "coach_trust",
        "title": "감독의 신뢰",
        "condition": lambda p: p.ovr >= 65,
        "weight": 7,
        "choices": [
            {
                "text": "주전 경쟁에 도전",
                "effect": {
                    "ovr": 2,
                    "reputation": 5
                }
            },
            {
                "text": "팀에 맞춰 역할을 수행",
                "effect": {
                    "ovr": 1,
                    "reputation": 3
                }
            }
        ]
    },

    {
        "id": "minor_injury",
        "title": "컨디션 난조",
        "condition": lambda p: not p.injured,
        "weight": 9,
        "choices": [
            {
                "text": "재활을 우선한다",
                "effect": {
                    "ovr": 0,
                    "reputation": 0
                }
            },
            {
                "text": "경기에 출전한다",
                "effect": {
                    "ovr": -1,
                    "reputation": 2
                }
            }
        ]
    },

    {
        "id": "media",
        "title": "언론의 관심",
        "condition": lambda p: p.reputation >= 30,
        "weight": 6,
        "choices": [
            {
                "text": "인터뷰에 적극적으로 참여",
                "effect": {
                    "reputation": 5
                }
            },
            {
                "text": "경기에 집중",
                "effect": {
                    "reputation": 1
                }
            }
        ]
    }

]


def available_events(player):

    result = []

    for event in EVENTS:

        try:
            valid = event["condition"](player)
        except Exception:
            valid = False

        if valid:
            result.append(event)

    return result


def generate_event(player):

    events = available_events(player)

    if not events:
        return None

    weights = [
        event["weight"]
        for event in events
    ]

    return random.choices(
        events,
        weights=weights,
        k=1
    )[0]


def apply_choice(
    player,
    event,
    choice_index
):

    choices = event.get(
        "choices",
        []
    )

    if not choices:
        return {}

    if choice_index < 0:
        choice_index = 0

    if choice_index >= len(choices):
        choice_index = len(choices) - 1

    choice = choices[
        choice_index
    ]

    effect = choice.get(
        "effect",
        {}
    )

    for key, value in effect.items():

        if hasattr(player, key):

            current = getattr(
                player,
                key
            )

            setattr(
                player,
                key,
                current + value
            )

    result = {

        "event_id":
            event["id"],

        "title":
            event["title"],

        "choice":
            choice["text"],

        "effect":
            effect

    }

    player.events.append(
        result
    )

    return result
