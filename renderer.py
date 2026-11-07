from datetime import datetime
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
from i18n import t
from models import HeroCardBlock, MetricScaleResult, RoleRankProgress, SessionCardData


# ==================== ЦВЕТОВАЯ ПАЛИТРА СВЕТЛОЙ ТЕМЫ ====================
COLOR_CANVAS_BG = (244, 246, 250)    # Мягкий светлый фоновый холст
COLOR_CARD_BG = (255, 255, 255)      # Чистый белый для блоков и карточек
COLOR_CARD_BORDER = (220, 227, 238)  # Нежный контур карточек
COLOR_DIVIDER = (235, 240, 247)      # Разделители внутри блоков

COLOR_TEXT_MAIN = (34, 39, 62)       # Основной темный текст (#22273e)
COLOR_TEXT_MUTED = (120, 134, 158)   # Второстепенный текст (#78869e)
COLOR_TEXT_LIGHT = (160, 174, 196)   # Светлые подписи (#a0aec4)

COLOR_PRIMARY = (0, 157, 255)        # Electric Cyan (#009dff)
COLOR_OVERWATCH_ORANGE = (240, 100, 20)  # Декоративный оранжевый (#f06414)
COLOR_SLATE_BORDER = (188, 200, 222) # Контур нормальной зоны (#bcc8de)

# Семантические приятные цвета для побед и поражений
COLOR_WIN_GREEN = (16, 185, 129)     # Приятный изумрудный зеленый (#10b981)
COLOR_WIN_BG = (236, 253, 245)       # Мягкая зеленая плашка
COLOR_WIN_BORDER = (167, 243, 208)

COLOR_LOSS_RED = (239, 68, 68)       # Приятный красный (#ef4444)
COLOR_LOSS_BG = (254, 242, 242)      # Мягкая красная плашка
COLOR_LOSS_BORDER = (254, 202, 202)

COLOR_NEUTRAL_BG = (241, 245, 249)   # Нейтральная плашка «как обычно»
COLOR_NEUTRAL_BORDER = (203, 213, 225)
COLOR_NEUTRAL_DOT = (100, 116, 139)

COLOR_TRACK_BG = (241, 245, 249)     # Фон трека шкалы
COLOR_BAND_BG = (224, 234, 246)      # Зона нормы (#e0eaf6)

DIVISION_COLORS = {
    "bronze": (194, 126, 75),
    "silver": (188, 200, 222),
    "gold": (234, 179, 8),
    "platinum": (34, 211, 238),
    "diamond": (147, 197, 253),
    "master": (244, 114, 182),
    "grandmaster": (251, 191, 36),
    "champion": (192, 132, 252),
    "unranked": (160, 174, 196),
}


def fmt_num(val: float, metric_type: str) -> str:
    if metric_type == "deaths" or metric_type == "eliminations":
        return f"{val:.1f}" if (val % 1 != 0 or val < 10) else f"{val:.0f}"
    if val >= 1000:
        return f"{val:,.0f}".replace(",", " ")
    return f"{val:.0f}"


def render_session_card(data: SessionCardData) -> bytes:
    fonts = load_app_fonts()
    W = 1040
    pad = 28
    lang = getattr(data, "language", "ru") or "ru"

    # Динамический расчет высоты
    num_blocks = max(1, len(data.role_blocks))
    # Блок героя теперь вмещает 3 шкалы (Урон/Хил, Смерти, Убийства)
    block_h = 236
    footer_h = 56 if data.other_heroes else 0
    header_h = 144

    # Дополнительный блок для соревновательного режима (прогресс рангов)
    has_comp_ranks = bool(data.gamemode == "competitive" and data.rank_progress)
    comp_h = 188 if has_comp_ranks else 0

    H = 24 + header_h + 18 + (comp_h + 16 if has_comp_ranks else 0) + num_blocks * (block_h + 16) + footer_h + 24

    # 1. Создаем холст
    img = Image.new("RGBA", (W, H), (*COLOR_CANVAS_BG, 255))

    # 2. Формируем верхний баннер из pictures/
    hero_keys = [b.hero_key for b in data.role_blocks]
    banner = get_banner_image(hero_keys=hero_keys, width=W, height=header_h + 60, fade_start_y=30)
    img.paste(banner, (0, 0), banner)

    draw = ImageDraw.Draw(img)

    # ==================== ШАПКА КАРТОЧКИ ====================
    hy = 24
    card_shape = [pad, hy, W - pad, hy + header_h]
    sub_bg = Image.new("RGBA", (W - 2 * pad, header_h), (255, 255, 255, 240))
    sub_mask = Image.new("L", (W - 2 * pad, header_h), 0)
    ImageDraw.Draw(sub_mask).rounded_rectangle([0, 0, W - 2 * pad - 1, header_h - 1], radius=16, fill=255)
    img.paste(sub_bg, (pad, hy), sub_mask)
    draw.rounded_rectangle(card_shape, radius=16, outline=COLOR_CARD_BORDER, width=1)

    # 1. Слева: Аватарка игрока + Инфо
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
    date_str = datetime.now().strftime("%d.%m.%Y")
    games_word = "games" if lang == "en" else "игр"
    min_word = "min" if lang == "en" else "мин"
    sub_str = f"{data.mode_title}  •  {data.games_played} {games_word}  •  {data.duration_min} {min_word}  •  {date_str}"

    draw.text((text_x, hy + 26), player_title, font=fonts["h1"], fill=COLOR_TEXT_MAIN)
    draw.text((text_x, hy + 64), sub_str, font=fonts["body"], fill=COLOR_TEXT_MUTED)

    # Интерактивный бейдж K/D (зеленый / красный с треугольником)
    kd_val = data.kd_val
    if kd_val <= 0.0:
        tot_e = data.total_eliminations
        tot_d = data.total_deaths
        kd_val = (tot_e / max(1.0, float(tot_d))) if tot_d > 0 else float(tot_e)

    if data.kd_status == "better":
        kd_col, kd_bg, kd_border = COLOR_WIN_GREEN, COLOR_WIN_BG, COLOR_WIN_BORDER
        diff_str = f" (+{data.kd_diff_pct}%)" if data.kd_diff_pct is not None else ""
        kd_text = f"K/D {kd_val:.1f}  ▲{diff_str}"
    elif data.kd_status == "worse":
        kd_col, kd_bg, kd_border = COLOR_LOSS_RED, COLOR_LOSS_BG, COLOR_LOSS_BORDER
        diff_str = f" ({data.kd_diff_pct}%)" if data.kd_diff_pct is not None else ""
        kd_text = f"K/D {kd_val:.1f}  ▼{diff_str}"
    else:
        kd_col, kd_bg, kd_border = COLOR_PRIMARY, (240, 246, 255), (188, 215, 245)
        norm_label = "norm" if lang == "en" else "норма"
        kd_text = f"K/D {kd_val:.1f}  ({norm_label})"

    kd_w = draw.textlength(kd_text, font=fonts["small_b"]) + 20
    draw.rounded_rectangle([text_x, hy + 94, text_x + kd_w, hy + 120], radius=6, fill=kd_bg, outline=kd_border, width=1)
    draw.text((text_x + 10, hy + 98), kd_text, font=fonts["small_b"], fill=kd_col)

    left_w = text_x + max(
        draw.textlength(player_title, font=fonts["h1"]),
        draw.textlength(sub_str, font=fonts["body"]),
        kd_w,
    )

    # 2. Справа: Бейдж винрейта
    total_decided = data.games_won + data.games_lost
    wr = round((data.games_won / total_decided) * 100) if total_decided > 0 else 0
    if wr >= 50:
        wr_col, wr_bg, wr_border = COLOR_WIN_GREEN, COLOR_WIN_BG, COLOR_WIN_BORDER
    elif total_decided > 0:
        wr_col, wr_bg, wr_border = COLOR_LOSS_RED, COLOR_LOSS_BG, COLOR_LOSS_BORDER
    else:
        wr_col, wr_bg, wr_border = COLOR_TEXT_MUTED, COLOR_NEUTRAL_BG, COLOR_NEUTRAL_BORDER

    badge_w = 170
    badge_h = 76
    badge_x = W - pad - badge_w - 20
    badge_y = hy + (header_h - badge_h) // 2
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=12, fill=wr_bg, outline=wr_border, width=1)
    
    wr_text = f"WR {wr}%"
    wr_bbox = draw.textbbox((0, 0), wr_text, font=fonts["h1"])
    wr_tw = wr_bbox[2] - wr_bbox[0]
    draw.text((badge_x + (badge_w - wr_tw) / 2, badge_y + 15), wr_text, font=fonts["h1"], fill=wr_col)
    
    wr_sub = t("card_session_badge", lang)
    sub_bbox = draw.textbbox((0, 0), wr_sub, font=fonts["small"])
    sub_tw = sub_bbox[2] - sub_bbox[0]
    draw.text((badge_x + (badge_w - sub_tw) / 2, badge_y + 47), wr_sub, font=fonts["small"], fill=COLOR_TEXT_MUTED)

    # 3. Центр: Крупный счет матчей 3W - 3L
    w_str = f"{data.games_won}W"
    sep_str = " - "
    l_str = f"{data.games_lost}L"
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

    sub_score = t("card_score_title", lang)
    sub_sc_w = draw.textlength(sub_score, font=fonts["tiny"])
    draw.text((score_x + (score_total_w - sub_sc_w) / 2, score_y + 60), sub_score, font=fonts["tiny"], fill=COLOR_TEXT_LIGHT)

    curr_y = hy + header_h + 18

    # ==================== БЛОК ПРОГРЕССА РАНГОВ (ДЛЯ СОРЕВНОВАТЕЛЬНОГО РЕЖИМА) ====================
    if has_comp_ranks and data.rank_progress:
        draw.rounded_rectangle([pad, curr_y, W - pad, curr_y + comp_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        
        # Шапка карточки рангов
        rank_header = t("card_ranks_title", lang)
        draw.text((pad + 24, curr_y + 16), rank_header, font=fonts["bold"], fill=COLOR_TEXT_MAIN)
        rh_w = draw.textlength(rank_header, font=fonts["bold"])
        draw.text((pad + 24 + rh_w + 14, curr_y + 18), t("card_comp_subtitle", lang), font=fonts["small"], fill=COLOR_TEXT_MUTED)

        badge_s = f"{t('card_season_prefix', lang)} {data.season_number}" if data.season_number else t("card_rank_default", lang)
        bw = draw.textlength(badge_s, font=fonts["tiny"]) + 16
        draw.rounded_rectangle([W - pad - 24 - bw, curr_y + 16, W - pad - 24, curr_y + 36], radius=6, fill=(255, 247, 237), outline=(254, 215, 170), width=1)
        draw.text((W - pad - 16 - bw + 4, curr_y + 19), badge_s, font=fonts["tiny"], fill=COLOR_OVERWATCH_ORANGE)

        draw.line([(pad + 24, curr_y + 44), (W - pad - 24, curr_y + 44)], fill=COLOR_DIVIDER, width=1)

        # 3 строки ролей
        for r_idx, rk in enumerate(data.rank_progress[:3]):
            ry = curr_y + 54 + r_idx * 42
            _draw_rank_role_row(draw, fonts, rk, pad + 24, ry, W - pad - 24, lang=lang)

        curr_y += comp_h + 16

    # ==================== БЛОКИ РОЛЕЙ И ГЕРОЕВ ====================
    if not data.role_blocks:
        draw.rounded_rectangle([pad, curr_y, W - pad, curr_y + block_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        draw.text(
            (pad + 28, curr_y + 60),
            t("card_no_10min_title", lang),
            font=fonts["h2"],
            fill=COLOR_TEXT_MAIN,
        )
        draw.text(
            (pad + 28, curr_y + 96),
            t("card_no_10min_sub", lang),
            font=fonts["body"],
            fill=COLOR_TEXT_MUTED,
        )
        curr_y += block_h + 16

    for block in data.role_blocks:
        draw.rounded_rectangle([pad, curr_y, W - pad, curr_y + block_h], radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)

        # Цветная плашка роли
        if block.role == "damage":
            role_col = COLOR_PRIMARY
            role_bg = (235, 245, 255)
        elif block.role == "support":
            role_col = COLOR_WIN_GREEN
            role_bg = COLOR_WIN_BG
        else:
            role_col = COLOR_OVERWATCH_ORANGE
            role_bg = (255, 247, 237)

        # Вертикальная цветная полоска роли слева
        draw.rounded_rectangle([pad + 14, curr_y + 16, pad + 19, curr_y + block_h - 16], radius=3, fill=role_col)

        # 1. PFP героя (скругленный квадрат)
        hero_pfp_size = 54
        hero_pfp_x = pad + 30
        hero_pfp_y = curr_y + 16
        hero_icon = get_hero_avatar(block.hero_key, size=hero_pfp_size, radius=12, border_color=COLOR_CARD_BORDER)
        img.paste(hero_icon, (hero_pfp_x, hero_pfp_y), hero_icon)

        # 2. Шапка блока: Роль (pill), Имя героя, время, статус
        info_x = hero_pfp_x + hero_pfp_size + 16
        hy_top = curr_y + 20

        # Ролевой бейдж
        role_tag = f" {block.role_title} "
        rt_len = draw.textlength(role_tag, font=fonts["small_b"]) + 12
        draw.rounded_rectangle([info_x, hy_top, info_x + rt_len, hy_top + 22], radius=6, fill=role_bg)
        draw.text((info_x + 6, hy_top + 3), role_tag, font=fonts["small_b"], fill=role_col)

        min_s = t("card_min_abbr", lang)
        hero_title = f"{block.hero_name}  ({block.time_min} {min_s})"
        title_x = info_x + rt_len + 12
        draw.text((title_x, hy_top), hero_title, font=fonts["h2"], fill=COLOR_TEXT_MAIN)
        ht_w = draw.textlength(hero_title, font=fonts["h2"])

        # Метка «не основной»
        if block.is_fallback:
            fb_x = title_x + ht_w + 12
            fb_text = t("card_fallback_tag", lang)
            fb_w = draw.textlength(fb_text, font=fonts["small"]) + 16
            draw.rounded_rectangle([fb_x, hy_top + 2, fb_x + fb_w, hy_top + 22], radius=6, fill=COLOR_NEUTRAL_BG)
            draw.text((fb_x + 8, hy_top + 4), fb_text, font=fonts["small"], fill=COLOR_TEXT_MUTED)

        # 3. Плашка итогового вердикта справа
        vt_norm = block.verdict_text.lower()
        if vt_norm in ("лучше обычного", "above average", "better than usual"):
            v_col, v_bg, v_border = COLOR_WIN_GREEN, COLOR_WIN_BG, COLOR_WIN_BORDER
        elif vt_norm in ("хуже обычного", "below average", "worse than usual"):
            v_col, v_bg, v_border = COLOR_LOSS_RED, COLOR_LOSS_BG, COLOR_LOSS_BORDER
        elif vt_norm in ("по-разному", "mixed"):
            v_col, v_bg, v_border = COLOR_OVERWATCH_ORANGE, (255, 247, 237), (254, 215, 170)
        else:
            v_col, v_bg, v_border = COLOR_TEXT_MUTED, COLOR_NEUTRAL_BG, COLOR_NEUTRAL_BORDER

        v_str = block.verdict_text.upper()
        vw = draw.textlength(v_str, font=fonts["bold"]) + 32
        vx = W - pad - 24 - vw
        draw.rounded_rectangle([vx, hy_top - 2, vx + vw, hy_top + 32], radius=8, fill=v_bg, outline=v_border, width=1)
        draw.text((vx + 16, hy_top + 6), v_str, font=fonts["bold"], fill=v_col)

        # Разделитель шапки блока
        draw.line([(pad + 30, curr_y + 68), (W - pad - 24, curr_y + 68)], fill=COLOR_DIVIDER, width=1)

        # Если вердикта нет ("рано судить")
        if not block.has_verdict:
            draw.text((pad + 30, curr_y + 92), block.early_reason or "рано судить", font=fonts["h2"], fill=COLOR_TEXT_MAIN)
            if block.career_ref_text:
                draw.text((pad + 30, curr_y + 128), block.career_ref_text, font=fonts["body"], fill=COLOR_TEXT_MUTED)
            draw.text(
                (pad + 30, curr_y + 158),
                t("card_no_10min_sub", lang),
                font=fonts["small"],
                fill=COLOR_TEXT_LIGHT,
            )
            curr_y += block_h + 16
            continue

        # Три строки-шкалы: Выдача (Урон/Хил), Смерти и Убийства
        scales = [s for s in (block.output_scale, block.deaths_scale, block.eliminations_scale) if s is not None]
        for s_idx, sc in enumerate(scales):
            sy = curr_y + 80 + s_idx * 48
            _draw_metric_scale_row(draw, fonts, sc, pad + 30, sy, W - pad - 24, lang=lang)

        curr_y += block_h + 16

    # ==================== ПОДВАЛ: «ЕЩЁ ИГРАЛ» ====================
    if data.other_heroes:
        draw.rounded_rectangle([pad, curr_y, W - pad, curr_y + 48], radius=12, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        min_s = t("card_min_abbr", lang)
        items_str = ",   ".join(f"{it.hero_name} {it.time_min} {min_s}" for it in data.other_heroes)
        footer_text = f"{t('card_also_played', lang)}   {items_str}"
        draw.text((pad + 24, curr_y + 15), footer_text, font=fonts["body"], fill=COLOR_TEXT_MUTED)

    # Конвертируем в RGB и сохраняем
    final_card = Image.new("RGB", img.size, COLOR_CANVAS_BG)
    final_card.paste(img, (0, 0), img)

    buf = io.BytesIO()
    final_card.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_metric_scale_row(
    draw: ImageDraw.ImageDraw,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    sc: MetricScaleResult,
    x_left: int,
    y_top: int,
    x_right: int,
    lang: str = "ru",
):
    # 1. Название метрики и сегодняшнее значение
    draw.text((x_left, y_top), sc.title, font=fonts["bold"], fill=COLOR_TEXT_MAIN)
    val_str = t("card_per_10m", lang, val=fmt_num(sc.session_val, sc.metric_type))
    draw.text((x_left, y_top + 18), val_str, font=fonts["small"], fill=COLOR_TEXT_MUTED)

    track_x1 = x_left + 150
    track_x2 = x_left + 580
    track_w = track_x2 - track_x1
    track_y = y_top + 12

    if not sc.show_scale:
        draw.text((track_x1, y_top + 8), sc.label_text, font=fonts["body"], fill=COLOR_TEXT_MUTED)
        return

    # 2. Горизонтальный трек шкалы
    draw.rounded_rectangle([track_x1, track_y - 6, track_x2, track_y + 6], radius=6, fill=COLOR_TRACK_BG, outline=COLOR_CARD_BORDER, width=1)

    # 3. Полоса «обычного» [0.30 .. 0.70] вокруг центра 0.50 («твоя норма»)
    b_x1 = int(track_x1 + 0.30 * track_w)
    b_x2 = int(track_x1 + 0.70 * track_w)
    mid_x = int(track_x1 + 0.50 * track_w)

    draw.rounded_rectangle([b_x1, track_y - 8, b_x2, track_y + 8], radius=5, fill=COLOR_BAND_BG, outline=COLOR_SLATE_BORDER, width=1)
    draw.line([(mid_x, track_y - 10), (mid_x, track_y + 10)], fill=COLOR_TEXT_MAIN, width=2)

    # Подпись нормы под шкалой
    norm_lbl = t(
        "card_your_norm",
        lang,
        norm=fmt_num(sc.norm_val, sc.metric_type),
        low=fmt_num(sc.band_low, sc.metric_type),
        high=fmt_num(sc.band_high, sc.metric_type),
    )
    nl_w = draw.textlength(norm_lbl, font=fonts["tiny"])
    draw.text((mid_x - nl_w / 2, track_y + 10), norm_lbl, font=fonts["tiny"], fill=COLOR_TEXT_MUTED)

    # 4. Точка сегодняшнего результата
    if sc.color == "green":
        dot_col = COLOR_WIN_GREEN
    elif sc.color == "red":
        dot_col = COLOR_LOSS_RED
    else:
        dot_col = COLOR_NEUTRAL_DOT

    dot_x = int(track_x1 + sc.pos_norm * track_w)
    draw.ellipse([dot_x - 8, track_y - 8, dot_x + 8, track_y + 8], fill=dot_col, outline=(255, 255, 255), width=2)

    # Стрелки при выходе за пределы
    if sc.clamped == "left":
        draw.text((track_x1 - 20, track_y - 9), "◀", font=fonts["bold"], fill=dot_col)
    elif sc.clamped == "right":
        draw.text((track_x2 + 8, track_y - 9), "▶", font=fonts["bold"], fill=dot_col)

    # 5. Текстовый вывод вердикта справа от шкалы
    lbl_x = track_x2 + 24
    draw.text((lbl_x, y_top + 6), sc.label_text, font=fonts["bold"], fill=dot_col)


def _draw_rank_role_row(
    draw: ImageDraw.ImageDraw,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    rk: RoleRankProgress,
    x1: int,
    y: int,
    x2: int,
    lang: str = "ru",
):
    """Отрисовывает одну строку роли в графике прогресса рангов (с идеальным выравниванием по колонкам)."""
    # 1. Колонка роли (фиксированная ширина бейджа 106px с центровкой текста)
    role_colors = {
        "tank": COLOR_OVERWATCH_ORANGE,
        "damage": COLOR_PRIMARY,
        "support": COLOR_WIN_GREEN,
    }
    r_col = role_colors.get(rk.role, COLOR_TEXT_MUTED)
    pill_w = 106
    draw.rounded_rectangle([x1, y, x1 + pill_w, y + 24], radius=6, fill=COLOR_TRACK_BG, outline=COLOR_CARD_BORDER, width=1)
    r_tag = rk.role_title
    rt_len = draw.textlength(r_tag, font=fonts["small_b"])
    draw.text((x1 + (pill_w - rt_len) / 2.0, y + 4), r_tag, font=fonts["small_b"], fill=r_col)

    # 2. Колонка дивизиона и ранга
    div_col = DIVISION_COLORS.get(rk.division.lower(), COLOR_TEXT_MAIN)
    tier_roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}.get(rk.tier, f"{rk.tier}")
    placement_label = "Placement" if lang == "en" else "Калибровка"
    rank_title = f"{rk.division_title} {tier_roman}" if rk.division.lower() != "unranked" else placement_label
    draw.text((x1 + 122, y + 2), rank_title, font=fonts["bold"], fill=div_col)

    # 3. Сегментированный трек прогресса
    track_x = x1 + 310
    track_w = 400
    track_h = 10
    seg_gap = 7
    num_segs = 5
    seg_w = (track_w - (num_segs - 1) * seg_gap) / float(num_segs)

    active_seg_idx = (5 - rk.tier) if 1 <= rk.tier <= 5 else -1

    for seg_i in range(num_segs):
        sx1 = track_x + seg_i * (seg_w + seg_gap)
        sx2 = sx1 + seg_w
        if seg_i < active_seg_idx:
            draw.rounded_rectangle([sx1, y + 8, sx2, y + 8 + track_h], radius=3, fill=div_col)
        elif seg_i == active_seg_idx:
            draw.rounded_rectangle([sx1, y + 8, sx2, y + 8 + track_h], radius=3, fill=COLOR_TRACK_BG, outline=div_col, width=1)
            prog_ratio = max(0.2, min(1.0, rk.progress_pct / 100.0))
            draw.rounded_rectangle([sx1, y + 8, sx1 + seg_w * prog_ratio, y + 8 + track_h], radius=3, fill=div_col)
        else:
            draw.rounded_rectangle([sx1, y + 8, sx2, y + 8 + track_h], radius=3, fill=COLOR_TRACK_BG, outline=COLOR_CARD_BORDER, width=1)

    draw.text((track_x + 2, y + 21), "V", font=fonts["tiny"], fill=COLOR_TEXT_LIGHT)
    draw.text((track_x + track_w - 8, y + 21), "I", font=fonts["tiny"], fill=COLOR_TEXT_LIGHT)

    # 4. Трендовая подпись справа
    default_delta = f"{rk.progress_pct}% to rank" if lang == "en" else f"{rk.progress_pct}% до ранга"
    delta_s = rk.delta_text or default_delta
    d_col = COLOR_WIN_GREEN if "▲" in delta_s else (COLOR_LOSS_RED if "▼" in delta_s else COLOR_TEXT_MUTED)
    dw = draw.textlength(delta_s, font=fonts["small_b"]) + 16
    dx = x2 - dw
    draw.rounded_rectangle([dx, y, dx + dw, y + 24], radius=6, fill=COLOR_TRACK_BG, outline=COLOR_CARD_BORDER, width=1)
    draw.text((dx + 8, y + 4), delta_s, font=fonts["small_b"], fill=d_col)
