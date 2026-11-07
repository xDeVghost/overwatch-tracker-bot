"""
Скрипт генерации демонстрационных карточек:
1) preview_session.png — карточка быстрой игры (3 шкалы на героя, интерактивный K/D)
2) preview_competitive.png — соревновательный режим с графиком прогресса рангов
3) preview_weekly.png — обновленный недельный отчет с гистограммой
"""
from models import (
    DailyMatchStats,
    HeroCardBlock,
    HeroWeeklyStats,
    MetricScaleResult,
    OtherHeroItem,
    RoleRankProgress,
    SessionCardData,
    WeeklyReportData,
)
from renderer import render_session_card
from weekly_renderer import render_weekly_card


def generate_previews():
    print("1. Генерация карточки сессии (Быстрая игра)...")
    demo_session = SessionCardData(
        player_name="Player",
        gamemode="quickplay",
        mode_title="Быстрая игра",
        duration_min=48,
        games_played=6,
        games_won=3,
        games_lost=3,
        total_eliminations=26,
        total_deaths=11,
        kd_val=2.36,
        kd_status="better",
        kd_diff_pct=18,
        role_blocks=[
            HeroCardBlock(
                role="damage",
                role_title="УРОН",
                hero_key="sojourn",
                hero_name="Соджорн",
                time_min=18,
                is_fallback=False,
                has_verdict=True,
                verdict_text="лучше обычного",
                output_scale=MetricScaleResult(
                    metric_type="damage",
                    title="Урон",
                    session_val=9590,
                    norm_val=8500,
                    band_low=8100,
                    band_high=8950,
                    status="better",
                    color="green",
                    pct_diff=13,
                    label_text="на 13% больше урона",
                    pos_norm=0.82,
                    clamped=None,
                    show_scale=True,
                ),
                deaths_scale=MetricScaleResult(
                    metric_type="deaths",
                    title="Смерти",
                    session_val=4.7,
                    norm_val=4.9,
                    band_low=4.4,
                    band_high=5.5,
                    status="usual",
                    color="gray",
                    pct_diff=-4,
                    label_text="как обычно (−4%)",
                    pos_norm=0.58,
                    clamped=None,
                    show_scale=True,
                ),
                eliminations_scale=MetricScaleResult(
                    metric_type="eliminations",
                    title="Убийства",
                    session_val=22.4,
                    norm_val=18.5,
                    band_low=16.8,
                    band_high=20.2,
                    status="better",
                    color="green",
                    pct_diff=21,
                    label_text="на 21% больше убийств",
                    pos_norm=0.86,
                    clamped=None,
                    show_scale=True,
                ),
            ),
            HeroCardBlock(
                role="support",
                role_title="ПОДДЕРЖКА",
                hero_key="zenyatta",
                hero_name="Дзенъятта",
                time_min=14,
                is_fallback=True,
                has_verdict=True,
                verdict_text="хуже обычного",
                output_scale=MetricScaleResult(
                    metric_type="healing",
                    title="Хил",
                    session_val=7028,
                    norm_val=7200,
                    band_low=6700,
                    band_high=7650,
                    status="usual",
                    color="gray",
                    pct_diff=-2,
                    label_text="как обычно (−2%)",
                    pos_norm=0.43,
                    clamped=None,
                    show_scale=True,
                ),
                deaths_scale=MetricScaleResult(
                    metric_type="deaths",
                    title="Смерти",
                    session_val=7.9,
                    norm_val=5.2,
                    band_low=4.6,
                    band_high=5.8,
                    status="worse",
                    color="red",
                    pct_diff=52,
                    label_text="на 52% чаще умираешь",
                    pos_norm=0.0,
                    clamped="left",
                    show_scale=True,
                ),
                eliminations_scale=MetricScaleResult(
                    metric_type="eliminations",
                    title="Убийства",
                    session_val=13.2,
                    norm_val=15.0,
                    band_low=13.8,
                    band_high=16.2,
                    status="worse",
                    color="red",
                    pct_diff=-12,
                    label_text="на 12% меньше убийств",
                    pos_norm=0.22,
                    clamped=None,
                    show_scale=True,
                ),
            ),
        ],
        other_heroes=[
            OtherHeroItem("juno", "Юнона", 7, 3),
            OtherHeroItem("illari", "Иллари", 6, 2),
            OtherHeroItem("jetpack-cat", "Реактивная Киса", 3, 1),
        ],
    )

    png_sess = render_session_card(demo_session)
    with open("preview_session.png", "wb") as f:
        f.write(png_sess)
    print("-> Сохранено в preview_session.png")

    print("\n2. Генерация карточки Соревновательного режима (с графиком прогресса рангов)...")
    comp_ranks = [
        RoleRankProgress(
            role="tank",
            role_title="ТАНК",
            division="diamond",
            division_title="Алмаз",
            tier=3,
            progress_pct=65,
            delta_text="▲ 2-0 в сессии",
        ),
        RoleRankProgress(
            role="damage",
            role_title="УРОН",
            division="platinum",
            division_title="Платина",
            tier=1,
            progress_pct=84,
            delta_text="▲ +1 ранг",
        ),
        RoleRankProgress(
            role="support",
            role_title="ПОДДЕРЖКА",
            division="gold",
            division_title="Золото",
            tier=2,
            progress_pct=42,
            delta_text="1-1 в сессии",
        ),
    ]

    demo_comp = SessionCardData(
        player_name="Player",
        gamemode="competitive",
        mode_title="Соревновательный",
        duration_min=54,
        games_played=7,
        games_won=5,
        games_lost=2,
        total_eliminations=38,
        total_deaths=14,
        kd_val=2.71,
        kd_status="better",
        kd_diff_pct=26,
        rank_progress=comp_ranks,
        role_blocks=[
            HeroCardBlock(
                role="tank",
                role_title="ТАНК",
                hero_key="reinhardt",
                hero_name="Райнхардт",
                time_min=24,
                is_fallback=False,
                has_verdict=True,
                verdict_text="лучше обычного",
                output_scale=MetricScaleResult(
                    metric_type="damage",
                    title="Урон",
                    session_val=12400,
                    norm_val=10800,
                    band_low=10200,
                    band_high=11400,
                    status="better",
                    color="green",
                    pct_diff=15,
                    label_text="на 15% больше урона",
                    pos_norm=0.85,
                    clamped=None,
                    show_scale=True,
                ),
                deaths_scale=MetricScaleResult(
                    metric_type="deaths",
                    title="Смерти",
                    session_val=5.2,
                    norm_val=5.8,
                    band_low=5.1,
                    band_high=6.5,
                    status="usual",
                    color="gray",
                    pct_diff=-10,
                    label_text="как обычно (−10%)",
                    pos_norm=0.62,
                    clamped=None,
                    show_scale=True,
                ),
                eliminations_scale=MetricScaleResult(
                    metric_type="eliminations",
                    title="Убийства",
                    session_val=24.1,
                    norm_val=20.0,
                    band_low=18.2,
                    band_high=21.8,
                    status="better",
                    color="green",
                    pct_diff=20,
                    label_text="на 20% больше убийств",
                    pos_norm=0.88,
                    clamped=None,
                    show_scale=True,
                ),
            )
        ],
        other_heroes=[
            OtherHeroItem("sigma", "Сигма", 12, 5),
            OtherHeroItem("winston", "Уинстон", 10, 4),
        ],
    )
    png_comp = render_session_card(demo_comp)
    with open("preview_competitive.png", "wb") as f:
        f.write(png_comp)
    print("-> Сохранено в preview_competitive.png")

    print("\n3. Генерация обновленного недельного отчета (без блока 10-мин средних)...")
    days = [
        DailyMatchStats("ПН", "26.10", 3, 2, 1, 1080, 67),
        DailyMatchStats("ВТ", "27.10", 4, 3, 1, 1740, 75),
        DailyMatchStats("СР", "28.10", 0, 0, 0, 0, 0),
        DailyMatchStats("ЧТ", "29.10", 3, 1, 2, 1740, 33),
        DailyMatchStats("ПТ", "30.10", 14, 8, 6, 6000, 57, is_best_day=True),
        DailyMatchStats("СБ", "31.10", 0, 0, 0, 0, 0),
        DailyMatchStats("ВС", "01.11", 0, 0, 0, 0, 0),
    ]
    heroes = [
        HeroWeeklyStats("reinhardt", "Райнхардт", "tank", 2160, 4, 3, 1, 18.5, 8.2, 11502, 0),
        HeroWeeklyStats("zenyatta", "Дзенъятта", "support", 1560, 4, 3, 1, 23.7, 4.6, 7874, 7819),
        HeroWeeklyStats("roadhog", "Турбосвин", "tank", 1380, 3, 1, 2, 23.0, 5.5, 10105, 6891),
        HeroWeeklyStats("winston", "Уинстон", "tank", 1620, 2, 1, 1, 25.0, 4.0, 11367, 3223),
        HeroWeeklyStats("doomfist", "Кулак Смерти", "tank", 1260, 2, 0, 2, 18.2, 10.7, 7377, 1757),
    ]
    demo_weekly = WeeklyReportData(
        player_name="Player",
        gamemode="quickplay",
        mode_title="Быстрая игра",
        period_title="Неделя 26 окт — 1 ноя",
        total_matches=24,
        total_wins=12,
        total_losses=12,
        winrate_pct=50,
        total_time_sec=10620,
        sessions_count=4,
        days=days,
        top_heroes=heroes,
        best_day_title="пятница · 8-6",
        hero_of_the_week="Райнхардт · 3-1",
        longest_session_str="14 матчей · 1 ч 40 мин",
    )

    png_week = render_weekly_card(demo_weekly)
    with open("preview_weekly.png", "wb") as f:
        f.write(png_week)
    print("-> Сохранено в preview_weekly.png")
    print("\nВсе 3 карточки успешно сгенерированы!")


if __name__ == "__main__":
    generate_previews()
