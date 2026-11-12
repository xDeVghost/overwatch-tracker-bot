import asyncio
from datetime import datetime, timedelta
import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import assets
import config
from db import Database
from engine import (
    compute_delta,
    evaluate_hero_session,
    extract_competitive_ranks,
    select_output_metric_type,
    select_role_heroes_and_footer,
    snapshots_equal,
    update_bucket_with_delta,
)
from i18n import (
    MODE_TITLES,
    ROLE_ORDER,
    ROLE_TITLES,
    format_matches_caption,
    get_hero_name,
    normalize_lang,
    t,
)
from models import (
    CareerSnapshot,
    DailyMatchStats,
    HeroCardBlock,
    HeroCounters,
    HeroWeeklyStats,
    MetricScaleResult,
    OtherHeroItem,
    RoleRankProgress,
    SessionCardData,
    WeeklyReportData,
)
from provider import OverFastProvider
from renderer import render_session_card
from weekly_engine import aggregate_weekly_report, get_current_week_bounds
from weekly_renderer import fmt_time, render_weekly_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_bot_token = config.BOT_TOKEN if (config.BOT_TOKEN and ":" in config.BOT_TOKEN) else "123456789:AAG_dummy_test_token_for_import"
bot = Bot(token=_bot_token)
dp = Dispatcher()
db = Database(config.DB_PATH)
provider = OverFastProvider(config.OVERFAST_BASE_URL)

BTN_WEEKLY_RU = t("btn_weekly", "ru")
BTN_WEEKLY_EN = t("btn_weekly", "en")
BTN_SETTINGS_RU = t("btn_settings", "ru")
BTN_SETTINGS_EN = t("btn_settings", "en")


def main_reply_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Клавиатура с двумя кнопками: Недельный отчёт и Настройки."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_weekly", lang)), KeyboardButton(text=t("btn_settings", lang))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def ensure_heroes_catalog(session: aiohttp.ClientSession):
    if db.heroes_need_refresh():
        heroes = await provider.fetch_heroes(session)
        if heroes:
            db.upsert_heroes_catalog(heroes)
            logger.info(f"HEROES_CATALOG_UPDATED: count={len(heroes)}")


async def download_avatar_if_needed(session: aiohttp.ClientSession, btag: str, avatar_url: Optional[str]) -> Optional[str]:
    """Скачивает и кэширует аватар игрока в cache/avatars/."""
    if not avatar_url:
        return None
    cache_path = os.path.join(assets.AVATARS_CACHE_DIR, f"{btag}.png")
    if os.path.isfile(cache_path):
        return cache_path
    try:
        async with session.get(avatar_url, timeout=12) as resp:
            if resp.status == 200:
                content = await resp.read()
                with open(cache_path, "wb") as f:
                    f.write(content)
                logger.info(f"AVATAR_DOWNLOADED: btag={btag}")
                return cache_path
    except Exception as e:
        logger.warning(f"AVATAR_DOWNLOAD_FAIL: btag={btag} err={e}")
    return None


async def poll_single_user(session: aiohttp.ClientSession, user_row: Tuple[int, str, str, int, str]) -> Tuple[bool, int]:
    """
    Опрашивает одного пользователя по обоим режимам (quickplay, competitive).
    Возвращает (были_ли_новые_данные, max_cache_age_sec).
    """
    user_id = user_row[0]
    btag = user_row[1]
    platform = user_row[2]
    prev_sum_ts = user_row[3]
    avatar_url = user_row[4] if len(user_row) > 4 else ""

    any_change = False
    max_cache_age = 0

    summary = await provider.fetch_summary(session, btag)
    curr_sum_ts = int(summary.get("last_updated_at") or 0) if summary else prev_sum_ts
    summary_changed = (curr_sum_ts > 0 and curr_sum_ts != prev_sum_ts)

    if summary and summary.get("avatar"):
        new_avatar = summary.get("avatar")
        if new_avatar != avatar_url:
            db.update_user_avatar(user_id, new_avatar)
        await download_avatar_if_needed(session, btag, new_avatar)

    if summary and summary.get("competitive"):
        db.update_user_ranks(user_id, json.dumps(summary.get("competitive")))

    if config.USE_SUMMARY_GATE and not summary_changed and prev_sum_ts > 0:
        return False, 0

    roles_map, _ = db.get_heroes_maps()
    now_ts = int(time.time())

    # Запрашиваем quickplay и competitive параллельно для ускорения опроса API
    (snap_qp, age_qp), (snap_comp, age_comp) = await asyncio.gather(
        provider.fetch_career(session, btag, "quickplay", platform),
        provider.fetch_career(session, btag, "competitive", platform),
    )
    mode_careers = [("quickplay", snap_qp, age_qp), ("competitive", snap_comp, age_comp)]

    for mode, curr_snap, cache_age in mode_careers:
        max_cache_age = max(max_cache_age, cache_age)
        if not curr_snap:
            continue

        prev_snap = db.get_snapshot(user_id, mode)
        if not prev_snap:
            db.save_snapshot(user_id, mode, curr_snap)
            continue

        if snapshots_equal(prev_snap, curr_snap):
            # Сохраняем свежий timestamp проверки, чтобы prev_snap не устаревал во время простоя
            db.save_snapshot(user_id, mode, curr_snap)
            continue

        deltas, is_reset = compute_delta(prev_snap, curr_snap)
        if is_reset or deltas is None:
            db.save_snapshot(user_id, mode, curr_snap)
            continue

        any_change = True

        # 1. Накапливаем наблюдения в вёдрах (независимо от сессий)
        bucket_updates = {}
        closed_observations = []
        for hk, h_delta in deltas.items():
            if hk == "all-heroes" or h_delta.time_played <= 0:
                continue
            role = roles_map.get(hk, "damage")
            m_type = select_output_metric_type(role, curr_snap.heroes.get(hk), h_delta.healing_done)
            bucket = db.get_bucket(user_id, mode, hk)
            new_bucket, closed_obs = update_bucket_with_delta(bucket, h_delta, m_type, config.OBS_SEC, now_ts)
            bucket_updates[hk] = new_bucket
            if closed_obs:
                closed_observations.append((hk, closed_obs))
                logger.info(
                    f"OBS_CLOSED: user={user_id} mode={mode} hero={hk} "
                    f"out10m={closed_obs.output_10m} d10m={closed_obs.deaths_10m} elim10m={closed_obs.eliminations_10m} rem_sec={new_bucket.time_sec:.1f}"
                )

        # 2. Ведра, наблюдения, активная сессия и новый snapshot должны
        # фиксироваться вместе: так одна и та же дельта не задвоится и не
        # потеряется при перезапуске между отдельными SQL-транзакциями.
        db.record_poll_update(
            user_id,
            mode,
            deltas,
            bucket_updates,
            closed_observations,
            curr_snap,
            now_ts,
        )

    logger.info(
        f"SUMMARY_GATE_CHECK: user={user_id} btag={btag} summary_changed={summary_changed} career_changed={any_change}"
    )
    if curr_sum_ts > 0 and curr_sum_ts != prev_sum_ts:
        db.update_user_summary_ts(user_id, curr_sum_ts)

    return any_change, max_cache_age


def build_session_card_for_mode(
    user_id: int, btag: str, mode: str, lang: Optional[str] = None
) -> Tuple[Optional[SessionCardData], float]:
    """
    Собирает данные карточки активной сессии для режима с учётом языка.
    Возвращает (SessionCardData | None, total_session_time_sec).
    """
    if not lang:
        lang = db.get_user_language(user_id)

    active = db.get_active_session(user_id, mode)
    if not active:
        return None, 0.0

    meta, sess_heroes = active
    total_sec = sum(c.time_played for k, c in sess_heroes.items() if k != "all-heroes")
    games_count = meta.get("games_played", 0)
    # Если сыгран хотя бы 1 матч или время сессии достигло минимума — формируем карточку
    if total_sec < config.MIN_SESSION_SEC and games_count < 1:
        return None, total_sec

    roles_map, names_map = db.get_heroes_maps(lang=lang)
    prefs = db.get_preferences(user_id)
    curr_snap = db.get_snapshot(user_id, mode)
    alt_mode = "quickplay" if mode == "competitive" else "competitive"
    alt_snap = db.get_snapshot(user_id, alt_mode)

    max_hero_blocks = 3 if mode == "competitive" else 4
    chosen_roles, other_heroes = select_role_heroes_and_footer(
        sess_heroes, prefs, roles_map, names_map, config.OBS_SEC, max_blocks=max_hero_blocks
    )

    role_blocks: List[HeroCardBlock] = []
    for role, hk, is_fb in chosen_roles:
        h_cnt = sess_heroes[hk]
        obs_list = db.get_observations(user_id, mode, hk, config.OBS_WINDOW)
        bucket = db.get_bucket(user_id, mode, hk)
        career_cnt = curr_snap.heroes.get(hk) if curr_snap else None
        alt_cnt = alt_snap.heroes.get(hk) if alt_snap else None
        h_name = names_map.get(hk, hk.capitalize())

        block = evaluate_hero_session(
            role=role,
            hero_key=hk,
            hero_name=h_name,
            is_fallback=is_fb,
            session_counters=h_cnt,
            observations=obs_list,
            career_counters=career_cnt,
            alt_career_counters=alt_cnt,
            bucket_time_sec=bucket.time_sec,
            obs_sec=config.OBS_SEC,
            min_obs=config.MIN_OBS,
            obs_window=config.OBS_WINDOW,
            lang=lang,
        )
        role_blocks.append(block)

    player_name = btag.split("#")[0].split("-")[0]
    mode_title = MODE_TITLES.get(lang, MODE_TITLES["ru"]).get(mode, "Quick Play" if lang == "en" else "Быстрая игра")

    avatar_path = os.path.join(assets.AVATARS_CACHE_DIR, f"{btag}.png")
    if not os.path.isfile(avatar_path):
        avatar_path = None

    tot_elim = sum(c.eliminations for k, c in sess_heroes.items() if k != "all-heroes")
    tot_deaths = sum(c.deaths for k, c in sess_heroes.items() if k != "all-heroes")
    sess_kd = (tot_elim / max(1.0, float(tot_deaths))) if tot_deaths > 0 else float(tot_elim)

    kd_status = "usual"
    kd_diff_pct = None
    c_snap_for_kd = curr_snap
    c_de = sum(h.deaths for hk, h in c_snap_for_kd.heroes.items() if hk != "all-heroes") if c_snap_for_kd else 0
    if c_de < 10 and alt_snap:
        alt_de = sum(h.deaths for hk, h in alt_snap.heroes.items() if hk != "all-heroes")
        if alt_de >= 10:
            c_snap_for_kd = alt_snap

    if c_snap_for_kd:
        c_el = sum(h.eliminations for hk, h in c_snap_for_kd.heroes.items() if hk != "all-heroes")
        c_de = sum(h.deaths for hk, h in c_snap_for_kd.heroes.items() if hk != "all-heroes")
        if c_snap_for_kd is curr_snap:
            c_el = max(0.0, c_el - tot_elim)
            c_de = max(0.0, c_de - tot_deaths)
        if c_de >= 5:
            c_kd = c_el / float(c_de)
            if c_kd > 0.05:
                kd_diff_pct = round(((sess_kd - c_kd) / c_kd) * 100)
                if kd_diff_pct >= 5:
                    kd_status = "better"
                elif kd_diff_pct <= -5:
                    kd_status = "worse"

    rank_prog = None
    season_number = None
    if mode == "competitive":
        ranks_json_data = db.get_user_ranks(user_id)
        user = db.get_user(user_id)
        plat = user[2] if user and len(user) > 2 else config.DEFAULT_PLATFORM
        rank_prog = extract_competitive_ranks(
            ranks_json_data,
            plat,
            session_won=meta["games_won"],
            session_lost=meta["games_lost"],
            lang=lang,
        )
        # Извлекаем номер сезона из данных рангов
        if isinstance(ranks_json_data, dict):
            for plat_data in ranks_json_data.values():
                if isinstance(plat_data, dict) and "season" in plat_data:
                    try:
                        season_number = int(plat_data["season"])
                    except (TypeError, ValueError):
                        season_number = None
                    if season_number is not None:
                        break

    actual_games = max(meta["games_played"], meta["games_won"] + meta["games_lost"])
    card_data = SessionCardData(
        player_name=player_name,
        gamemode=mode,
        mode_title=mode_title,
        duration_min=max(1, int(round(total_sec / 60.0))),
        games_played=actual_games,
        games_won=meta["games_won"],
        games_lost=meta["games_lost"],
        role_blocks=role_blocks,
        other_heroes=other_heroes,
        total_eliminations=int(tot_elim),
        total_deaths=int(tot_deaths),
        kd_val=round(sess_kd, 2),
        kd_status=kd_status,
        kd_diff_pct=kd_diff_pct,
        player_avatar_path=avatar_path,
        rank_progress=rank_prog,
        season_number=season_number,
        language=lang,
    )
    return card_data, total_sec


def format_card_caption(card: SessionCardData, warning_note: Optional[str] = None, lang: str = "ru") -> str:
    n = card.games_played
    word = format_matches_caption(n, lang)
    draws = max(0, n - (card.games_won + card.games_lost))
    draw_str = f"  🤝 {draws}" if draws > 0 else ""
    caption = f"🎮 <b>{card.player_name}</b> · {card.mode_title} · {n} {word} (✅ {card.games_won}  ❌ {card.games_lost}{draw_str})"
    if warning_note:
        caption += f"\n⚠️ <i>{warning_note}</i>"
    return caption


def make_settings_kb(chat_id: int, lang: str) -> InlineKeyboardMarkup:
    prefs = db.get_preferences(chat_id)
    _, names_map = db.get_heroes_maps(lang=lang)
    r_titles = ROLE_TITLES.get(lang, ROLE_TITLES["ru"])

    buttons = []
    for role in ROLE_ORDER:
        hk = prefs.get(role, "—")
        h_name = names_map.get(hk, hk)
        change_txt = t("change_action", lang)
        buttons.append(
            [InlineKeyboardButton(text=f"{r_titles.get(role, role.upper())}: {h_name} ({change_txt})", callback_data=f"pref_role:{role}")]
        )

    # Кнопка переключения языка
    btn_lang_text = "🌐 Язык: Русский 🇷🇺 (Switch to EN)" if lang == "ru" else "🌐 Language: English 🇬🇧 (Переключить на RU)"
    buttons.append([InlineKeyboardButton(text=btn_lang_text, callback_data="toggle_lang")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== TELEGRAM HANDLERS ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = db.get_user(message.chat.id)
    user_lang = db.get_user_language(message.chat.id)
    if not user:
        tg_lang = (message.from_user.language_code or "ru").lower()[:2]
        user_lang = "en" if tg_lang == "en" else "ru"

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        if user:
            await message.answer(
                t("start_already_registered", user_lang, btag=user[1]),
                parse_mode="HTML",
                reply_markup=main_reply_kb(user_lang),
            )
        else:
            await message.answer(
                t("start_greeting", user_lang),
                parse_mode="HTML",
                reply_markup=main_reply_kb(user_lang),
            )
        return
    await register_battletag(message, parts[1].strip(), user_lang=user_lang)


@dp.message(F.text.regexp(r"^[A-Za-zА-Яа-я0-9_]{2,16}[#-]\d{3,7}$"))
async def msg_battletag_direct(message: Message):
    await register_battletag(message, message.text.strip())


async def register_battletag(message: Message, raw_tag: str, user_lang: Optional[str] = None):
    if not user_lang:
        user_lang = db.get_user_language(message.chat.id)
        if not db.get_user(message.chat.id):
            tg_lang = (message.from_user.language_code or "ru").lower()[:2]
            user_lang = "en" if tg_lang == "en" else "ru"

    norm_tag = provider.normalize_battletag(raw_tag)
    wait_msg = await message.answer(t("checking_profile", user_lang, btag=norm_tag), parse_mode="HTML")

    async with aiohttp.ClientSession() as session:
        await ensure_heroes_catalog(session)
        summary = await provider.fetch_summary(session, norm_tag)
        if not summary or summary.get("privacy") == "private" or summary.get("is_public") is False:
            await wait_msg.edit_text(t("profile_not_found", user_lang))
            return

        qp_snap, _ = await provider.fetch_career(session, norm_tag, "quickplay")
        comp_snap, _ = await provider.fetch_career(session, norm_tag, "competitive")
        if not qp_snap and not comp_snap:
            await wait_msg.edit_text(t("profile_no_career", user_lang))
            return

        sum_ts = int(summary.get("last_updated_at") or 0)
        avatar_url = summary.get("avatar") or ""
        db.upsert_user(message.chat.id, norm_tag, config.DEFAULT_PLATFORM, sum_ts, avatar_url, language=user_lang)
        if summary.get("competitive"):
            db.update_user_ranks(message.chat.id, json.dumps(summary.get("competitive")))
        if avatar_url:
            await download_avatar_if_needed(session, norm_tag, avatar_url)

        if qp_snap:
            db.save_snapshot(message.chat.id, "quickplay", qp_snap)
        if comp_snap:
            db.save_snapshot(message.chat.id, "competitive", comp_snap)
        db.auto_init_preferences(message.chat.id, qp_snap, comp_snap)

    prefs = db.get_preferences(message.chat.id)
    roles_map, names_map = db.get_heroes_maps(lang=user_lang)
    r_titles = ROLE_TITLES.get(user_lang, ROLE_TITLES["ru"])
    pref_str = ", ".join(
        f"{r_titles.get(r, r.upper())}: <b>{names_map.get(prefs[r], prefs[r])}</b>" for r in ROLE_ORDER if r in prefs
    )

    await wait_msg.edit_text(
        t("profile_success", user_lang, btag=norm_tag, pref_str=pref_str),
        parse_mode="HTML",
    )
    await message.answer(t("menu_active", user_lang), reply_markup=main_reply_kb(user_lang))


@dp.message(Command("settings"))
@dp.message(F.text.in_([BTN_SETTINGS_RU, BTN_SETTINGS_EN]))
async def cmd_settings(message: Message):
    user = db.get_user(message.chat.id)
    user_lang = db.get_user_language(message.chat.id)
    if not user:
        await message.answer(t("need_register", user_lang), parse_mode="HTML")
        return

    kb = make_settings_kb(message.chat.id, user_lang)
    await message.answer(
        t("settings_title", user_lang, btag=user[1]),
        parse_mode="HTML",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "toggle_lang")
async def cb_toggle_lang(call: CallbackQuery):
    curr_lang = db.get_user_language(call.message.chat.id)
    new_lang = "en" if curr_lang == "ru" else "ru"
    db.set_user_language(call.message.chat.id, new_lang)
    user = db.get_user(call.message.chat.id)
    btag = user[1] if user else ""
    await call.answer(t("lang_switched", new_lang))
    await call.message.edit_text(
        t("settings_title", new_lang, btag=btag),
        parse_mode="HTML",
        reply_markup=make_settings_kb(call.message.chat.id, new_lang),
    )
    await call.message.answer(t("menu_active", new_lang), reply_markup=main_reply_kb(new_lang))


@dp.callback_query(F.data.startswith("pref_role:"))
async def cb_select_role(call: CallbackQuery):
    role = call.data.split(":", 1)[1]
    user_lang = db.get_user_language(call.message.chat.id)
    roles_map, names_map = db.get_heroes_maps(lang=user_lang)
    r_titles = ROLE_TITLES.get(user_lang, ROLE_TITLES["ru"])

    qp_snap = db.get_snapshot(call.message.chat.id, "quickplay")
    comp_snap = db.get_snapshot(call.message.chat.id, "competitive")
    totals: Dict[str, float] = {}
    for snap in (qp_snap, comp_snap):
        if snap:
            for hk, cnt in snap.heroes.items():
                totals[hk] = totals.get(hk, 0.0) + cnt.time_played

    role_heroes = [hk for hk, r in roles_map.items() if r == role]
    role_heroes.sort(key=lambda hk: (totals.get(hk, 0.0), names_map.get(hk, hk)), reverse=True)

    rows = []
    row = []
    h_suffix = "h" if user_lang == "en" else "ч"
    for hk in role_heroes:
        t_hrs = totals.get(hk, 0.0) / 3600.0
        suffix = f" ({t_hrs:.0f}{h_suffix})" if t_hrs >= 1 else ""
        row.append(InlineKeyboardButton(text=f"{names_map.get(hk, hk)}{suffix}", callback_data=f"set_hero:{role}:{hk}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    await call.message.edit_text(
        t("select_role_prompt", user_lang, role_title=r_titles.get(role, role.upper())),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_hero:"))
async def cb_set_hero(call: CallbackQuery):
    _, role, hk = call.data.split(":", 2)
    db.set_preferred_hero(call.message.chat.id, role, hk)
    user_lang = db.get_user_language(call.message.chat.id)
    _, names_map = db.get_heroes_maps(lang=user_lang)
    await call.answer(t("hero_selected", user_lang, name=names_map.get(hk, hk)))

    kb = make_settings_kb(call.message.chat.id, user_lang)
    await call.message.edit_text(
        t("prefs_updated", user_lang),
        parse_mode="HTML",
        reply_markup=kb,
    )



@dp.message(Command("close"))
async def cmd_close_manual(message: Message):
    user = db.get_user(message.chat.id)
    user_lang = db.get_user_language(message.chat.id)
    if not user:
        await message.answer(t("need_register", user_lang), parse_mode="HTML")
        return
    user_id = user[0]
    archived = []
    modes_map = MODE_TITLES.get(user_lang, MODE_TITLES["ru"])
    for mode in ("quickplay", "competitive"):
        if db.get_active_session(user_id, mode):
            db.archive_active_session(user_id, mode)
            archived.append(modes_map.get(mode, mode))
    if archived:
        await message.answer(t("cmd_close_success", user_lang, modes=", ".join(archived)), reply_markup=main_reply_kb(user_lang))
    else:
        await message.answer(t("cmd_close_empty", user_lang), reply_markup=main_reply_kb(user_lang))


@dp.message(Command("sync"))
@dp.message(Command("card"))
async def cmd_sync(message: Message):
    """
    Принудительно опрашивает серверы Blizzard на наличие новых сыгранных матчей
    и отправляет карточки активных сессий, если накопились сыгранные игры.
    """
    user = db.get_user(message.chat.id)
    user_lang = db.get_user_language(message.chat.id)
    if not user:
        await message.answer(t("need_register", user_lang), parse_mode="HTML")
        return

    user_id = user[0]
    btag = user[1]
    wait_text = "🔄 Опрашиваю серверы Blizzard на наличие сыгранных матчей..." if user_lang == "ru" else "🔄 Checking Blizzard servers for recent matches..."
    wait_msg = await message.answer(wait_text)

    async with aiohttp.ClientSession() as session:
        try:
            await poll_single_user(session, user)
        except Exception as poll_err:
            logger.error(f"SYNC_POLL_ERROR: {poll_err}", exc_info=True)

    sent_any = False
    now_ts = int(time.time())

    for mode in ("competitive", "quickplay"):
        try:
            card, total_sec = build_session_card_for_mode(user_id, btag, mode, lang=user_lang)
            if card is not None:
                png_bytes = render_session_card(card)
                photo = BufferedInputFile(png_bytes, filename=f"ow_{mode}_sync.png")
                await message.answer_photo(
                    photo=photo,
                    caption=format_card_caption(card, lang=user_lang),
                    parse_mode="HTML",
                    reply_markup=main_reply_kb(user_lang),
                )
                db.archive_active_session(user_id, mode, now_ts)
                sent_any = True
        except Exception as e:
            logger.error(f"SYNC_CARD_ERROR: mode={mode} {e}", exc_info=True)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not sent_any:
        no_matches_txt = (
            "ℹ️ <b>Нет активных или новых сыгранных матчей для карточки.</b>\n"
            "Если ты только что доиграл матч, статистика Blizzard может обновляться с задержкой (до 5–10 минут)."
            if user_lang == "ru"
            else "ℹ️ <b>No active or uncarded matches found.</b>\nBlizzard stats may update with a slight delay (5–10 minutes)."
        )
        await message.answer(no_matches_txt, parse_mode="HTML", reply_markup=main_reply_kb(user_lang))


async def send_weekly_report_to_user(
    user_id: int, btag: str, avatar_url: str, user_lang: str, target_dt: datetime
) -> Tuple[int, bool]:
    """
    Генерирует и отправляет карточки еженедельного отчёта за неделю, содержащую target_dt.
    Возвращает (количество отправленных карточек, были_ли_ошибки).
    """
    avatar_path = os.path.join(assets.AVATARS_CACHE_DIR, f"{btag}.png")
    if not os.path.isfile(avatar_path) and avatar_url:
        try:
            async with aiohttp.ClientSession() as sess:
                await download_avatar_if_needed(sess, btag, avatar_url)
        except Exception:
            pass

    target_ts = int(target_dt.timestamp())
    sent_count = 0
    had_failure = False
    for mode in ("quickplay", "competitive"):
        try:
            weekly_data = aggregate_weekly_report(user_id, mode, db, now_ts=target_ts, lang=user_lang)
            if avatar_path and os.path.isfile(avatar_path):
                weekly_data.player_avatar_path = avatar_path

            # Отправляем карточку для режима только если были матчи
            if weekly_data.total_matches > 0:
                png_bytes = render_weekly_card(weekly_data)
                photo = BufferedInputFile(png_bytes, filename=f"weekly_{mode}.png")
                caption = t(
                    "weekly_caption",
                    user_lang,
                    player_name=weekly_data.player_name,
                    mode_title=weekly_data.mode_title,
                    period=weekly_data.period_title,
                    matches=weekly_data.total_matches,
                    wr=weekly_data.winrate_pct,
                    time=fmt_time(weekly_data.total_time_sec),
                    sessions=weekly_data.sessions_count,
                    best_day=weekly_data.best_day_title,
                    hero_of_week=weekly_data.hero_of_the_week,
                )
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=main_reply_kb(user_lang),
                )
                sent_count += 1
                logger.info(
                    f"WEEKLY_REPORT_SENT: user={user_id} btag={btag} mode={mode} matches={weekly_data.total_matches}"
                )
        except Exception as e:
            had_failure = True
            logger.error(f"WEEKLY_REPORT_ERROR: user={user_id} mode={mode} err={e}", exc_info=True)

    return sent_count, had_failure


async def check_auto_weekly_reports():
    """
    Автоматическая отправка еженедельного отчёта всем активным пользователям.
    Срабатывает:
    - В воскресенье вечером (с 20:00) за завершающуюся неделю.
    - В понедельник за только что окончившуюся прошедшую неделю.
    Пометка в БД гарантирует, что каждому пользователю отчёт за неделю отправляется строго 1 раз.
    """
    now_dt = datetime.now(config.APP_TIMEZONE)
    if now_dt.weekday() == 6 and now_dt.hour >= 20:
        target_dt = now_dt
    elif now_dt.weekday() == 0:
        target_dt = now_dt - timedelta(days=1)
    else:
        return

    start_dt, _, _ = get_current_week_bounds(target_dt)
    week_key = start_dt.strftime("%Y-%m-%d")

    for user_row in db.list_users():
        user_id = user_row[0]
        btag = user_row[1]
        avatar_url = user_row[4] if len(user_row) > 4 else ""
        user_lang = user_row[5] if len(user_row) > 5 else db.get_user_language(user_id)

        last_sent = db.get_user_last_weekly(user_id)
        if last_sent == week_key:
            continue

        sent_count = 0
        had_failure = False
        try:
            sent_count, had_failure = await send_weekly_report_to_user(
                user_id, btag, avatar_url, user_lang, target_dt
            )
            if sent_count > 0 and not had_failure:
                logger.info(f"AUTO_WEEKLY_SUCCESS: user={user_id} btag={btag} week={week_key} sent={sent_count}")
        except Exception as e:
            logger.error(f"AUTO_WEEKLY_FAIL: user={user_id} err={e}", exc_info=True)
        # Mark the week only after at least one report was delivered.  A
        # transient API/render/Telegram failure (or an empty week) must not
        # permanently suppress the next retry.
        if sent_count > 0 and not had_failure:
            db.set_user_last_weekly(user_id, week_key)


@dp.message(Command("weekly"))
@dp.message(F.text.in_([BTN_WEEKLY_RU, BTN_WEEKLY_EN]))
async def cmd_weekly(message: Message):
    user = db.get_user(message.chat.id)
    user_lang = db.get_user_language(message.chat.id)
    if not user:
        await message.answer(t("need_register", user_lang), parse_mode="HTML")
        return

    status_msg = await message.answer(t("generating_weekly", user_lang))
    user_id = user[0]
    btag = user[1]
    avatar_url = user[4] if len(user) > 4 else ""

    sent_count, _ = await send_weekly_report_to_user(
        user_id, btag, avatar_url, user_lang, datetime.now(config.APP_TIMEZONE)
    )
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent_count == 0:
        await message.answer(
            t("weekly_empty", user_lang),
            parse_mode="HTML",
            reply_markup=main_reply_kb(user_lang),
        )


async def polling_worker():
    while True:
        await asyncio.sleep(config.POLL_INTERVAL_SEC)
        now_ts = int(time.time())
        try:
            # 1. Проверяем и отправляем автоматические еженедельные отчёты
            try:
                await check_auto_weekly_reports()
            except Exception as w_err:
                logger.error(f"AUTO_WEEKLY_WORKER_ERROR: {w_err}", exc_info=True)

            # 2. Опрашиваем пользователей и отправляем карточки сессий
            async with aiohttp.ClientSession() as session:
                await ensure_heroes_catalog(session)
                for user_row in db.list_users():
                    user_id = user_row[0]
                    btag = user_row[1]
                    user_lang = user_row[5] if len(user_row) > 5 else db.get_user_language(user_id)
                    try:
                        await poll_single_user(session, user_row)
                    except Exception as poll_err:
                        logger.error(f"POLL_ERROR: user={user_id} btag={btag} err={poll_err}", exc_info=True)
                        continue

                    for mode in ("quickplay", "competitive"):
                        try:
                            active = db.get_active_session(user_id, mode)
                            if not active:
                                continue
                            meta, _ = active
                            if (now_ts - meta["last_change_at"]) < config.SESSION_TIMEOUT_SEC:
                                continue

                            # Сессия протухла — собираем и пытаемся отправить карточку
                            card_build_failed = False
                            try:
                                card, total_sec = build_session_card_for_mode(user_id, btag, mode, lang=user_lang)
                            except Exception as card_err:
                                logger.error(
                                    f"CARD_BUILD_ERROR: user={user_id} mode={mode} err={card_err}",
                                    exc_info=True,
                                )
                                card, total_sec = None, 0.0
                                card_build_failed = True

                            has_new_activity = (
                                meta.get("games_played", 0) > meta.get("last_viewed_games", 0)
                                or (meta.get("last_viewed_games", 0) == 0 and total_sec >= config.MIN_SESSION_SEC)
                            )
                            should_archive = False
                            if card is not None and has_new_activity:
                                try:
                                    png_bytes = render_session_card(card)
                                    photo = BufferedInputFile(png_bytes, filename=f"ow_{mode}.png")
                                    await bot.send_photo(
                                        chat_id=user_id,
                                        photo=photo,
                                        caption=format_card_caption(card, lang=user_lang),
                                        parse_mode="HTML",
                                        reply_markup=main_reply_kb(user_lang),
                                    )
                                    logger.info(
                                        f"AUTO_SESSION_SENT: user={user_id} btag={btag} mode={mode} games={meta.get('games_played')}"
                                    )
                                    should_archive = True
                                except Exception as send_err:
                                    logger.error(f"AUTO_SEND_FAIL: user={user_id} mode={mode} err={send_err}")
                            elif card is None and not card_build_failed:
                                logger.info(
                                    f"SESSION_DROPPED_SHORT: user={user_id} mode={mode} total_sec={total_sec:.1f}"
                                )
                                should_archive = True
                            elif card_build_failed:
                                logger.info(
                                    f"SESSION_RETAINED_BUILD_ERROR: user={user_id} mode={mode}"
                                )
                            else:
                                logger.info(
                                    f"AUTO_SESSION_ARCHIVED_SILENT: user={user_id} mode={mode} games={meta.get('games_played')} already viewed"
                                )
                                should_archive = True

                            # Keep failed sends active so the next polling
                            # cycle can retry instead of silently losing the
                            # whole session.
                            if should_archive:
                                db.archive_active_session(user_id, mode, now_ts)

                        except Exception as mode_err:
                            logger.error(
                                f"MODE_TIMEOUT_ERROR: user={user_id} btag={btag} mode={mode} err={mode_err}",
                                exc_info=True,
                            )
                            # Preserve the active session after unexpected
                            # errors; it is safer to retry than to discard
                            # data that has not been delivered.

        except Exception as e:
            logger.error(f"WORKER_ERROR: {e}", exc_info=True)


async def main():
    asyncio.create_task(polling_worker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
