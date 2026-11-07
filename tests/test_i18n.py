import pytest
from i18n import (
    t,
    get_hero_name,
    format_time_duration,
    format_matches_caption,
    LANG_RU,
    LANG_EN,
)
from db import Database
from models import SessionCardData, WeeklyReportData, DailyMatchStats, HeroWeeklyStats
from renderer import render_session_card
from weekly_renderer import render_weekly_card


def test_i18n_translation_keys():
    assert t("start_greeting", lang=LANG_RU) != ""
    assert t("start_greeting", lang=LANG_EN) != ""
    assert "BattleTag" in t("start_greeting", lang=LANG_RU)
    assert "BattleTag" in t("start_greeting", lang=LANG_EN)


def test_i18n_hero_names():
    assert get_hero_name("ana", lang=LANG_RU) == "Ана"
    assert get_hero_name("ana", lang=LANG_EN) == "Ana"
    assert get_hero_name("wrecking-ball", lang=LANG_RU) == "Таран"
    assert get_hero_name("wrecking-ball", lang=LANG_EN) == "Wrecking Ball"


def test_i18n_duration_formatting():
    # format_time_duration takes seconds
    assert format_time_duration(65 * 60, lang=LANG_RU) == "1 ч 5 мин"
    assert format_time_duration(65 * 60, lang=LANG_EN) == "1 h 5 min"
    assert format_time_duration(40 * 60, lang=LANG_RU) == "40 мин"
    assert format_time_duration(40 * 60, lang=LANG_EN) == "40 min"


def test_db_language_preference(tmp_path):
    test_db_path = str(tmp_path / "test_ow.db")
    db = Database(test_db_path)
    
    # Check default before user inserted
    assert db.get_user_language(12345) == "ru"
    
    # Upsert with en
    db.upsert_user(12345, "Battletag-123", "pc", language="en")
    assert db.get_user_language(12345) == "en"
    
    # Toggle to ru
    db.set_user_language(12345, "ru")
    assert db.get_user_language(12345) == "ru"
    
    user = db.get_user(12345)
    assert user is not None
    # user = (user_id, battletag, platform, last_summary_updated_at, avatar_url, language)
    assert user[5] == "ru"


def test_render_cards_en():
    session_data = SessionCardData(
        player_name="Player",
        gamemode="quickplay",
        mode_title="Quick Play",
        duration_min=45,
        games_played=5,
        games_won=3,
        games_lost=2,
        total_eliminations=20,
        total_deaths=8,
        kd_val=2.5,
        kd_status="better",
        kd_diff_pct=15,
        role_blocks=[],
        other_heroes=[],
        language="en",
    )
    png_session = render_session_card(session_data)
    assert len(png_session) > 1000

    weekly_data = WeeklyReportData(
        player_name="Player",
        gamemode="quickplay",
        mode_title="Quick Play",
        period_title="Week 26 Oct — 1 Nov",
        total_matches=10,
        total_wins=6,
        total_losses=4,
        winrate_pct=60,
        total_time_sec=3600,
        sessions_count=2,
        days=[DailyMatchStats("Mon", "26.10", 5, 3, 2, 1800, 60)],
        top_heroes=[HeroWeeklyStats("tracer", "Tracer", "damage", 1800, 5, 3, 2, 20.0, 5.0, 8000, 0)],
        best_day_title="Monday · 3-2",
        hero_of_the_week="Tracer · 3-2",
        longest_session_str="5 matches · 30 min",
        language="en",
    )
    png_weekly = render_weekly_card(weekly_data)
    assert len(png_weekly) > 1000
