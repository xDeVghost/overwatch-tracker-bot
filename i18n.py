from typing import Dict, Optional

# Supported languages
LANG_RU = "ru"
LANG_EN = "en"
SUPPORTED_LANGUAGES = (LANG_RU, LANG_EN)

# Canonical hero display names in English and Russian
HERO_RU_MAP = {
    "ana": "Ана", "ashe": "Эш", "baptiste": "Батист", "bastion": "Бастион",
    "brigitte": "Бригитта", "cassidy": "Кэссиди", "doomfist": "Кулак Смерти",
    "dva": "D.Va", "echo": "Эхо", "freja": "Фрейя", "genji": "Гэндзи",
    "hanzo": "Хандзо", "hazard": "Хазард", "illari": "Иллари",
    "jetpack-cat": "Реактивная Киса", "junker-queen": "Королева Стервятников",
    "junkrat": "Крысавчик", "juno": "Юнона", "kiriko": "Кирико",
    "lifeweaver": "Ткач Жизни", "lucio": "Лусио", "mauga": "Мауга",
    "mei": "Мэй", "mercy": "Ангел", "moira": "Мойра", "orisa": "Ориса",
    "pharah": "Фарра", "ramattra": "Раматтра", "reaper": "Жнец",
    "reinhardt": "Райнхардт", "roadhog": "Турбосвин", "sigma": "Сигма",
    "sierra": "Сьерра", "sojourn": "Соджорн", "soldier-76": "Солдат-76",
    "sombra": "Сомбра", "symmetra": "Симметра", "torbjorn": "Торбьорн",
    "tracer": "Трейсер", "venture": "Авантюра", "widowmaker": "Роковая Вдова",
    "winston": "Уинстон", "wrecking-ball": "Таран", "zarya": "Заря",
    "zenyatta": "Дзенъятта", "anran": "Анран",
}

HERO_EN_MAP = {
    "ana": "Ana", "ashe": "Ashe", "baptiste": "Baptiste", "bastion": "Bastion",
    "brigitte": "Brigitte", "cassidy": "Cassidy", "doomfist": "Doomfist",
    "dva": "D.Va", "echo": "Echo", "freja": "Freja", "genji": "Genji",
    "hanzo": "Hanzo", "hazard": "Hazard", "illari": "Illari",
    "jetpack-cat": "Jetpack Cat", "junker-queen": "Junker Queen",
    "junkrat": "Junkrat", "juno": "Juno", "kiriko": "Kiriko",
    "lifeweaver": "Lifeweaver", "lucio": "Lúcio", "mauga": "Mauga",
    "mei": "Mei", "mercy": "Mercy", "moira": "Moira", "orisa": "Orisa",
    "pharah": "Pharah", "ramattra": "Ramattra", "reaper": "Reaper",
    "reinhardt": "Reinhardt", "roadhog": "Roadhog", "sigma": "Sigma",
    "sierra": "Sierra", "sojourn": "Sojourn", "soldier-76": "Soldier: 76",
    "sombra": "Sombra", "symmetra": "Symmetra", "torbjorn": "Torbjörn",
    "tracer": "Tracer", "venture": "Venture", "widowmaker": "Widowmaker",
    "winston": "Winston", "wrecking-ball": "Wrecking Ball", "zarya": "Zarya",
    "zenyatta": "Zenyatta", "anran": "Anran",
}

ROLE_ORDER = ["tank", "damage", "support"]

ROLE_TITLES: Dict[str, Dict[str, str]] = {
    "ru": {"tank": "ТАНК", "damage": "УРОН", "support": "ПОДДЕРЖКА"},
    "en": {"tank": "TANK", "damage": "DAMAGE", "support": "SUPPORT"},
}

MODE_TITLES: Dict[str, Dict[str, str]] = {
    "ru": {"quickplay": "Быстрая игра", "competitive": "Соревновательный"},
    "en": {"quickplay": "Quick Play", "competitive": "Competitive"},
}

DIVISION_MAP: Dict[str, Dict[str, str]] = {
    "ru": {
        "bronze": "Бронза",
        "silver": "Серебро",
        "gold": "Золото",
        "platinum": "Платина",
        "diamond": "Алмаз",
        "master": "Мастер",
        "grandmaster": "Грандмастер",
        "champion": "Чемпион",
        "unranked": "Калибровка",
    },
    "en": {
        "bronze": "Bronze",
        "silver": "Silver",
        "gold": "Gold",
        "platinum": "Platinum",
        "diamond": "Diamond",
        "master": "Master",
        "grandmaster": "Grandmaster",
        "champion": "Champion",
        "unranked": "Placement",
    },
}

METRIC_TITLES: Dict[str, Dict[str, str]] = {
    "ru": {
        "damage": "Урон",
        "healing": "Хил",
        "deaths": "Смерти",
        "eliminations": "Убийства",
    },
    "en": {
        "damage": "Damage",
        "healing": "Healing",
        "deaths": "Deaths",
        "eliminations": "Eliminations",
    },
}

MONTH_NAMES: Dict[str, list] = {
    "ru": ["", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
    "en": ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

DAY_NAMES: Dict[str, list] = {
    "ru": ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"],
    "en": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
}

DAY_FULL_NAMES: Dict[str, list] = {
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}

TEXTS: Dict[str, Dict[str, str]] = {
    "ru": {
        # Reply buttons
        "btn_card_now": "📊 Карточка сейчас",
        "btn_weekly": "📅 Недельный отчёт",
        "btn_settings": "⚙️ Настройки",
        "btn_lang_toggle": "🌐 Язык: Русский 🇷🇺",

        # Start & Help
        "start_greeting": (
            "Привет! Отправь свой BattleTag в формате <code>Name#12345</code> "
            "(или <code>/start Name#12345</code>), чтобы я начал отслеживать сессии.\n\n"
            "Доступные функции:\n"
            "• <b>📊 Карточка сейчас</b> — сформировать карточку текущей сессии\n"
            "• <b>📅 Недельный отчёт</b> — инфографика и гистограмма за неделю\n"
            "• <b>⚙️ Настройки</b> — выбор основных героев по ролям и языковые настройки"
        ),

        # Profile registration
        "checking_profile": "⏳ Проверяю профиль <b>{btag}</b>...",
        "profile_not_found": "❌ Не нашёл профиль или он закрыт. Проверь BattleTag и убедись, что профиль открыт в настройках игры.",
        "profile_no_career": "❌ Профиль найден, но статистика карьеры недоступна (проверь, что профиль открыт в игре).",
        "profile_success": (
            "✅ Нашёл профиль <b>{btag}</b>!\n"
            "Основные герои по ролям выбраны автоматически:\n{pref_str}\n\n"
            "Изменить их можно через кнопку <b>⚙️ Настройки</b>."
        ),
        "menu_active": "Меню управления активно:",

        # Settings
        "need_register": "Сначала привяжи BattleTag через <code>/start Name#12345</code>",
        "settings_title": "⚙️ <b>Настройки профиля {btag}</b>\nВыбери предпочитаемого героя для каждой роли или измени язык:",
        "change_action": "изменить",
        "select_role_prompt": "Выбери основного героя для роли <b>{role_title}</b> (отсортированы по времени игры):",
        "hero_selected": "Выбран {name}",
        "prefs_updated": "⚙️ <b>Предпочтения обновлены!</b>\nВыбери роль, если хочешь поменять ещё:",
        "lang_switched": "Язык изменён на Русский 🇷🇺",

        # Card now
        "fetching_data": "🔄 Запрашиваю свежие данные с серверов...",
        "blizzard_delay": "Данные Blizzard обновляются с задержкой, поэтому самый последний матч мог ещё не попасть в карточку.",
        "too_short_session": (
            "⏱ <b>Слишком мало времени в сессии</b> ({details}).\n"
            "Для карточки нужно минимум 5 минут игры (или сыграть 1 матч). Сессия не сброшена — сыграй ещё или подожди, "
            "если последние матчи ещё не обновились на сервере Blizzard."
        ),
        "no_active_session": (
            "📭 <b>Сейчас нет активной сессии.</b>\n"
            "Если ты только что доиграл матч, статистика Blizzard может обновляться до 10 минут — попробуй чуть позже."
        ),
        "session_min_short": "{mode}: {mins} из 10 мин",

        # Manual close
        "cmd_close_success": "✅ Сессия ({modes}) закрыта и перенесена в историю.",
        "cmd_close_empty": "📭 Нет активных сессий для закрытия.",

        # Weekly
        "generating_weekly": "📊 Формирую недельный отчёт...",
        "weekly_empty": (
            "📭 <b>На этой неделе ещё нет сыгранных матчей.</b>\n"
            "Как только доиграешь хотя бы одну сессию, отчёт появится здесь."
        ),
        "weekly_caption": (
            "📅 <b>Недельный отчёт · {player_name}</b> ({mode_title})\n"
            "Период: {period}\n"
            "Всего матчей: <b>{matches}</b> (Винрейт <b>{wr}%</b>)\n"
            "Время в игре: {time} за {sessions} сессий\n"
            "🏆 Лучший день: <b>{best_day}</b>\n"
            "👑 Герой недели: <b>{hero_of_week}</b>"
        ),

        # In-card labels
        "card_sub": "{mode_title}  •  {games} игр  •  {duration} мин  •  {date}",
        "card_session_badge": "за сессию",
        "card_kd_norm": "норма",
        "card_score_title": "ПОБЕДЫ — ПОРАЖЕНИЯ",
        "card_ranks_title": "ПРОГРЕСС В РАНГАХ",
        "card_comp_subtitle": "•   Соревновательный режим",
        "card_rank_default": "РЕЙТИНГ",
        "card_season_prefix": "СЕЗОН",
        "card_no_10min_title": "Ни на одном герое в этой сессии ещё не набрано 10 минут.",
        "card_no_10min_sub": "Для надёжного сравнения с твоей нормой нужно минимум 10 минут игры на герое.",
        "card_fallback_tag": "не основной",
        "card_per_10m": "{val} за 10 мин",
        "card_your_norm": "твоя норма: {norm} (обычно {low}–{high})",
        "card_norm_not_ready": "норма ещё не накоплена",
        "card_also_played": "Ещё играл:",
        "card_min_abbr": "мин",
        "card_to_rank": "{pct}% до ранга",
        "card_in_session": "в сессии",

        # Verdicts
        "verdict_better": "лучше обычного",
        "verdict_worse": "хуже обычного",
        "verdict_usual": "как обычно",
        "verdict_mixed": "по-разному",

        # Weekly in-card
        "weekly_sub": "за неделю",
        "weekly_score_title": "ПОБЕДЫ — ПОРАЖЕНИЯ",
        "weekly_kpi_matches": "МАТЧИ",
        "weekly_kpi_winrate": "ВИНРЕЙТ",
        "weekly_kpi_time": "ВРЕМЯ В ИГРЕ",
        "weekly_kpi_sessions": "СЕССИИ",
        "weekly_histo_title": "МАТЧИ ПО ДНЯМ",
        "weekly_histo_sub": "•  победы и поражения за неделю",
        "weekly_histo_wins": "Победы",
        "weekly_histo_losses": "Поражения",
        "weekly_histo_best": "ЛУЧШИЙ",
        "weekly_heroes_title": "ГЕРОИ НЕДЕЛИ",
        "weekly_col_score": "СЧЁТ",
        "weekly_col_elims": "УБИЙСТВ",
        "weekly_col_deaths": "СМЕРТЕЙ",
        "weekly_col_dmg": "УРОН",
        "weekly_col_heal": "ИСЦЕЛЕНИЕ",
        "weekly_no_heroes": "На этой неделе ещё не сыграно матчей.",
        "weekly_hl_hero": "ГЕРОЙ НЕДЕЛИ",
        "weekly_hl_session": "САМАЯ БОЛЬШАЯ СЕССИЯ",
        "weekly_hl_day": "ЛУЧШИЙ ДЕНЬ",
        "weekly_matches_suffix": "матчей",
    },
    "en": {
        # Reply buttons
        "btn_card_now": "📊 Card Now",
        "btn_weekly": "📅 Weekly Report",
        "btn_settings": "⚙️ Settings",
        "btn_lang_toggle": "🌐 Language: English 🇬🇧",

        # Start & Help
        "start_greeting": (
            "Hello! Send your BattleTag in <code>Name#12345</code> format "
            "(or <code>/start Name#12345</code>) to start tracking your sessions.\n\n"
            "Features:\n"
            "• <b>📊 Card Now</b> — generate card for current session\n"
            "• <b>📅 Weekly Report</b> — weekly infographics and charts\n"
            "• <b>⚙️ Settings</b> — select main heroes and switch language"
        ),

        # Profile registration
        "checking_profile": "⏳ Checking profile <b>{btag}</b>...",
        "profile_not_found": "❌ Profile not found or private. Please check your BattleTag and make sure your profile is public in Overwatch settings.",
        "profile_no_career": "❌ Profile found, but career stats are unavailable (ensure your profile visibility is public).",
        "profile_success": (
            "✅ Profile found: <b>{btag}</b>!\n"
            "Preferred heroes auto-selected:\n{pref_str}\n\n"
            "You can customize them via <b>⚙️ Settings</b>."
        ),
        "menu_active": "Control menu active:",

        # Settings
        "need_register": "Please link your BattleTag first with <code>/start Name#12345</code>",
        "settings_title": "⚙️ <b>Settings for {btag}</b>\nChoose your preferred hero for each role or switch language:",
        "change_action": "change",
        "select_role_prompt": "Choose your main hero for <b>{role_title}</b> (sorted by playtime):",
        "hero_selected": "Selected {name}",
        "prefs_updated": "⚙️ <b>Settings updated!</b>\nSelect a role if you want to change more:",
        "lang_switched": "Language switched to English 🇬🇧",

        # Card now
        "fetching_data": "🔄 Fetching fresh data from Blizzard servers...",
        "blizzard_delay": "Blizzard statistics update with a delay, so the very latest match might not be included yet.",
        "too_short_session": (
            "⏱ <b>Session is too short</b> ({details}).\n"
            "At least 5 minutes of play (or 1 completed match) is required. The session is preserved — play more or wait for Blizzard servers to sync."
        ),
        "no_active_session": (
            "📭 <b>No active session right now.</b>\n"
            "If you just finished a match, Blizzard stats may take up to 10 minutes to update — please try again shortly."
        ),
        "session_min_short": "{mode}: {mins} of 10 min",

        # Manual close
        "cmd_close_success": "✅ Session ({modes}) closed and moved to history.",
        "cmd_close_empty": "📭 No active sessions to close.",

        # Weekly
        "generating_weekly": "📊 Generating weekly report...",
        "weekly_empty": (
            "📭 <b>No matches recorded for this week yet.</b>\n"
            "Complete at least one session and your report will show up here."
        ),
        "weekly_caption": (
            "📅 <b>Weekly Report · {player_name}</b> ({mode_title})\n"
            "Period: {period}\n"
            "Total matches: <b>{matches}</b> (Winrate <b>{wr}%</b>)\n"
            "Playtime: {time} across {sessions} sessions\n"
            "🏆 Best day: <b>{best_day}</b>\n"
            "👑 Hero of the week: <b>{hero_of_week}</b>"
        ),

        # In-card labels
        "card_sub": "{mode_title}  •  {games} games  •  {duration} min  •  {date}",
        "card_session_badge": "this session",
        "card_kd_norm": "norm",
        "card_score_title": "WINS — LOSSES",
        "card_ranks_title": "RANK PROGRESS",
        "card_comp_subtitle": "•   Competitive Play",
        "card_rank_default": "COMPETITIVE",
        "card_season_prefix": "SEASON",
        "card_no_10min_title": "No hero has reached 10 minutes of playtime in this session yet.",
        "card_no_10min_sub": "At least 10 minutes on a hero is required for an accurate performance comparison.",
        "card_fallback_tag": "off-hero",
        "card_per_10m": "{val} per 10 min",
        "card_your_norm": "your norm: {norm} (typical {low}–{high})",
        "card_norm_not_ready": "norm not accumulated yet",
        "card_also_played": "Also played:",
        "card_min_abbr": "min",
        "card_to_rank": "{pct}% to rank",
        "card_in_session": "in session",

        # Verdicts
        "verdict_better": "above average",
        "verdict_worse": "below average",
        "verdict_usual": "as usual",
        "verdict_mixed": "mixed",

        # Weekly in-card
        "weekly_sub": "this week",
        "weekly_score_title": "WINS — LOSSES",
        "weekly_kpi_matches": "MATCHES",
        "weekly_kpi_winrate": "WINRATE",
        "weekly_kpi_time": "PLAYTIME",
        "weekly_kpi_sessions": "SESSIONS",
        "weekly_histo_title": "MATCHES BY DAY",
        "weekly_histo_sub": "•  wins and losses this week",
        "weekly_histo_wins": "Wins",
        "weekly_histo_losses": "Losses",
        "weekly_histo_best": "BEST",
        "weekly_heroes_title": "HEROES OF THE WEEK",
        "weekly_col_score": "SCORE",
        "weekly_col_elims": "ELIMS",
        "weekly_col_deaths": "DEATHS",
        "weekly_col_dmg": "DAMAGE",
        "weekly_col_heal": "HEALING",
        "weekly_no_heroes": "No matches played this week yet.",
        "weekly_hl_hero": "HERO OF THE WEEK",
        "weekly_hl_session": "LONGEST SESSION",
        "weekly_hl_day": "BEST DAY",
        "weekly_matches_suffix": "matches",
    },
}


def normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return LANG_RU
    lang_clean = str(lang).strip().lower()[:2]
    return LANG_EN if lang_clean == LANG_EN else LANG_RU


def t(key: str, lang: str = LANG_RU, **kwargs) -> str:
    normalized = normalize_lang(lang)
    lang_dict = TEXTS.get(normalized, TEXTS[LANG_RU])
    text = lang_dict.get(key, TEXTS[LANG_RU].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_hero_name(hero_key: str, lang: str = LANG_RU) -> str:
    normalized = normalize_lang(lang)
    if normalized == LANG_EN:
        return HERO_EN_MAP.get(hero_key, hero_key.replace("-", " ").title())
    return HERO_RU_MAP.get(hero_key, HERO_EN_MAP.get(hero_key, hero_key.capitalize()))


def format_matches_caption(n: int, lang: str = LANG_RU) -> str:
    normalized = normalize_lang(lang)
    if normalized == LANG_EN:
        word = "match" if n == 1 else "matches"
    else:
        if 11 <= (n % 100) <= 14:
            word = "матчей"
        elif (n % 10) == 1:
            word = "матч"
        elif 2 <= (n % 10) <= 4:
            word = "матча"
        else:
            word = "матчей"
    return word


def format_time_duration(sec: float, lang: str = LANG_RU) -> str:
    normalized = normalize_lang(lang)
    m = int(round(sec / 60.0))
    if normalized == LANG_EN:
        if m >= 60:
            return f"{m // 60} h {m % 60} min"
        return f"{m} min"
    else:
        if m >= 60:
            return f"{m // 60} ч {m % 60} мин"
        return f"{m} мин"


def format_metric_label(
    metric_type: str,
    status: str,
    raw_pct: Optional[int],
    lang: str = LANG_RU,
) -> str:
    normalized = normalize_lang(lang)
    if raw_pct is None:
        return t("card_norm_not_ready", normalized)

    if status == "usual":
        if raw_pct > 0:
            pct_str = f"+{raw_pct}%"
        elif raw_pct < 0:
            pct_str = f"−{abs(raw_pct)}%"
        else:
            pct_str = "0%"
        if normalized == LANG_EN:
            return f"as usual ({pct_str})"
        return f"как обычно ({pct_str})"

    abs_p = max(1, abs(raw_pct))
    if normalized == LANG_EN:
        if metric_type in ("damage", "healing"):
            noun = "damage" if metric_type == "damage" else "healing"
            return f"+{abs_p}% {noun}" if status == "better" else f"−{abs_p}% {noun}"
        elif metric_type == "eliminations":
            return f"+{abs_p}% elims" if status == "better" else f"−{abs_p}% elims"
        else:  # deaths
            return f"{abs_p}% fewer deaths" if status == "better" else f"{abs_p}% more deaths"
    else:
        if metric_type in ("damage", "healing"):
            noun = "урона" if metric_type == "damage" else "хила"
            word = "больше" if status == "better" else "меньше"
            return f"на {abs_p}% {word} {noun}"
        elif metric_type == "eliminations":
            word = "больше" if status == "better" else "меньше"
            return f"на {abs_p}% {word} убийств"
        else:
            word = "реже" if status == "better" else "чаще"
            return f"на {abs_p}% {word} умираешь"
