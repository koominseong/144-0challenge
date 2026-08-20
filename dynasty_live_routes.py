# dynasty_live_routes.py - v3.2
# =========================================
# app.py 등록:
#   from dynasty_live_routes import live_bp
#   app.register_blueprint(live_bp)
# =========================================

from flask import Blueprint, render_template, request, redirect, url_for

from dynasty_utils import get_supabase
from dynasty_live import (
    start_live_game,
    start_scenario,
    progress,
    load_context,
    user_side,
    offense_defense,
    win_prob,
    _current_batter,
    _cond as cond_of,
)

live_bp = Blueprint("dynasty_live", __name__)


# =========================================
# LIVE 진입
# =========================================

@live_bp.route("/dynasty/<int:save_id>/live/<int:schedule_id>")
def live_enter(save_id, schedule_id):

    sb = get_supabase()

    g = (
        sb.table("dynasty_schedule")
        .select("played")
        .eq("id", schedule_id)
        .execute()
        .data[0]
    )

    live_row = start_live_game(
        save_id,
        schedule_id
    )

    if g["played"] and not live_row["finished"]:
        return redirect(
            url_for(
                "dynasty.dynasty_dashboard",
                save_id=save_id
            )
        )

    return _render(
        save_id,
        live_row
    )


# =========================================
# 시나리오
# =========================================

@live_bp.route("/dynasty/<int:save_id>/scenario/<code>")
def scenario_enter(save_id, code):

    if code not in (
        "save_lead",
        "comeback"
    ):
        return redirect(
            url_for(
                "dynasty.dynasty_dashboard",
                save_id=save_id
            )
        )

    live_row = start_scenario(
        save_id,
        code
    )

    live_row = progress(
        save_id,
        live_row["id"]
    )

    return _render(
        save_id,
        live_row
    )


# =========================================
# LIVE 액션
# =========================================

@live_bp.route(
    "/dynasty/<int:save_id>/live/<int:live_id>/action",
    methods=["POST"]
)
def live_action(save_id, live_id):

    action = request.form.get(
        "action",
        "swing"
    )

    ph_id = request.form.get(
        "ph_id",
        type=int
    )

    rp_id = request.form.get(
        "rp_id",
        type=int
    )

    slot = request.form.get(
        "slot",
        type=int
    )

    skill = request.form.get(
        "skill",
        type=int
    )

    outcome = request.form.get(
        "outcome"
    )

    # =====================================
    # v3.2 감독 지시
    # =====================================

    tactic = request.form.get(
        "tactic"
    )

    defense_mode = request.form.get(
        "defense_mode"
    )

    live_row = progress(
        save_id,
        live_id,
        user_action=action,
        ph_id=ph_id,
        rp_id=rp_id,
        user_action_slot=slot,
        skill=skill,
        outcome=outcome,
        tactic=tactic,
        defense_mode=defense_mode
    )

    return _render(
        save_id,
        live_row
    )


# =========================================
# 화면 렌더링
# =========================================

def _render(save_id, live_row):

    sb = get_supabase()

    state = live_row["state"]

    ctx = load_context(
        save_id,
        state
    )

    home = ctx["team_map"][
        state["home_id"]
    ]

    away = ctx["team_map"][
        state["away_id"]
    ]

    us = user_side(
        state,
        ctx
    )

    off, def_ = offense_defense(
        state
    )

    mode = (
        state.get("view_mode")
        or "manager"
    )

    # =====================================
    # 주자
    # =====================================

    base_names = [
        ctx["players"][rid]["name"]
        if rid
        else None
        for rid in state["bases"]
    ]

    # =====================================
    # 컨디션
    # =====================================

    cond_map = state.get(
        "cond",
        {}
    )

    def cond_mark(pid):

        c = cond_map.get(
            str(pid),
            0
        )

        if c >= 2:
            return "🔥"

        if c <= -2:
            return "❄"

        return ""

    # =====================================
    # 현재 투수
    # =====================================

    cur_pitcher = None

    pk = (
        "h_pitcher"
        if def_ == "home"
        else "a_pitcher"
    )

    if state.get(pk):

        p = ctx["players"][
            state[pk]
        ]

        outs_thrown = state[
            "h_pit_outs"
            if def_ == "home"
            else "a_pit_outs"
        ]

        def_fx = (
            ctx["home_fx"]
            if def_ == "home"
            else ctx["away_fx"]
        )

        max_outs = (
            int(
                12
                + (
                    p["stamina"]
                    or 50
                ) * 0.21
            )
            + def_fx.get(
                "sp_outs",
                0
            )
        )

        stamina_pct = max(
            0,
            min(
                100,
                round(
                    (
                        1
                        - outs_thrown
                        / max(
                            1,
                            max_outs
                        )
                    )
                    * 100
                )
            )
        )

        cur_pitcher = {

            "id":
                p["id"],

            "name":
                p["name"],

            "overall":
                p["overall"],

            "ip":
                f"{outs_thrown // 3}."
                f"{outs_thrown % 3}",

            "stamina_pct":
                stamina_pct,
        }

    # =====================================
    # 라인업
    # =====================================

    def lineup_view(side):

        team = ctx[side]

        if (
            not team
            or not team["batters"]
        ):
            return []

        ok = (
            "h_order"
            if side == "home"
            else "a_order"
        )

        cur_slot = (
            state[ok]
            % len(team["batters"])
        )

        over = (
            state
            .get("ph_over", {})
            .get(side, {})
        )

        rows = []

        for i, p in enumerate(
            team["batters"]
        ):

            shown = ctx["players"].get(
                over.get(
                    str(i)
                ),
                p
            )

            rows.append({

                "num":
                    i + 1,

                "id":
                    shown["id"],

                "name":
                    shown["name"],

                "overall":
                    shown["overall"],

                "positions":
                    shown.get(
                        "positions"
                    ) or "",

                "cond":
                    cond_mark(
                        shown["id"]
                    ),

                "at_bat": (
                    i == cur_slot
                    and side == off
                    and state["pending"]
                    != "finished"
                ),

                "sub":
                    str(i) in over,
            })

        return rows

    # =====================================
    # 다음 타자
    # =====================================

    next_batter = None

    for r in lineup_view(off):

        if r["at_bat"]:

            next_batter = r

            break

    # =====================================
    # 벤치 / 불펜
    # =====================================

    used_ph = state.get(
        "used_ph",
        []
    )

    bench = []
    rps = []

    if us:

        bench = [

            {
                "id":
                    p["id"],

                "name":
                    p["name"],

                "overall":
                    p["overall"],

                "positions":
                    p.get(
                        "positions"
                    ) or "",

                "cond":
                    cond_mark(
                        p["id"]
                    ),
            }

            for p in ctx[us].get(
                "bench",
                []
            )

            if p["id"]
            not in used_ph
        ]

        cur_pid = state[
            "h_pitcher"
            if us == "home"
            else "a_pitcher"
        ]

        rps = [

            {
                "id":
                    p["id"],

                "name":
                    p["name"],

                "overall":
                    p["overall"],

                "cond":
                    cond_mark(
                        p["id"]
                    ),
            }

            for p in ctx[us]["rps"]

            if p["id"] != cur_pid
        ]

    # =====================================
    # v3.2 불펜 상태
    # =====================================

    bullpen_status = []

    if us:

        bullpen_state = (
            state
            .get("bullpen", {})
            .get(us, {})
        )

        cur_pid = state.get(
            "h_pitcher"
            if us == "home"
            else "a_pitcher"
        )

        for p in ctx[us].get(
            "rps",
            []
        ):

            if p["id"] == cur_pid:
                continue

            bp = bullpen_state.get(
                str(p["id"]),
                {}
            )

            required = bp.get(
                "required_pitches",
                15
            )

            warmup = bp.get(
                "warmup_pitches",
                0
            )

            bullpen_status.append({

                "id":
                    p["id"],

                "name":
                    p["name"],

                "overall":
                    p["overall"],

                "warming":
                    bool(
                        bp.get(
                            "warming",
                            False
                        )
                    ),

                "warmup":
                    warmup,

                "required":
                    required,

                "ready":
                    bool(
                        bp.get(
                            "ready",
                            False
                        )
                        or warmup >= required
                    ),
            })

    # =====================================
    # v3.2 실제 수비 위치
    # =====================================

    defense_view = []

    if us:

        defense_state = (
            state
            .get("defense", {})
            .get(us, {})
        )

        pitcher_key = (
            "h_pitcher"
            if us == "home"
            else "a_pitcher"
        )

        for pos in (
            "P",
            "C",
            "1B",
            "2B",
            "3B",
            "SS",
            "LF",
            "CF",
            "RF"
        ):

            if pos == "P":

                pid = state.get(
                    pitcher_key
                )

            else:

                pid = defense_state.get(
                    pos
                )

            if not pid:
                continue

            p = ctx["players"].get(
                pid
            )

            if not p:
                continue

            defense_view.append({

                "pos":
                    pos,

                "id":
                    p["id"],

                "name":
                    p["name"],

                "overall":
                    p["overall"],

                "positions":
                    p.get(
                        "positions"
                    ) or "",
            })

    # =====================================
    # 작전 성공률
    # =====================================

    steal_pct = None
    bunt_pct = None
    coach_tip = None

    if (
        us
        and off == us
        and state["pending"]
        in (
            "offense",
            "duel_bat"
        )
    ):

        off_fx = (
            ctx["home_fx"]
            if off == "home"
            else ctx["away_fx"]
        )

        def_fx = (
            ctx["home_fx"]
            if def_ == "home"
            else ctx["away_fx"]
        )

        if (
            state["bases"][0]
            and not state["bases"][1]
        ):

            runner = ctx["players"][
                state["bases"][0]
            ]

            spd = (
                runner["speed"]
                or 40
            ) + cond_of(
                state,
                runner["id"]
            )

            sp = (
                0.45
                + (
                    spd - 50
                ) * 0.008
                + off_fx.get(
                    "steal_bonus",
                    0.0
                )
                - def_fx.get(
                    "opp_steal_cut",
                    0.0
                )
            )

            steal_pct = round(
                min(
                    0.9,
                    max(
                        0.1,
                        sp
                    )
                ) * 100
            )

            if steal_pct >= 60:

                coach_tip = (
                    f"주루코치: "
                    f"\"{runner['name']}, "
                    f"충분히 갈 수 있습니다. "
                    f"성공률 {steal_pct}%로 봅니다.\""
                )

            elif steal_pct <= 40:

                coach_tip = (
                    f"주루코치: "
                    f"\"무리입니다. "
                    f"{steal_pct}%… "
                    f"아웃카운트만 헌납할 수 있어요.\""
                )

        if (
            next_batter
            and any(state["bases"])
            and state["outs"] < 2
        ):

            b, _ = _current_batter(
                state,
                ctx,
                off
            )

            bp = (
                0.72
                + (
                    (
                        b["contact"]
                        or 50
                    ) - 50
                ) * 0.002
                + off_fx.get(
                    "bunt_bonus",
                    0.0
                )
            )

            bunt_pct = round(
                min(
                    0.95,
                    bp
                ) * 100
            )

    # =====================================
    # 투수코치
    # =====================================

    if (
        us
        and def_ == us
        and state["pending"]
        in (
            "pitching",
            "duel_pitch"
        )
        and cur_pitcher
    ):

        if cur_pitcher[
            "stamina_pct"
        ] <= 25:

            coach_tip = (
                f"투수코치: "
                f"\"{cur_pitcher['name']}, "
                f"한계입니다. "
                f"공 끝이 무뎌졌어요.\""
            )

        elif (
            state["inning"] >= 9
            and not state[
                "h_used_cp"
                if us == "home"
                else "a_used_cp"
            ]
        ):

            coach_tip = (
                "투수코치: "
                "\"마무리 몸 다 풀렸습니다. "
                "언제든 콜만 주세요.\""
            )

    # =====================================
    # 박스스코어
    # =====================================

    def boxscore(side):

        tid = (
            state["home_id"]
            if side == "home"
            else state["away_id"]
        )

        rows = []

        for k, v in state.get(
            "acc",
            {}
        ).items():

            if v.get(
                "team_id"
            ) != tid:
                continue

            if not (
                v["hits"]
                or v["hr"]
                or v["rbi"]
                or v["sb"]
                or v["so"]
                or v["saves"]
            ):
                continue

            rows.append(v)

        rows.sort(
            key=lambda v: (
                v["hits"]
                + v["hr"] * 2
                + v["rbi"]
                + v["so"] * 0.4
            ),
            reverse=True
        )

        return rows[:8]

    # =====================================
    # 주루
    # =====================================

    send_runner = None

    if (
        state["pending"]
        == "running"
        and state.get(
            "send_runner"
        )
    ):

        send_runner = ctx[
            "players"
        ][
            state["send_runner"]
        ]["name"]

    # =====================================
    # 듀얼 상대
    # =====================================

    duel_info = None

    if (
        state["pending"]
        == "duel_bat"
        and cur_pitcher
    ):

        duel_info = {

            "kind":
                "bat",

            "vs":
                cur_pitcher["name"],

            "vs_ovr":
                cur_pitcher["overall"],
        }

    elif (
        state["pending"]
        == "duel_pitch"
        and next_batter
    ):

        duel_info = {

            "kind":
                "pitch",

            "vs":
                next_batter["name"],

            "vs_ovr":
                next_batter["overall"],
        }

    # =====================================
    # 모드 선택
    # =====================================

    mode_batters = []
    mode_sp = None

    if (
        state["pending"]
        == "mode_select"
        and us
    ):

        mode_batters = [

            {
                "id":
                    p["id"],

                "name":
                    p["name"],

                "overall":
                    p["overall"],
            }

            for p in ctx[us][
                "batters"
            ]
        ]

        if ctx[us]["sps"]:

            sp = ctx[us]["sps"][
                state["week"]
                % len(
                    ctx[us]["sps"]
                )
            ]

            mode_sp = {

                "name":
                    sp["name"],

                "overall":
                    sp["overall"],
            }

    # =====================================
    # 시점 전환
    # =====================================

    view_options = []

    if (
        us
        and state["pending"]
        not in (
            "finished",
            "mode_select"
        )
    ):

        for p in ctx[us][
            "batters"
        ]:

            view_options.append({

                "id":
                    p["id"],

                "label":
                    f"⚾ {p['name']} "
                    f"(타자 OVR "
                    f"{p['overall']})",
            })

        pitchers = (
            list(
                ctx[us]["sps"]
            )
            + list(
                ctx[us]["rps"]
            )
            + (
                [ctx[us]["cp"]]
                if ctx[us]["cp"]
                else []
            )
        )

        for p in pitchers:

            view_options.append({

                "id":
                    p["id"],

                "label":
                    f"🔥 {p['name']} "
                    f"(투수 OVR "
                    f"{p['overall']})",
            })

    # =====================================
    # 모멘텀
    # =====================================

    mo = state.get(
        "momentum",
        {
            "home": 0,
            "away": 0
        }
    )

    # =====================================
    # 저장
    # =====================================

    save = (
        sb.table("dynasty_save")
        .select("*")
        .eq("id", save_id)
        .execute()
        .data[0]
    )

    # =====================================
    # 렌더링
    # =====================================

    return render_template(

        "dynasty_live.html",

        save=save,

        live=live_row,

        state=state,

        home=home,

        away=away,

        user_team=(
            home
            if us == "home"
            else away
        ),

        mode=mode,

        base_names=base_names,

        cur_pitcher=cur_pitcher,

        next_batter=next_batter,

        can_steal=bool(
            state["bases"][0]
            and not state["bases"][1]
        ),

        away_lineup=
            lineup_view("away"),

        home_lineup=
            lineup_view("home"),

        my_lineup=(
            lineup_view(us)
            if us
            else []
        ),

        bench=bench,

        rps=rps,

        cp_available=bool(
            us
            and ctx[us]["cp"]
            and not state[
                "h_used_cp"
                if us == "home"
                else "a_used_cp"
            ]
        ),

        wp=win_prob(
            state,
            ctx
        ),

        box_home=
            boxscore("home"),

        box_away=
            boxscore("away"),

        send_runner=
            send_runner,

        duel_info=
            duel_info,

        mode_batters=
            mode_batters,

        mode_sp=
            mode_sp,

        steal_pct=
            steal_pct,

        bunt_pct=
            bunt_pct,

        coach_tip=
            coach_tip,

        crowd=
            state.get(
                "crowd",
                50
            ),

        op=
            state.get(
                "op",
                0
            ),

        momentum_my=(
            mo.get(
                us,
                0
            )
            if us
            else 0
        ),

        momentum_opp=(
            mo.get(
                "away"
                if us == "home"
                else "home",
                0
            )
            if us
            else 0
        ),

        is_clutch=(
            state["inning"] >= 7
            and abs(
                state["h_score"]
                -
                state["a_score"]
            ) <= 3
        ),

        mvp=state.get(
            "mvp"
        ),

        highlights=state.get(
            "scenes",
            []
        ),

        feats=state.get(
            "feats",
            []
        ),

        is_scenario=bool(
            state.get(
                "scenario"
            )
        ),

        view_options=
            view_options,

        pitch_speed=(
            max(
                600,
                1300
                - (
                    cur_pitcher[
                        "overall"
                    ]
                    or 50
                ) * 8
            )
            if cur_pitcher
            else 900
        ),

        # =================================
        # v3.2 추가
        # =================================

        bullpen_status=
            bullpen_status,

        defense_view=
            defense_view,
    )
