import io
import os
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from assets import (
    get_banner_image,
    get_hero_avatar,
    get_player_avatar,
    load_app_fonts,
)
from i18n import format_time_duration, t
from models import DailyMatchStats, HeroWeeklyStats, WeeklyReportData

# Палитра
COLOR_CANVAS_BG = (244, 246, 250)
COLOR_CARD_BG = (255, 255, 255)
COLOR_CARD_BORDER = (220, 227, 238)
COLOR_DIVIDER = (235, 240, 247)

COLOR_TEXT_MAIN = (34, 39, 62)       # #22273e
COLOR_TEXT_MUTED = (120, 134, 158)   # #78869e
COLOR_TEXT_LIGHT = (160, 174, 196)   # #a0aec4

COLOR_PRIMARY = (0, 157, 255)        # #009dff
COLOR_OVERWATCH_ORANGE = (240, 100, 20)  # #f06414
COLOR_SLATE_BORDER = (188, 200, 222) # #bcc8de

COLOR_WIN_GREEN = (16, 185, 129)     # #10b981
COLOR_WIN_BG = (236, 253, 245)
COLOR_WIN_BORDER = (167, 243, 208)

COLOR_LOSS_RED = (239, 68, 68)       # #ef4444
COLOR_LOSS_BG = (254, 242, 242)
COLOR_LOSS_BORDER = (254, 202, 202)

COLOR_NEUTRAL_BG = (241, 245, 249)


def fmt_time(sec: float) -> str:
    m = int(round(sec / 60.0))
    if m >= 60:
        return f"{m // 60} ч {m % 60} мин"
    return f"{m} мин"


def fmt_stat(val: float) -> str:
    if val >= 1000:
        return f"{val:,.0f}".replace(",", " ")
    return f"{val:.1f}" if (val % 1 != 0 or val < 10) else f"{val:.0f}"


def render_weekly_card(data: WeeklyReportData) -> bytes:
    fonts = load_app_fonts()
    W = 1040
    pad = 28
    lang = getattr(data, "language", "ru") or "ru"

    header_h = 144
    kpi_h = 96
    histo_h = 240
    heroes_h = 56 + (len(data.top_heroes) * 64 if data.top_heroes else 60)
    footer_h = 84

    H = 24 + header_h + 16 + kpi_h + 16 + histo_h + 16 + heroes_h + 16 + footer_h + 28

    # 1. Холст
    img = Image.new("RGBA", (W, H), (*COLOR_CANVAS_BG, 255))

    # 2. Баннер в шапке
    hero_keys = [h.hero_key for h in data.top_heroes]
    banner = get_banner_image(hero_keys=hero_keys, width=W, height=header_h + 70, fade_start_y=30)
    img.paste(banner, (0, 0), banner)

    draw = ImageDraw.Draw(img)

    # ==================== 1. ШАПКА ====================
    hy = 24
    sub_bg = Image.new("RGBA", (W - 2 * pad, header_h), (255, 255, 255, 242))
    sub_mask = Image.new("L", (W - 2 * pad, header_h), 0)
    ImageDraw.Draw(sub_mask).rounded_rectangle([0, 0, W - 2 * pad - 1, header_h - 1], radius=16, fill=255)
    img.paste(sub_bg, (pad, hy), sub_mask)
    draw.rounded_rectangle([pad, hy, W - pad, hy + header_h], radius=16, outline=COLOR_CARD_BORDER, width=1)

    pfp_size = 72
    pfp_x = pad + 20
    pfp_y = hy + (header_h - pfp_size) // 2
    player_pfp = get_player_avatar(
        avatar_path_or_url=data.player_avatar_path,
        player_name=data.player_name,
        size=pfp_size,
        border_color=COLOR_PRIMARY,
        border_width=2,
    )
    img.paste(player_pfp, (pfp_x, pfp_y), player_pfp)

    text_x = pfp_x + pfp_size + 18
    player_title = data.player_name.upper()
    sub_str = f"{data.period_title}  •  {data.mode_title}"
    draw.text((text_x, hy + 30), player_title, font=fonts["h1"], fill=COLOR_TEXT_MAIN)
    draw.text((text_x, hy + 68), sub_str, font=fonts["body"], fill=COLOR_TEXT_MUTED)

    left_w = text_x + max(
        draw.textlength(player_title, font=fonts["h1"]),
        draw.textlength(sub_str, font=fonts["body"]),
    )

    # Бейдж винрейта справа
    badge_w = 170
    badge_h = 76
    badge_x = W - pad - badge_w - 20
    badge_y = hy + (header_h - badge_h) // 2
    wr_val = data.winrate_pct
    wr_col = COLOR_WIN_GREEN if wr_val >= 50 else COLOR_LOSS_RED
    wr_bg = COLOR_WIN_BG if wr_val >= 50 else COLOR_LOSS_BG
    wr_border = COLOR_WIN_BORDER if wr_val >= 50 else COLOR_LOSS_BORDER

    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=12, fill=wr_bg, outline=wr_border, width=1)
    wr_text = f"WR {wr_val}%"
    wr_bbox = draw.textbbox((0, 0), wr_text, font=fonts["h1"])
    wr_tw = wr_bbox[2] - wr_bbox[0]
    draw.text((badge_x + (badge_w - wr_tw) / 2, badge_y + 15), wr_text, font=fonts["h1"], fill=wr_col)
    wr_sub = t("weekly_sub", lang)
    sub_bbox = draw.textbbox((0, 0), wr_sub, font=fonts["small"])
    sub_tw = sub_bbox[2] - sub_bbox[0]
    draw.text((badge_x + (badge_w - sub_tw) / 2, badge_y + 47), wr_sub, font=fonts["small"], fill=COLOR_TEXT_MUTED)

    # Центр: Счет побед/поражений
    w_str = f"{data.total_wins}W"
    sep_str = " - "
    l_str = f"{data.total_losses}L"
    w_len = draw.textlength(w_str, font=fonts["huge"])
    sep_len = draw.textlength(sep_str, font=fonts["huge"])
    l_len = draw.textlength(l_str, font=fonts["huge"])
    score_total_w = w_len + sep_len + l_len

    available_gap = badge_x - left_w
    score_x = left_w + max(16, (available_gap - score_total_w) / 2.0)
    score_y = hy + 28

    draw.text((score_x, score_y), w_str, font=fonts["huge"], fill=COLOR_WIN_GREEN)
    draw.text((score_x + w_len, score_y), sep_str, font=fonts["huge"], fill=COLOR_SLATE_BORDER)
    draw.text((score_x + w_len + sep_len, score_y), l_str, font=fonts["huge"], fill=COLOR_LOSS_RED)

    sub_score = t("weekly_score_title", lang)
    sub_sc_w = draw.textlength(sub_score, font=fonts["tiny"])
    draw.text((score_x + (score_total_w - sub_sc_w) / 2, score_y + 60), sub_score, font=fonts["tiny"], fill=COLOR_TEXT_LIGHT)

    # ==================== 2. ЧЕТЫРЕ КАРТОЧКИ KPI ====================
    kpi_y = hy + header_h + 16
    kpi_items = [
        (t("weekly_kpi_matches", lang), f"{data.total_matches}"),
        (t("weekly_kpi_winrate", lang), f"{data.winrate_pct}%"),
        (t("weekly_kpi_time", lang), format_time_duration(data.total_time_sec, lang)),
        (t("weekly_kpi_sessions", lang), f"{data.sessions_count}"),
    ]
    card_w = (W - 2 * pad - 3 * 14) / 4.0

    for i, (title, val) in enumerate(kpi_items):
        cx = int(pad + i * (card_w + 14))
        draw.rounded_rectangle([cx, kpi_y, cx + card_w, kpi_y + kpi_h], radius=14, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        draw.text((cx + 18, kpi_y + 16), title, font=fonts["small_b"], fill=COLOR_TEXT_MUTED)
        draw.text((cx + 18, kpi_y + 44), val, font=fonts["h1"], fill=COLOR_TEXT_MAIN)

    # ==================== 3. ГИСТОГРАММА МАТЧИ ПО ДНЯМ ====================
    histo_y = kpi_y + kpi_h + 16
    draw.rounded_rectangle([pad, histo_y, W - pad, histo_y + histo_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)

    draw.text((pad + 24, histo_y + 16), t("weekly_histo_title", lang), font=fonts["bold"], fill=COLOR_TEXT_MAIN)
    draw.text((pad + 175, histo_y + 18), t("weekly_histo_sub", lang), font=fonts["small"], fill=COLOR_TEXT_MUTED)

    # Легенда
    leg_x = W - pad - 210
    draw.rounded_rectangle([leg_x, histo_y + 18, leg_x + 12, histo_y + 30], radius=3, fill=COLOR_WIN_GREEN)
    draw.text((leg_x + 18, histo_y + 16), t("weekly_histo_wins", lang), font=fonts["small"], fill=COLOR_TEXT_MUTED)
    draw.rounded_rectangle([leg_x + 90, histo_y + 18, leg_x + 102, histo_y + 30], radius=3, fill=COLOR_LOSS_RED)
    draw.text((leg_x + 108, histo_y + 16), t("weekly_histo_losses", lang), font=fonts["small"], fill=COLOR_TEXT_MUTED)

    # Отрисовка колонок гистограммы
    chart_y_base = histo_y + histo_h - 52
    chart_max_h = 100
    max_day_games = max([d.games_played for d in data.days] + [1])

    bar_slot_w = (W - 2 * pad - 48) / 7.0
    bar_width = 38

    for d_idx, day in enumerate(data.days):
        slot_center = pad + 24 + d_idx * bar_slot_w + bar_slot_w / 2.0
        bx1 = slot_center - bar_width / 2.0
        bx2 = slot_center + bar_width / 2.0

        # Метка дня недели и даты
        day_lbl = day.day_name
        dl_w = draw.textlength(day_lbl, font=fonts["bold"])
        draw.text((slot_center - dl_w / 2, chart_y_base + 8), day_lbl, font=fonts["bold"], fill=COLOR_TEXT_MAIN)

        sub_info = f"{format_time_duration(day.time_sec, lang)}" if day.time_sec > 0 else "—"
        si_w = draw.textlength(sub_info, font=fonts["tiny"])
        draw.text((slot_center - si_w / 2, chart_y_base + 26), sub_info, font=fonts["tiny"], fill=COLOR_TEXT_MUTED)

        # Бейдж «ЛУЧШИЙ ДЕНЬ»
        if day.is_best_day and day.games_played > 0:
            bd_str = t("weekly_histo_best", lang)
            bd_w = draw.textlength(bd_str, font=fonts["tiny"]) + 12
            draw.rounded_rectangle([slot_center - bd_w / 2, chart_y_base - chart_max_h - 38, slot_center + bd_w / 2, chart_y_base - chart_max_h - 22], radius=4, fill=COLOR_PRIMARY)
            draw.text((slot_center - (bd_w - 12) / 2, chart_y_base - chart_max_h - 37), bd_str, font=fonts["tiny"], fill=(255, 255, 255))

        if day.games_played == 0:
            # Тонкая линия-заглушка
            draw.rounded_rectangle([bx1, chart_y_base - 4, bx2, chart_y_base], radius=2, fill=COLOR_DIVIDER)
            continue

        # Высота столбца
        col_total_h = max(14, int((day.games_played / max_day_games) * chart_max_h))
        top_y = chart_y_base - col_total_h

        # Разбивка на победы и поражения
        win_ratio = (day.games_won / day.games_played) if day.games_played > 0 else 0.0
        win_h = int(col_total_h * win_ratio)
        loss_h = col_total_h - win_h

        # Рисуем стек
        if loss_h > 0 and win_h > 0:
            # Верхний сегмент (поражения)
            draw.rounded_rectangle([bx1, top_y, bx2, top_y + loss_h], radius=4, fill=COLOR_LOSS_RED)
            # Нижний сегмент (победы)
            draw.rounded_rectangle([bx1, top_y + loss_h, bx2, chart_y_base], radius=4, fill=COLOR_WIN_GREEN)
        elif win_h > 0:
            draw.rounded_rectangle([bx1, top_y, bx2, chart_y_base], radius=5, fill=COLOR_WIN_GREEN)
        else:
            draw.rounded_rectangle([bx1, top_y, bx2, chart_y_base], radius=5, fill=COLOR_LOSS_RED)

        # Число матчей над столбцом
        cnt_str = f"{day.games_played}"
        cw = draw.textlength(cnt_str, font=fonts["small_b"])
        draw.text((slot_center - cw / 2, top_y - 18), cnt_str, font=fonts["small_b"], fill=COLOR_TEXT_MAIN)

    # ==================== 5. ГЕРОИ НЕДЕЛИ ====================
    heroes_y = histo_y + histo_h + 16
    draw.rounded_rectangle([pad, heroes_y, W - pad, heroes_y + heroes_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)

    # Заголовок таблицы
    draw.text((pad + 24, heroes_y + 16), t("weekly_heroes_title", lang), font=fonts["bold"], fill=COLOR_TEXT_MAIN)

    # Колонки таблицы справа
    c_score_x = W - pad - 480
    c_elim_x = W - pad - 380
    c_deaths_x = W - pad - 280
    c_dmg_x = W - pad - 180
    c_heal_x = W - pad - 90

    draw.text((c_score_x, heroes_y + 18), t("weekly_col_score", lang), font=fonts["tiny"], fill=COLOR_TEXT_MUTED)
    draw.text((c_elim_x, heroes_y + 18), t("weekly_col_elims", lang), font=fonts["tiny"], fill=COLOR_TEXT_MUTED)
    draw.text((c_deaths_x, heroes_y + 18), t("weekly_col_deaths", lang), font=fonts["tiny"], fill=COLOR_TEXT_MUTED)
    draw.text((c_dmg_x, heroes_y + 18), t("weekly_col_dmg", lang), font=fonts["tiny"], fill=COLOR_TEXT_MUTED)
    draw.text((c_heal_x, heroes_y + 18), t("weekly_col_heal", lang), font=fonts["tiny"], fill=COLOR_TEXT_MUTED)

    draw.line([(pad + 24, heroes_y + 44), (W - pad - 24, heroes_y + 44)], fill=COLOR_DIVIDER, width=1)

    if not data.top_heroes:
        draw.text((pad + 24, heroes_y + 60), t("weekly_no_heroes", lang), font=fonts["body"], fill=COLOR_TEXT_MUTED)
    else:
        for idx, h_stat in enumerate(data.top_heroes):
            row_y = heroes_y + 54 + idx * 64
            if idx > 0:
                draw.line([(pad + 24, row_y - 6), (W - pad - 24, row_y - 6)], fill=COLOR_DIVIDER, width=1)

            # PFP героя
            h_icon = get_hero_avatar(h_stat.hero_key, size=44, radius=10, border_color=COLOR_CARD_BORDER)
            img.paste(h_icon, (pad + 24, row_y), h_icon)

            # Имя и время
            hx = pad + 24 + 44 + 14
            draw.text((hx, row_y + 2), h_stat.hero_name, font=fonts["bold"], fill=COLOR_TEXT_MAIN)
            draw.text((hx, row_y + 24), format_time_duration(h_stat.time_sec, lang), font=fonts["small"], fill=COLOR_TEXT_MUTED)

            # Счёт
            has_score = (h_stat.games_won + h_stat.games_lost) > 0
            score_s = f"{h_stat.games_won}-{h_stat.games_lost}" if has_score else "—"
            if has_score:
                s_col = COLOR_WIN_GREEN if h_stat.games_won >= h_stat.games_lost else COLOR_LOSS_RED
            else:
                s_col = COLOR_TEXT_LIGHT
            draw.text((c_score_x, row_y + 12), score_s, font=fonts["bold"], fill=s_col)

            # Метрики за 10 мин
            draw.text((c_elim_x, row_y + 12), fmt_stat(h_stat.eliminations_10m), font=fonts["body"], fill=COLOR_TEXT_MAIN)
            draw.text((c_deaths_x, row_y + 12), fmt_stat(h_stat.deaths_10m), font=fonts["body"], fill=COLOR_TEXT_MAIN)
            draw.text((c_dmg_x, row_y + 12), fmt_stat(h_stat.damage_10m), font=fonts["body"], fill=COLOR_TEXT_MAIN)
            heal_s = fmt_stat(h_stat.healing_10m) if h_stat.healing_10m > 0 else "—"
            draw.text((c_heal_x, row_y + 12), heal_s, font=fonts["body"], fill=COLOR_TEXT_MAIN)

    # ==================== 6. ИТОГИ НЕДЕЛИ (ХАЙЛАЙТЫ) ====================
    foot_y = heroes_y + heroes_h + 16
    draw.rounded_rectangle([pad, foot_y, W - pad, foot_y + footer_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)

    highlights = [
        (t("weekly_hl_hero", lang), data.hero_of_the_week),
        (t("weekly_hl_session", lang), data.longest_session_str),
        (t("weekly_hl_day", lang), data.best_day_title),
    ]
    h_col_w = (W - 2 * pad) / 3.0
    for i, (h_title, h_val) in enumerate(highlights):
        hx = pad + i * h_col_w
        if i > 0:
            draw.line([(hx, foot_y + 16), (hx, foot_y + footer_h - 16)], fill=COLOR_DIVIDER, width=1)
        draw.text((hx + 24, foot_y + 16), h_title, font=fonts["tiny"], fill=COLOR_TEXT_MUTED)
        draw.text((hx + 24, foot_y + 40), h_val, font=fonts["bold"], fill=COLOR_TEXT_MAIN)

    final_card = Image.new("RGB", img.size, COLOR_CANVAS_BG)
    final_card.paste(img, (0, 0), img)

    buf = io.BytesIO()
    final_card.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
