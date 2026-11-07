from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple

from db import Database
from i18n import (
    DAY_FULL_NAMES,
    DAY_NAMES,
    MODE_TITLES,
    MONTH_NAMES,
    format_matches_caption,
    format_time_duration,
)
from models import (
    DailyMatchStats,
    HeroCounters,
    HeroWeeklyStats,
    WeeklyReportData,
)


def get_current_week_bounds(now_dt: Optional[datetime] = None, lang: str = "ru") -> Tuple[datetime, datetime, str]:
    """
    Возвращает (start_datetime, end_datetime, title_string).
    Календарная неделя: с понедельника 00:00:00 по воскресенье 23:59:59.
    """
    if now_dt is None:
        now_dt = datetime.now()

    # weekday(): Понедельник = 0, Воскресенье = 6
    start_dt = (now_dt - timedelta(days=now_dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)

    months = MONTH_NAMES.get(lang, MONTH_NAMES["ru"])
    m1 = months[start_dt.month]
    m2 = months[end_dt.month]
    prefix = "Week" if lang == "en" else "Неделя"
    if m1 == m2:
        period_str = f"{prefix} {start_dt.day} — {end_dt.day} {m1}"
    else:
        period_str = f"{prefix} {start_dt.day} {m1} — {end_dt.day} {m2}"

    return start_dt, end_dt, period_str


def aggregate_weekly_report(
    user_id: int,
    gamemode: str,
    db: Database,
    now_ts: Optional[int] = None,
    lang: str = "ru",
) -> WeeklyReportData:
    """
    Агрегирует данные за текущую календарную неделю для указанного пользователя и режима.
    """
    now_dt = datetime.fromtimestamp(now_ts) if now_ts else datetime.now()
    start_dt, end_dt, period_title = get_current_week_bounds(now_dt, lang=lang)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # 1. Получаем историю сессий за эту неделю
    history_sessions = db.get_history_sessions_since(user_id, since_ts=start_ts, gamemode=gamemode)

    # 2. Добавляем активную сессию, если она идет прямо сейчас
    active = db.get_active_session(user_id, gamemode)
    all_sessions: List[Tuple[dict, Dict[str, HeroCounters]]] = list(history_sessions)
    if active:
        act_meta, act_heroes = active
        if act_meta["started_at"] >= start_ts:
            all_sessions.append((
                {
                    "id": -1,
                    "gamemode": gamemode,
                    "started_at": act_meta["started_at"],
                    "ended_at": act_meta["last_change_at"],
                    "duration_sec": sum(c.time_played for c in act_heroes.values()),
                    "games_played": act_meta["games_played"],
                    "games_won": act_meta["games_won"],
                    "games_lost": act_meta["games_lost"],
                    "eliminations": sum(c.eliminations for c in act_heroes.values()),
                    "deaths": sum(c.deaths for c in act_heroes.values()),
                    "damage": sum(c.hero_damage_done for c in act_heroes.values()),
                    "healing": sum(c.healing_done for c in act_heroes.values()),
                },
                act_heroes,
            ))

    # Получаем каталог героев и пользователя
    roles_map, names_map = db.get_heroes_maps(lang=lang)
    user_row = db.get_user(user_id)
    default_player_name = "Player" if lang == "en" else "Игрок"
    player_name = user_row[1].split("-")[0].split("#")[0] if user_row else default_player_name
    avatar_url = user_row[4] if user_row and len(user_row) > 4 else ""
    mode_title = MODE_TITLES.get(lang, MODE_TITLES["ru"]).get(gamemode, "Quick Play" if lang == "en" else "Быстрая игра")

    # Инициализируем дни недели (ПН .. ВС или MON .. SUN)
    day_abbrs = DAY_NAMES.get(lang, DAY_NAMES["ru"])
    day_fulls = DAY_FULL_NAMES.get(lang, DAY_FULL_NAMES["ru"])
    days_data: List[DailyMatchStats] = []
    for d_idx in range(7):
        day_date = start_dt + timedelta(days=d_idx)
        days_data.append(
            DailyMatchStats(
                day_name=day_abbrs[d_idx],
                date_str=f"{day_date.day:02d}.{day_date.month:02d}",
                games_played=0,
                games_won=0,
                games_lost=0,
                time_sec=0.0,
                winrate_pct=0,
                is_best_day=False,
            )
        )

    tot_matches = 0
    tot_wins = 0
    tot_losses = 0
    tot_time_sec = 0.0
    tot_elim = 0.0
    tot_deaths = 0.0
    tot_dmg = 0.0
    tot_heal = 0.0

    # Агрегация по героям за неделю
    hero_totals: Dict[str, HeroCounters] = {}
    longest_session_games = 0
    longest_session_time = 0.0

    for s_meta, s_heroes in all_sessions:
        s_gp = s_meta["games_played"]
        s_gw = s_meta["games_won"]
        s_gl = s_meta["games_lost"]
        s_dur = s_meta["duration_sec"]

        tot_matches += s_gp
        tot_wins += s_gw
        tot_losses += s_gl
        tot_time_sec += s_dur

        # Сессия с наибольшим числом матчей и временем
        if (s_gp, s_dur) > (longest_session_games, longest_session_time):
            longest_session_games = s_gp
            longest_session_time = s_dur

        # Относим к дню недели по started_at (начало игровой сессии)
        s_dt = datetime.fromtimestamp(s_meta["started_at"])
        w_idx = s_dt.weekday()
        if 0 <= w_idx < 7:
            day_obj = days_data[w_idx]
            day_obj.games_played += s_gp
            day_obj.games_won += s_gw
            day_obj.games_lost += s_gl
            day_obj.time_sec += s_dur

        # Суммируем показатели героев
        for hk, cnt in s_heroes.items():
            if hk == "all-heroes":
                continue
            tot_elim += cnt.eliminations
            tot_deaths += cnt.deaths
            tot_dmg += cnt.hero_damage_done
            tot_heal += cnt.healing_done

            if hk not in hero_totals:
                hero_totals[hk] = HeroCounters()
            h_acc = hero_totals[hk]
            h_acc.time_played += cnt.time_played
            h_acc.eliminations += cnt.eliminations
            h_acc.deaths += cnt.deaths
            h_acc.hero_damage_done += cnt.hero_damage_done
            h_acc.healing_done += cnt.healing_done
            h_acc.games_played += cnt.games_played
            h_acc.games_won += cnt.games_won
            h_acc.games_lost += cnt.games_lost

    # Расчет винрейтов по дням и поиск лучшего дня
    best_day_idx = -1
    best_day_score = -1.0
    for i, d in enumerate(days_data):
        decided = d.games_won + d.games_lost
        if decided > 0:
            d.winrate_pct = round((d.games_won / decided) * 100)
            # Оценка полезности дня: винрейт + вес побед
            day_score = d.winrate_pct * 10.0 + d.games_won * 2.0
            if day_score > best_day_score:
                best_day_score = day_score
                best_day_idx = i

    best_day_title = "—"
    if best_day_idx >= 0 and days_data[best_day_idx].games_played > 0:
        days_data[best_day_idx].is_best_day = True
        bd = days_data[best_day_idx]
        best_day_title = f"{day_fulls[best_day_idx]} · {bd.games_won}-{bd.games_lost}"

    # Топ героев недели
    top_heroes_list: List[HeroWeeklyStats] = []
    sorted_heroes = sorted(hero_totals.items(), key=lambda x: x[1].time_played, reverse=True)
    hero_of_the_week_title = "—"

    for idx, (hk, h_cnt) in enumerate(sorted_heroes[:5]):
        h_time = h_cnt.time_played
        factor = (600.0 / h_time) if h_time > 0 else 0.0
        h_role = roles_map.get(hk, "damage")
        h_name = names_map.get(hk, hk.capitalize())

        top_heroes_list.append(
            HeroWeeklyStats(
                hero_key=hk,
                hero_name=h_name,
                role=h_role,
                time_sec=h_time,
                games_played=h_cnt.games_played,
                games_won=h_cnt.games_won,
                games_lost=h_cnt.games_lost,
                eliminations_10m=round(h_cnt.eliminations * factor, 1),
                deaths_10m=round(h_cnt.deaths * factor, 1),
                damage_10m=round(h_cnt.hero_damage_done * factor, 0),
                healing_10m=round(h_cnt.healing_done * factor, 0),
            )
        )
        if idx == 0 and h_time >= 600:
            hero_of_the_week_title = f"{h_name} · {h_cnt.games_won}-{h_cnt.games_lost}"

    # Общие средние за 10 минут
    f_all = (600.0 / tot_time_sec) if tot_time_sec > 0 else 0.0
    tot_decided = tot_wins + tot_losses
    overall_wr = round((tot_wins / tot_decided) * 100) if tot_decided > 0 else 0

    longest_sess_str = "—"
    if longest_session_time > 0:
        match_w = format_matches_caption(longest_session_games, lang)
        time_w = format_time_duration(longest_session_time, lang)
        longest_sess_str = f"{longest_session_games} {match_w} · {time_w}"

    return WeeklyReportData(
        player_name=player_name,
        gamemode=gamemode,
        mode_title=mode_title,
        period_title=period_title,
        total_matches=tot_matches,
        total_wins=tot_wins,
        total_losses=tot_losses,
        winrate_pct=overall_wr,
        total_time_sec=tot_time_sec,
        sessions_count=len(all_sessions),
        days=days_data,
        top_heroes=top_heroes_list,
        best_day_title=best_day_title,
        hero_of_the_week=hero_of_the_week_title,
        longest_session_str=longest_sess_str,
        player_avatar_path=None,
        language=lang,
    )

