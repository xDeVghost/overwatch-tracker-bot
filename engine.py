import logging
from typing import Dict, List, Optional, Tuple
import config
from models import (
    BucketState,
    CareerSnapshot,
    HeroCardBlock,
    HeroCounters,
    MetricScaleResult,
    ObservationRecord,
    OtherHeroItem,
    RoleRankProgress,
)
from i18n import (
    DIVISION_MAP,
    METRIC_TITLES,
    ROLE_ORDER,
    ROLE_TITLES as I18N_ROLE_TITLES,
    format_metric_label,
    t,
)

logger = logging.getLogger(__name__)

ROLE_ORDER = ["tank", "damage", "support"]
ROLE_TITLES = I18N_ROLE_TITLES["ru"]
DIVISION_RU_MAP = DIVISION_MAP["ru"]


def extract_competitive_ranks(
    ranks_data: dict, platform: str, session_won: int = 0, session_lost: int = 0, lang: str = "ru"
) -> Optional[List[RoleRankProgress]]:
    if not ranks_data or not isinstance(ranks_data, dict):
        return None
    p_ranks = ranks_data.get(platform) or ranks_data.get("pc") or {}
    if not isinstance(p_ranks, dict):
        return None

    r_titles = I18N_ROLE_TITLES.get(lang, I18N_ROLE_TITLES["ru"])
    role_order = [("tank", r_titles.get("tank", "TANK")), ("damage", r_titles.get("damage", "DAMAGE")), ("support", r_titles.get("support", "SUPPORT"))]
    div_map = DIVISION_MAP.get(lang, DIVISION_MAP["ru"])
    session_word = "in session" if lang == "en" else "в сессии"
    placement_title = "Placement" if lang == "en" else "Калибровка"

    res: List[RoleRankProgress] = []
    has_any = False
    for r_key, r_title in role_order:
        r_info = p_ranks.get(r_key)
        if r_info and isinstance(r_info, dict):
            div = str(r_info.get("division") or "unranked").lower()
            tier = int(r_info.get("tier") or 1)
            div_title = div_map.get(div, div.capitalize())
            delta_str = None
            if session_won > 0 or session_lost > 0:
                delta_str = f"▲ {session_won}-{session_lost} {session_word}" if session_won >= session_lost else f"▼ {session_won}-{session_lost} {session_word}"
            res.append(
                RoleRankProgress(
                    role=r_key,
                    role_title=r_title,
                    division=div,
                    division_title=div_title,
                    tier=tier,
                    progress_pct=50,
                    delta_text=delta_str,
                )
            )
            has_any = True
        else:
            res.append(
                RoleRankProgress(
                    role=r_key,
                    role_title=r_title,
                    division="unranked",
                    division_title=placement_title,
                    tier=1,
                    progress_pct=0,
                    delta_text=None,
                )
            )
    return res if has_any else None


def snapshots_equal(prev: CareerSnapshot, curr: CareerSnapshot) -> bool:
    if set(prev.heroes.keys()) != set(curr.heroes.keys()):
        return False
    for k, ch in curr.heroes.items():
        ph = prev.heroes.get(k)
        if not ph:
            return False
        if (
            ch.time_played != ph.time_played
            or ch.deaths != ph.deaths
            or ch.eliminations != ph.eliminations
            or ch.hero_damage_done != ph.hero_damage_done
            or ch.healing_done != ph.healing_done
            or ch.games_played != ph.games_played
            or ch.games_won != ph.games_won
            or ch.games_lost != ph.games_lost
        ):
            return False
    return True


def compute_delta(prev: CareerSnapshot, curr: CareerSnapshot) -> Tuple[Optional[Dict[str, HeroCounters]], bool]:
    """
    Возвращает (deltas_by_hero, is_negative_reset).
    Если любой счётчик любого героя уменьшился — возвращает (None, True).
    """
    deltas: Dict[str, HeroCounters] = {}
    all_keys = set(prev.heroes.keys()) | set(curr.heroes.keys())

    for k in all_keys:
        ph = prev.heroes.get(k, HeroCounters())
        ch = curr.heroes.get(k, HeroCounters())

        dt = ch.time_played - ph.time_played
        dd = ch.deaths - ph.deaths
        delim = ch.eliminations - ph.eliminations
        ddmg = ch.hero_damage_done - ph.hero_damage_done
        dheal = ch.healing_done - ph.healing_done
        dgp = ch.games_played - ph.games_played
        dgw = ch.games_won - ph.games_won
        dgl = ch.games_lost - ph.games_lost

        if dt < -1e-3 or dd < -1e-3 or delim < -1e-3 or ddmg < -1e-3 or dheal < -1e-3 or dgp < 0 or dgw < 0 or dgl < 0:
            logger.warning(f"NEGATIVE_DELTA_RESET: hero={k} dt={dt} dd={dd} delim={delim} ddmg={ddmg} dheal={dheal} dgp={dgp}")
            return None, True

        if dt > 0 or dgp > 0 or dd > 0 or delim > 0 or ddmg > 0 or dheal > 0:
            deltas[k] = HeroCounters(
                time_played=max(0.0, dt),
                deaths=max(0.0, dd),
                eliminations=max(0.0, delim),
                hero_damage_done=max(0.0, ddmg),
                healing_done=max(0.0, dheal),
                games_played=max(0, dgp),
                games_won=max(0, dgw),
                games_lost=max(0, dgl),
            )

    return deltas, False


def select_output_metric_type(role: str, career_hero: Optional[HeroCounters], bucket_or_session_healing: float = 0.0) -> str:
    """
    Для Урона и Танка: всегда 'damage'.
    Для Поддержки: 'healing', если у героя есть healing_done > 0 в карьере (или в текущих данных), иначе 'damage'.
    """
    if role == "support":
        career_heal = career_hero.healing_done if career_hero else 0.0
        if career_heal > 0 or bucket_or_session_healing > 0:
            return "healing"
    return "damage"


def update_bucket_with_delta(
    bucket: BucketState,
    delta: HeroCounters,
    metric_type: str,
    obs_sec: int = config.OBS_SEC,
    now_ts: int = 0,
) -> Tuple[BucketState, Optional[ObservationRecord]]:
    """
    Добавляет дельту в незакрытое ведро.
    Правило 2: из одной дельты закрывается НЕ БОЛЕЕ ОДНОГО наблюдения.
    Остаток (даже если >= obs_sec) остаётся в ведре пропорционально времени и закроется следующей дельтой.
    """
    total_time = bucket.time_sec + delta.time_played
    total_deaths = bucket.deaths + delta.deaths
    total_elim = bucket.eliminations + delta.eliminations
    total_dmg = bucket.damage + delta.hero_damage_done
    total_heal = bucket.healing + delta.healing_done

    if total_time < obs_sec or total_time <= 0:
        return (
            BucketState(
                time_sec=total_time,
                deaths=total_deaths,
                eliminations=total_elim,
                damage=total_dmg,
                healing=total_heal,
            ),
            None,
        )

    # Закрываем ровно одно наблюдение на obs_sec (600 с)
    rate_10m = 600.0 / total_time
    deaths_10m = total_deaths * rate_10m
    elim_10m = total_elim * rate_10m
    output_raw = total_heal if metric_type == "healing" else total_dmg
    output_10m = output_raw * rate_10m

    obs = ObservationRecord(
        output_10m=round(output_10m, 2),
        deaths_10m=round(deaths_10m, 2),
        eliminations_10m=round(elim_10m, 2),
        created_at=now_ts,
    )

    rem_time = total_time - obs_sec
    rem_ratio = rem_time / total_time
    new_bucket = BucketState(
        time_sec=round(rem_time, 4),
        deaths=total_deaths * rem_ratio,
        eliminations=total_elim * rem_ratio,
        damage=total_dmg * rem_ratio,
        healing=total_heal * rem_ratio,
    )
    return new_bucket, obs


def _compute_norm_and_band(values: List[float]) -> Tuple[float, float, float]:
    """
    Возвращает (норма, нижняя_граница_обычного, верхняя_граница_обычного)
    по последним наблюдениям (центральное значение и средние 50%).
    """
    if not values:
        return 0.0, 0.0, 0.0

    s = sorted(values)
    n = len(s)

    if n == 1:
        # Одно значение — норма = оно, коридор ±12%
        v = s[0]
        return v, v * 0.88, v * 1.12

    def _point_at(q: float) -> float:
        pos = q * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    return _point_at(0.50), _point_at(0.25), _point_at(0.75)


def build_metric_scale(
    metric_type: str,
    session_val: float,
    obs_values: List[float],
    lang: str = "ru",
) -> MetricScaleResult:
    """
    Строит шкалу и подпись для одной метрики.
    """
    titles = METRIC_TITLES.get(lang, METRIC_TITLES["ru"])
    title = titles.get(metric_type, "Output" if lang == "en" else "Выдача")
    higher_is_better = metric_type != "deaths"

    norm, band_low, band_high = _compute_norm_and_band(obs_values)

    if norm <= 0:
        return MetricScaleResult(
            metric_type=metric_type,
            title=title,
            session_val=round(session_val, 1),
            norm_val=0.0,
            band_low=0.0,
            band_high=0.0,
            status="usual",
            color="gray",
            pct_diff=None,
            label_text=t("card_norm_not_ready", lang),
            pos_norm=0.5,
            clamped=None,
            show_scale=False,
        )

    raw_pct = round(((session_val - norm) / norm) * 100)

    # Определяем статус строго по выходу за полосу [band_low, band_high]
    if higher_is_better:
        if session_val > band_high:
            status = "better"
            color = "green"
        elif session_val < band_low:
            status = "worse"
            color = "red"
        else:
            status = "usual"
            color = "gray"
    else:
        # Для смертей меньше = лучше
        if session_val < band_low:
            status = "better"
            color = "green"
        elif session_val > band_high:
            status = "worse"
            color = "red"
        else:
            status = "usual"
            color = "gray"

    label_text = format_metric_label(metric_type, status, raw_pct, lang)

    # Координата на шкале [0.0 .. 1.0]: полоса "обычного" занимает [0.30 .. 0.70], норма = 0.50
    # Вправо (> 0.50) ВСЕГДА лучше, влево (< 0.50) ВСЕГДА хуже
    if status == "usual":
        if higher_is_better:
            if session_val >= norm:
                span = band_high - norm
                raw_pos = 0.50 + (0.20 * (session_val - norm) / span if span > 1e-6 else 0.0)
            else:
                span = norm - band_low
                raw_pos = 0.50 - (0.20 * (norm - session_val) / span if span > 1e-6 else 0.0)
        else:
            if session_val <= norm:
                span = norm - band_low
                raw_pos = 0.50 + (0.20 * (norm - session_val) / span if span > 1e-6 else 0.0)
            else:
                span = band_high - norm
                raw_pos = 0.50 - (0.20 * (session_val - norm) / span if span > 1e-6 else 0.0)
    elif status == "better":
        if higher_is_better:
            step = max(band_high - norm, norm * 0.12, 1e-3)
            raw_pos = max(0.73, 0.70 + 0.18 * ((session_val - band_high) / step))
        else:
            step = max(norm - band_low, norm * 0.12, 1e-3)
            raw_pos = max(0.73, 0.70 + 0.18 * ((band_low - session_val) / step))
    else:  # status == "worse"
        if higher_is_better:
            step = max(norm - band_low, norm * 0.12, 1e-3)
            raw_pos = min(0.27, 0.30 - 0.18 * ((band_low - session_val) / step))
        else:
            step = max(band_high - norm, norm * 0.12, 1e-3)
            raw_pos = min(0.27, 0.30 - 0.18 * ((session_val - band_high) / step))

    clamped = None
    if raw_pos < 0.0:
        pos_norm = 0.0
        clamped = "left"
    elif raw_pos > 1.0:
        pos_norm = 1.0
        clamped = "right"
    else:
        pos_norm = round(raw_pos, 4)

    return MetricScaleResult(
        metric_type=metric_type,
        title=title,
        session_val=round(session_val, 1),
        norm_val=round(norm, 1),
        band_low=round(band_low, 1),
        band_high=round(band_high, 1),
        status=status,
        color=color,
        pct_diff=raw_pct,
        label_text=label_text,
        pos_norm=pos_norm,
        clamped=clamped,
        show_scale=True,
    )


def combine_metric_verdicts(statuses: List[str], lang: str = "ru") -> str:
    """
    Итоговый вердикт героя из метрик (Урон/Хил, Смерти, Убийства).
    """
    valid = [s for s in statuses if s in ("better", "worse", "usual")]
    if not valid:
        return t("verdict_usual", lang)
    b_cnt = valid.count("better")
    w_cnt = valid.count("worse")
    if b_cnt > 0 and w_cnt > 0:
        return t("verdict_mixed", lang)
    if b_cnt >= 1 and w_cnt == 0:
        return t("verdict_better", lang)
    if w_cnt >= 1 and b_cnt == 0:
        return t("verdict_worse", lang)
    return t("verdict_usual", lang)


def combine_two_verdicts(out_status: str, deaths_status: str, lang: str = "ru") -> str:
    return combine_metric_verdicts([out_status, deaths_status], lang=lang)


def evaluate_hero_session(
    role: str,
    hero_key: str,
    hero_name: str,
    is_fallback: bool,
    session_counters: HeroCounters,
    observations: List[ObservationRecord],
    career_counters: Optional[HeroCounters],
    bucket_time_sec: float = 0.0,
    obs_sec: int = config.OBS_SEC,
    min_obs: int = config.MIN_OBS,
    obs_window: int = config.OBS_WINDOW,
    lang: str = "ru",
) -> HeroCardBlock:
    """
    Оценивает отыгрыш героя за сессию и возвращает блок карточки со всеми метриками.
    """
    r_titles = I18N_ROLE_TITLES.get(lang, I18N_ROLE_TITLES["ru"])
    role_title = r_titles.get(role, role.upper())
    time_sec = session_counters.time_played
    time_min = max(1, int(round(time_sec / 60.0)))
    metric_type = select_output_metric_type(role, career_counters, session_counters.healing_done)

    # Показатели сессии в пересчёте на 10 минут
    factor_10m = 600.0 / max(1.0, time_sec)
    sess_out_10m = (
        session_counters.healing_done if metric_type == "healing" else session_counters.hero_damage_done
    ) * factor_10m
    sess_deaths_10m = session_counters.deaths * factor_10m
    sess_elim_10m = session_counters.eliminations * factor_10m

    # Формируем выборку для расчёта норм
    recent_obs = observations[:obs_window]
    if len(recent_obs) >= 4:
        # Достаточно собственных 10-минутных наблюдений бота
        out_history = [o.output_10m for o in recent_obs]
        deaths_history = [o.deaths_10m for o in recent_obs]
        elim_history = [o.eliminations_10m for o in recent_obs if o.eliminations_10m > 0]
    elif career_counters and career_counters.time_played >= 60:
        # Если наблюдений мало, используем личную среднюю норму из карьеры Blizzard
        c_f10 = 600.0 / career_counters.time_played
        c_out = (career_counters.healing_done if metric_type == "healing" else career_counters.hero_damage_done) * c_f10
        c_deaths = career_counters.deaths * c_f10
        c_elim = career_counters.eliminations * c_f10
        # Коридор обычной игры: +/- 12% от среднего по карьере
        out_history = [c_out * 0.88, c_out, c_out * 1.12]
        deaths_history = [c_deaths * 0.88, c_deaths, c_deaths * 1.12]
        elim_history = [c_elim * 0.88, c_elim, c_elim * 1.12]
    else:
        out_history = []
        deaths_history = []
        elim_history = []

    out_scale = build_metric_scale(metric_type, sess_out_10m, out_history, lang=lang)
    deaths_scale = build_metric_scale("deaths", sess_deaths_10m, deaths_history, lang=lang)
    elim_scale = build_metric_scale("eliminations", sess_elim_10m, elim_history, lang=lang) if (sess_elim_10m > 0 or elim_history) else None

    statuses = [s.status for s in (out_scale, deaths_scale, elim_scale) if s is not None and s.show_scale]
    final_verdict = combine_metric_verdicts(statuses, lang=lang) if statuses else t("verdict_usual", lang)

    logger.info(
        f"VERDICT_LOG: hero={hero_key} time_min={time_min} "
        f"out=({out_scale.session_val} vs norm={out_scale.norm_val} -> {out_scale.status}) "
        f"deaths=({deaths_scale.session_val} vs norm={deaths_scale.norm_val} -> {deaths_scale.status}) "
        f"elim=({sess_elim_10m:.1f} -> {elim_scale.status if elim_scale else 'no_scale'}) "
        f"final='{final_verdict}'"
    )

    return HeroCardBlock(
        role=role,
        role_title=role_title,
        hero_key=hero_key,
        hero_name=hero_name,
        time_min=time_min,
        is_fallback=is_fallback,
        has_verdict=True,
        verdict_text=final_verdict,
        eliminations=session_counters.eliminations,
        eliminations_10m=sess_elim_10m,
        output_scale=out_scale,
        deaths_scale=deaths_scale,
        eliminations_scale=elim_scale,
    )


def select_role_heroes_and_footer(
    session_heroes: Dict[str, HeroCounters],
    preferences: Dict[str, str],
    hero_roles: Dict[str, str],
    hero_names: Dict[str, str],
    obs_sec: int = config.OBS_SEC,
    max_blocks: int = 4,
) -> Tuple[List[Tuple[str, str, bool]], List[OtherHeroItem]]:
    """
    Отбирает до max_blocks (по умолчанию 4) наиболее играемых героев сессии (время >= 120 сек)
    для отображения полноценных блоков со всеми метриками и шкалами как есть.
    Остальные герои сессии (время >= 60 сек) идут в подвал «Ещё играл: ...».
    """
    candidates = [
        hk for hk, cnt in session_heroes.items()
        if hk != "all-heroes" and cnt.time_played >= 120
    ]

    if not candidates:
        sub_cands = [hk for hk, cnt in session_heroes.items() if hk != "all-heroes" and cnt.time_played >= 60]
        if sub_cands:
            sub_cands.sort(key=lambda hk: session_heroes[hk].time_played, reverse=True)
            candidates = [sub_cands[0]]

    # Сортируем по времени игры с небольшим бонусом предпочитаемым героям
    def _rank_key(hk: str) -> float:
        role = hero_roles.get(hk, "damage")
        pref_boost = 60.0 if preferences.get(role) == hk else 0.0
        return session_heroes[hk].time_played + pref_boost

    candidates.sort(key=_rank_key, reverse=True)

    chosen_blocks: List[Tuple[str, str, bool]] = []
    chosen_keys = set()

    for hk in candidates[:max_blocks]:
        role = hero_roles.get(hk, "damage")
        pref_key = preferences.get(role)
        is_fb = bool(pref_key and hk != pref_key)
        chosen_blocks.append((role, hk, is_fb))
        chosen_keys.add(hk)

    other_items: List[OtherHeroItem] = []
    for hk, cnt in sorted(session_heroes.items(), key=lambda x: x[1].time_played, reverse=True):
        if hk == "all-heroes" or hk in chosen_keys:
            continue
        if cnt.time_played >= 60:
            other_items.append(
                OtherHeroItem(
                    hero_key=hk,
                    hero_name=hero_names.get(hk, hk.capitalize()),
                    time_min=max(1, int(round(cnt.time_played / 60.0))),
                    eliminations=cnt.eliminations,
                )
            )

    return chosen_blocks, other_items
