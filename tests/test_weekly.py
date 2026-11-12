import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import Database
from models import HeroCounters
from weekly_engine import aggregate_weekly_report, get_current_week_bounds
from weekly_renderer import render_weekly_card


def test_week_bounds_monday_to_sunday():
    # 2026-11-05 is a Thursday (weekday 3)
    dt = datetime(2026, 11, 5, 14, 30)
    start_dt, end_dt, period_title = get_current_week_bounds(dt)

    assert start_dt.weekday() == 0  # Monday
    assert start_dt.day == 2
    assert start_dt.month == 11

    assert end_dt.weekday() == 6    # Sunday
    assert end_dt.day == 8
    assert end_dt.month == 11
    assert "ноя" in period_title


def test_session_archiving_and_weekly_aggregation():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = tmp_file.name
    tmp_file.close()

    db = Database(tmp_db)
    user_id = 99
    btag = "TestPlayer-1234"
    db.upsert_user(user_id, btag)

    # Добавляем сессию 1 (Пятница 2026-11-06)
    fri_ts = int(datetime(2026, 11, 6, 20, 0).timestamp())
    deltas_1 = {
        "all-heroes": HeroCounters(games_played=5, games_won=4, games_lost=1),
        "reinhardt": HeroCounters(time_played=1800, eliminations=35, deaths=10, hero_damage_done=25000, games_played=3, games_won=3, games_lost=0),
        "zenyatta": HeroCounters(time_played=900, eliminations=18, deaths=4, hero_damage_done=8000, healing_done=9000, games_played=2, games_won=1, games_lost=1),
    }
    db.add_session_delta(user_id, "quickplay", deltas_1, fri_ts)
    sess_id_1 = db.archive_active_session(user_id, "quickplay", ended_at=fri_ts + 2700)
    assert sess_id_1 is not None

    # Добавляем сессию 2 (Суббота 2026-11-07)
    sat_ts = int(datetime(2026, 11, 7, 18, 0).timestamp())
    deltas_2 = {
        "all-heroes": HeroCounters(games_played=3, games_won=1, games_lost=2),
        "reinhardt": HeroCounters(time_played=1200, eliminations=20, deaths=8, hero_damage_done=16000, games_played=2, games_won=1, games_lost=1),
    }
    db.add_session_delta(user_id, "quickplay", deltas_2, sat_ts)
    sess_id_2 = db.archive_active_session(user_id, "quickplay", ended_at=sat_ts + 1200)
    assert sess_id_2 is not None

    # Агрегируем отчет за эту неделю (на дату воскресенья 2026-11-08)
    sun_ts = int(datetime(2026, 11, 8, 22, 0).timestamp())
    report = aggregate_weekly_report(user_id, "quickplay", db, now_ts=sun_ts)

    assert report.total_matches == 8
    assert report.total_wins == 5
    assert report.total_losses == 3
    assert report.winrate_pct == round((5 / 8) * 100)
    assert report.sessions_count == 2
    assert report.player_name == "TestPlayer"

    # Проверка распределения по дням
    fri_day = next(d for d in report.days if d.day_name == "ПТ")
    sat_day = next(d for d in report.days if d.day_name == "СБ")
    assert fri_day.games_played == 5
    assert fri_day.games_won == 4
    assert sat_day.games_played == 3
    assert sat_day.games_won == 1

    # Проверка топ героев и сохраненного счета побед-поражений
    assert len(report.top_heroes) >= 2
    top_h = report.top_heroes[0]
    assert top_h.hero_key == "reinhardt"
    assert top_h.time_sec == 3000
    assert top_h.games_won == 4  # 3 + 1
    assert top_h.games_lost == 1 # 0 + 1
    assert "4-1" in report.hero_of_the_week

    # Проверка генерации PNG без исключений
    png_bytes = render_weekly_card(report)
    assert len(png_bytes) > 10000

    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass



def test_db_last_weekly_sent_tracking():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = tmp_file.name
    tmp_file.close()

    db = Database(tmp_db)
    user_id = 12345
    db.upsert_user(user_id, "Tracker-123")

    # По умолчанию пустая строка
    assert db.get_user_last_weekly(user_id) == ""

    # Устанавливаем ключ недели
    db.set_user_last_weekly(user_id, "2026-11-09")
    assert db.get_user_last_weekly(user_id) == "2026-11-09"

    # Обновляем на следующую неделю
    db.set_user_last_weekly(user_id, "2026-11-16")
    assert db.get_user_last_weekly(user_id) == "2026-11-16"

    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass


def test_best_day_only_losses_not_selected_and_dash_score():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = tmp_file.name
    tmp_file.close()

    db = Database(tmp_db)
    user_id = 777
    db.upsert_user(user_id, "LossUser-1234")

    # Игрок сыграл только в четверг: 0 побед, 2 поражения
    thu_ts = int(datetime(2026, 11, 5, 21, 0).timestamp())
    deltas = {
        "all-heroes": HeroCounters(games_played=2, games_won=0, games_lost=2),
        "sojourn": HeroCounters(time_played=900, hero_damage_done=8000, games_played=0, games_won=0, games_lost=0),
    }
    db.add_session_delta(user_id, "quickplay", deltas, thu_ts)
    db.archive_active_session(user_id, "quickplay", ended_at=thu_ts + 900)

    report = aggregate_weekly_report(user_id, "quickplay", db, now_ts=thu_ts)
    # День без побед (0-2) не должен выбираться как лучший день
    assert report.best_day_title == "—"
    assert not any(d.is_best_day for d in report.days)

    # Герой недели без зафиксированных матчей отображает время вместо "0-0"
    assert "0-0" not in report.hero_of_the_week
    assert "15 мин" in report.hero_of_the_week

    # Рендер не должен падать
    png = render_weekly_card(report)
    assert len(png) > 10000

    import gc
    del db
    gc.collect()
    try:
        os.remove(tmp_db)
    except PermissionError:
        pass



