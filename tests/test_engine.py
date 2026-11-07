import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from db import Database
from engine import (
    build_metric_scale,
    combine_two_verdicts,
    compute_delta,
    evaluate_hero_session,
    select_output_metric_type,
    select_role_heroes_and_footer,
    update_bucket_with_delta,
)
from models import BucketState, CareerSnapshot, HeroCounters, ObservationRecord
from provider import parse_raw_career_json


def test_missing_keys_default_to_zero_and_delta():
    raw_prev = {"sojourn": {"game": {"time_played": 1000}}}
    raw_curr = {
        "sojourn": {
            "game": {"time_played": 1600, "games_played": 1, "games_won": 1},
            "combat": {"deaths": 5, "hero_damage_done": 8500},
        }
    }
    s1 = parse_raw_career_json(raw_prev, taken_at=100)
    s2 = parse_raw_career_json(raw_curr, taken_at=700)

    assert s1.heroes["sojourn"].deaths == 0.0
    assert s1.heroes["sojourn"].healing_done == 0.0

    deltas, is_reset = compute_delta(s1, s2)
    assert not is_reset
    assert deltas["sojourn"].time_played == 600.0
    assert deltas["sojourn"].deaths == 5.0
    assert deltas["sojourn"].hero_damage_done == 8500.0
    assert deltas["sojourn"].healing_done == 0.0


def test_negative_delta_triggers_reset():
    s1 = CareerSnapshot(taken_at=100, heroes={"sojourn": HeroCounters(time_played=1000, deaths=10)})
    s2 = CareerSnapshot(taken_at=200, heroes={"sojourn": HeroCounters(time_played=950, deaths=10)})
    deltas, is_reset = compute_delta(s1, s2)
    assert is_reset is True
    assert deltas is None


def test_bucket_closes_max_one_observation_per_delta_and_carries_remainder():
    # Накопление 750 сек и 15 смертей -> закрывается 1 наблюдение (12.0 смертей/10м), остаток 150 сек и 3.0 смерти
    bucket = BucketState(time_sec=150.0, deaths=3.0, damage=1500.0, healing=0.0)
    delta = HeroCounters(time_played=600.0, deaths=12.0, hero_damage_done=6000.0)

    new_b, obs = update_bucket_with_delta(bucket, delta, "damage", obs_sec=600, now_ts=123)
    assert obs is not None
    assert obs.deaths_10m == 12.0
    assert obs.output_10m == 6000.0
    assert round(new_b.time_sec, 2) == 150.0
    assert round(new_b.deaths, 2) == 3.0
    assert round(new_b.damage, 2) == 1500.0

    # Правило 2: если прилетела огромная дельта 1300 сек, закрывается ТОЛЬКО ОДНО наблюдение, остаток 700 сек ждёт следующей дельты
    b2, obs2 = update_bucket_with_delta(BucketState(), HeroCounters(time_played=1300.0, deaths=13.0, hero_damage_done=13000.0), "damage", obs_sec=600)
    assert obs2 is not None
    assert round(b2.time_sec, 1) == 700.0


def test_support_without_healing_uses_damage():
    sombra_supp = HeroCounters(time_played=3600, hero_damage_done=45000, healing_done=0)
    ana_supp = HeroCounters(time_played=3600, hero_damage_done=15000, healing_done=55000)
    assert select_output_metric_type("support", sombra_supp) == "damage"
    assert select_output_metric_type("support", ana_supp) == "healing"


def test_verdict_provided_as_is_with_scales_and_metrics():
    obs_7 = [ObservationRecord(output_10m=8000, deaths_10m=5.0) for _ in range(7)]
    sess_cnt = HeroCounters(time_played=720, deaths=6, hero_damage_done=9600)
    career_cnt = HeroCounters(time_played=36000, deaths=300, hero_damage_done=480000)

    block_few_obs = evaluate_hero_session(
        role="damage", hero_key="sojourn", hero_name="Соджорн", is_fallback=False,
        session_counters=sess_cnt, observations=obs_7, career_counters=career_cnt,
        bucket_time_sec=180, obs_sec=600, min_obs=8
    )
    # По новой логике: инфа предоставляется как есть со шкалами и вердиктом
    assert block_few_obs.has_verdict is True
    assert block_few_obs.verdict_text in ("лучше обычного", "как обычно", "хуже обычного")
    assert block_few_obs.output_scale is not None
    assert block_few_obs.deaths_scale is not None

    # Сессия меньше 10 минут (360 сек = 6 мин) — тоже выводится как есть
    obs_10 = [ObservationRecord(output_10m=8000, deaths_10m=5.0) for _ in range(10)]
    short_cnt = HeroCounters(time_played=360, deaths=3, hero_damage_done=5000)
    block_short = evaluate_hero_session(
        role="damage", hero_key="sojourn", hero_name="Соджорн", is_fallback=False,
        session_counters=short_cnt, observations=obs_10, career_counters=career_cnt,
        obs_sec=600, min_obs=8
    )
    assert block_short.has_verdict is True
    assert block_short.time_min == 6
    assert block_short.output_scale is not None


def test_scale_colors_directions_zero_norm_and_clamping():
    history = [4.0, 4.5, 4.8, 5.0, 5.0, 5.2, 5.5, 6.0]  # норма = 5.0, полоса [4.725 .. 5.275]

    # Внутри полосы -> серая точка и "как обычно"
    sc_usual = build_metric_scale("deaths", 4.9, history)
    assert sc_usual.color == "gray"
    assert sc_usual.status == "usual"
    assert sc_usual.label_text.startswith("как обычно")
    assert 0.30 <= sc_usual.pos_norm <= 0.70

    # Для смертей МЕНЬШЕ = ЛУЧШЕ -> зелёная точка СПРАВА (pos_norm > 0.70)
    sc_better_deaths = build_metric_scale("deaths", 3.5, history)
    assert sc_better_deaths.color == "green"
    assert sc_better_deaths.status == "better"
    assert sc_better_deaths.pos_norm > 0.70
    assert "реже умираешь" in sc_better_deaths.label_text

    # Для смертей БОЛЬШЕ = ХУЖЕ -> красная точка СЛЕВА (pos_norm < 0.30) + обрезка со стрелкой на краю
    sc_worse_deaths = build_metric_scale("deaths", 9.5, history)
    assert sc_worse_deaths.color == "red"
    assert sc_worse_deaths.status == "worse"
    assert sc_worse_deaths.pos_norm == 0.0
    assert sc_worse_deaths.clamped == "left"
    assert "чаще умираешь" in sc_worse_deaths.label_text

    # Если норма == 0 -> шкала скрыта
    sc_zero = build_metric_scale("damage", 500, [0.0] * 8)
    assert sc_zero.show_scale is False
    assert sc_zero.pct_diff is None


def test_combine_two_verdicts_four_cases():
    assert combine_two_verdicts("better", "better") == "лучше обычного"
    assert combine_two_verdicts("better", "usual") == "лучше обычного"
    assert combine_two_verdicts("worse", "worse") == "хуже обычного"
    assert combine_two_verdicts("usual", "worse") == "хуже обычного"
    assert combine_two_verdicts("usual", "usual") == "как обычно"
    assert combine_two_verdicts("better", "worse") == "по-разному"
    assert combine_two_verdicts("worse", "better") == "по-разному"


def test_role_fallback_and_footer_selection():
    sess_heroes = {
        "sojourn": HeroCounters(time_played=300),    # 5 мин (предпочитаемый ДД)
        "ashe": HeroCounters(time_played=900),       # 15 мин (другой ДД)
        "ana": HeroCounters(time_played=720),        # 12 мин (предпочитаемый саппорт)
        "winston": HeroCounters(time_played=420),    # 7 мин (танк)
        "torbjorn": HeroCounters(time_played=90),    # 1.5 мин (< 2 мин -> уйдёт в подвал)
    }
    prefs = {"damage": "sojourn", "support": "ana", "tank": "zarya"}
    roles = {"sojourn": "damage", "ashe": "damage", "ana": "support", "winston": "tank", "zarya": "tank", "torbjorn": "damage"}
    names = {"sojourn": "Соджорн", "ashe": "Эш", "ana": "Ана", "winston": "Уинстон", "zarya": "Заря", "torbjorn": "Торбьорн"}

    chosen, footer = select_role_heroes_and_footer(sess_heroes, prefs, roles, names, obs_sec=600, max_blocks=4)

    # Все 4 героя с временем >= 120 сек получают карточки
    chosen_keys = [c[1] for c in chosen]
    assert "ashe" in chosen_keys
    assert "ana" in chosen_keys
    assert "winston" in chosen_keys
    assert "sojourn" in chosen_keys
    assert len(chosen) == 4

    # Торбьорн (< 120 сек) уходит в подвал
    footer_names = [item.hero_name for item in footer]
    assert "Торбьорн" in footer_names


def test_multi_hero_support_session_all_selected_as_is():
    # Ситуация пользователя: сыграно 20 минут на саппортах, частая смена героев
    sess_heroes = {
        "zenyatta": HeroCounters(time_played=420, eliminations=8, deaths=3, healing_done=4200),  # 7 мин
        "ana": HeroCounters(time_played=360, eliminations=5, deaths=2, healing_done=3900),       # 6 мин
        "jetpack-cat": HeroCounters(time_played=240, eliminations=3, deaths=2),                  # 4 мин
        "juno": HeroCounters(time_played=180, eliminations=2, deaths=1),                         # 3 мин
    }
    prefs = {"support": "ana"}
    roles = {"zenyatta": "support", "ana": "support", "jetpack-cat": "support", "juno": "support"}
    names = {"zenyatta": "Дзенъятта", "ana": "Ана", "jetpack-cat": "Реактивная Киса", "juno": "Юнона"}

    chosen, footer = select_role_heroes_and_footer(sess_heroes, prefs, roles, names, max_blocks=4)

    # Все 4 саппорта отбираются в блоки
    chosen_keys = [c[1] for c in chosen]
    assert chosen_keys == ["zenyatta", "ana", "jetpack-cat", "juno"]

    # Проверяем, что Ана (предпочитаемый саппорт) без пометки "не основной"
    ana_block = [c for c in chosen if c[1] == "ana"][0]
    assert ana_block[2] is False  # is_fallback=False

    zen_block = [c for c in chosen if c[1] == "zenyatta"][0]
    assert zen_block[2] is True   # is_fallback=True ("не основной")


def test_evaluate_hero_session_short_time_provided_as_is():
    # Проверяем, что при времени < 10 мин данные предоставляются как есть со шкалами
    h_cnt = HeroCounters(time_played=420, eliminations=8, deaths=3, healing_done=4200)
    career_cnt = HeroCounters(time_played=45000, eliminations=700, deaths=350, healing_done=500000)

    block = evaluate_hero_session(
        role="support",
        hero_key="zenyatta",
        hero_name="Дзенъятта",
        is_fallback=False,
        session_counters=h_cnt,
        observations=[],
        career_counters=career_cnt,
    )

    assert block.has_verdict is True
    assert block.verdict_text in ("лучше обычного", "как обычно", "хуже обычного", "по-разному")
    assert block.output_scale is not None
    assert block.deaths_scale is not None
    assert block.output_scale.session_val == 6000.0  # 4200 * (600 / 420)
    assert block.deaths_scale.session_val == round(3 * (600 / 420), 1)


def test_session_storage_and_timeout_cleanup():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = tmp_file.name
    tmp_file.close()
    db = Database(tmp_db)
    deltas = {
        "all-heroes": HeroCounters(games_played=2, games_won=1, games_lost=1),
        "sojourn": HeroCounters(time_played=800, deaths=6, hero_damage_done=12000),
    }
    db.add_session_delta(user_id=42, gamemode="quickplay", deltas=deltas, now_ts=1000)
    active = db.get_active_session(42, "quickplay")
    assert active is not None
    meta, heroes = active
    assert meta["games_played"] == 2
    assert heroes["sojourn"].time_played == 800

    # Симулируем закрытие по таймауту (now_ts - last_change_at >= SESSION_TIMEOUT_SEC)
    assert (1000 + config.SESSION_TIMEOUT_SEC) - meta["last_change_at"] >= config.SESSION_TIMEOUT_SEC
    db.clear_active_session(42, "quickplay")
    assert db.get_active_session(42, "quickplay") is None
    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass


def test_competitive_ranks_parsing_and_db_storage():
    import json
    from engine import extract_competitive_ranks
    raw_comp = {
        "pc": {
            "season": 25,
            "tank": {"division": "diamond", "tier": 3},
            "damage": {"division": "platinum", "tier": 1},
            "support": {"division": "gold", "tier": 2},
        }
    }
    ranks = extract_competitive_ranks(raw_comp, "pc", session_won=2, session_lost=0)
    assert ranks is not None
    assert len(ranks) == 3
    assert ranks[0].role == "tank"
    assert ranks[0].division_title == "Алмаз"
    assert ranks[0].tier == 3
    assert "2-0" in ranks[0].delta_text

    assert ranks[1].role == "damage"
    assert ranks[1].division_title == "Платина"
    assert ranks[1].tier == 1

    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = tmp_file.name
    tmp_file.close()
    db = Database(tmp_db)
    db.upsert_user(99, "Tester-1234")
    db.update_user_ranks(99, json.dumps(raw_comp))
    loaded = db.get_user_ranks(99)
    assert loaded["pc"]["tank"]["division"] == "diamond"

    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass
