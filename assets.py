import os
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
HEROES_PFP_DIR = os.path.join(BASE_DIR, "heroespfp")
PICTURES_DIR = os.path.join(BASE_DIR, "pictures")
AVATARS_CACHE_DIR = os.path.join(BASE_DIR, "cache", "avatars")

os.makedirs(AVATARS_CACHE_DIR, exist_ok=True)

# Ключ героя в API -> базовое имя файла в heroespfp/
HERO_PFP_SPECIAL_MAP = {
    "dva": "d_va.png",
    "d-mon": "d_mon.png",
    "jetpack-cat": "jetpack_cat.png",
    "junker-queen": "junker_queen.png",
    "soldier-76": "soldier_76.png",
    "wrecking-ball": "wrecking_ball.png",
    "doomfist": "doomfist.png",
}

# Кэш готовых аватарок в памяти для мгновенного рендера
_HERO_AVATAR_CACHE: Dict[Tuple[str, int, int], Image.Image] = {}
_FONTS_CACHE: Optional[Dict[str, ImageFont.FreeTypeFont]] = None


def get_hero_pfp_path(hero_key: str) -> Optional[str]:
    """Возвращает путь к иконке героя в папке heroespfp."""
    if hero_key in HERO_PFP_SPECIAL_MAP:
        cand = os.path.join(HEROES_PFP_DIR, HERO_PFP_SPECIAL_MAP[hero_key])
        if os.path.isfile(cand):
            return cand

    # Пробуем варианты: прямая замена дефисов на подчеркивания
    variants = [
        f"{hero_key}.png",
        f"{hero_key.replace('-', '_')}.png",
        f"{hero_key.replace('-', '')}.png",
    ]
    for v in variants:
        p = os.path.join(HEROES_PFP_DIR, v)
        if os.path.isfile(p):
            return p
    return None


def get_hero_avatar(
    hero_key: str,
    size: int = 56,
    radius: int = 12,
    border_color: Tuple[int, int, int] = (188, 200, 222),
    border_width: int = 1,
) -> Image.Image:
    """
    Возвращает аватарку героя в виде стильного скругленного квадрата
    с антиалиасингом и тонким бордером.
    """
    cache_key = (hero_key, size, radius)
    if cache_key in _HERO_AVATAR_CACHE:
        return _HERO_AVATAR_CACHE[cache_key].copy()

    file_path = get_hero_pfp_path(hero_key)
    scale = 4  # Суперсэмплинг для ультра-гладких скруглений
    hi_size = size * scale
    hi_radius = radius * scale

    if file_path and os.path.isfile(file_path):
        try:
            with Image.open(file_path) as raw:
                raw_rgba = raw.convert("RGBA")
                raw_resized = raw_rgba.resize((hi_size, hi_size), Image.Resampling.LANCZOS)
        except Exception:
            raw_resized = Image.new("RGBA", (hi_size, hi_size), (34, 39, 62, 255))
    else:
        raw_resized = Image.new("RGBA", (hi_size, hi_size), (34, 39, 62, 255))

    # Маска скругленного квадрата (squircle)
    mask = Image.new("L", (hi_size, hi_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([0, 0, hi_size - 1, hi_size - 1], radius=hi_radius, fill=255)

    # Применяем маску
    output = Image.new("RGBA", (hi_size, hi_size), (0, 0, 0, 0))
    output.paste(raw_resized, (0, 0), mask)

    # Рисуем тонкий бордер
    draw_out = ImageDraw.Draw(output)
    draw_out.rounded_rectangle(
        [0, 0, hi_size - 1, hi_size - 1],
        radius=hi_radius,
        outline=(*border_color, 255),
        width=border_width * scale,
    )

    final_img = output.resize((size, size), Image.Resampling.LANCZOS)
    _HERO_AVATAR_CACHE[cache_key] = final_img
    return final_img.copy()


def get_player_avatar(
    avatar_path_or_url: Optional[str],
    player_name: str,
    size: int = 76,
    border_color: Tuple[int, int, int] = (0, 157, 255),
    border_width: int = 2,
) -> Image.Image:
    """
    Возвращает аватар игрока, оформленный в круг со стильной рамкой.
    Если файла/URL нет, генерирует контрастный монограммный аватар.
    """
    scale = 4
    hi_size = size * scale

    loaded_img = None
    if avatar_path_or_url and os.path.isfile(avatar_path_or_url):
        try:
            with Image.open(avatar_path_or_url) as raw:
                loaded_img = raw.convert("RGBA").resize((hi_size, hi_size), Image.Resampling.LANCZOS)
        except Exception:
            loaded_img = None

    if loaded_img is None:
        # Стильная монограмма с инициалом игрока
        loaded_img = Image.new("RGBA", (hi_size, hi_size), (34, 39, 62, 255))
        d = ImageDraw.Draw(loaded_img)
        letter = (player_name.strip()[:1] or "O").upper()
        font_path = os.path.join(FONTS_DIR, "Montserrat-Bold.ttf")
        try:
            font = ImageFont.truetype(font_path, int(hi_size * 0.48))
        except Exception:
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), letter, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (hi_size - tw) / 2 - bbox[0]
        ty = (hi_size - th) / 2 - bbox[1]
        d.text((tx, ty), letter, font=font, fill=(255, 255, 255, 255))

    mask = Image.new("L", (hi_size, hi_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse([0, 0, hi_size - 1, hi_size - 1], fill=255)

    output = Image.new("RGBA", (hi_size, hi_size), (0, 0, 0, 0))
    output.paste(loaded_img, (0, 0), mask)

    # Рисуем рамку
    draw_out = ImageDraw.Draw(output)
    draw_out.ellipse([0, 0, hi_size - 1, hi_size - 1], outline=(*border_color, 255), width=border_width * scale)

    return output.resize((size, size), Image.Resampling.LANCZOS)


def get_banner_image(
    hero_keys: Optional[List[str]] = None,
    width: int = 1040,
    height: int = 160,
    fade_start_y: int = 40,
) -> Image.Image:
    """
    Создает шапку с фоновым артом из папки pictures,
    плавно переходящую в белый цвет (#ffffff) снизу.
    """
    # Подбираем файл картинки
    selected_file = None
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")

    # 1. Если переданы герои, ищем скриншот героя
    if hero_keys:
        for hk in hero_keys:
            norm_hk = hk.replace("-", "_")
            if os.path.isdir(PICTURES_DIR):
                for f in os.listdir(PICTURES_DIR):
                    if f.lower().endswith(valid_exts):
                        f_low = f.lower()
                        if hk in f_low or norm_hk in f_low:
                            selected_file = os.path.join(PICTURES_DIR, f)
                            break
            if selected_file:
                break

    # 2. Если героя нет, ищем живописную карту
    if not selected_file and os.path.isdir(PICTURES_DIR):
        map_keywords = ["colosseo", "busan", "midtown", "havana", "rialto", "all_heroes"]
        for kw in map_keywords:
            for f in os.listdir(PICTURES_DIR):
                if f.lower().endswith(valid_exts) and kw in f.lower():
                    selected_file = os.path.join(PICTURES_DIR, f)
                    break
            if selected_file:
                break

    # 3. Фолбэк на любой подходящий файл
    if not selected_file and os.path.isdir(PICTURES_DIR):
        for f in os.listdir(PICTURES_DIR):
            if f.lower().endswith(valid_exts):
                selected_file = os.path.join(PICTURES_DIR, f)
                break

    banner = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    if selected_file and os.path.isfile(selected_file):
        try:
            with Image.open(selected_file) as raw:
                raw_rgb = raw.convert("RGBA")
                # Масштабируем с сохранением пропорций, заполняя прямоугольник (Cover)
                rw, rh = raw_rgb.size
                scale = max(width / rw, height / rh)
                new_w = int(round(rw * scale))
                new_h = int(round(rh * scale))
                resized = raw_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Центрируем кроп
                crop_x = (new_w - width) // 2
                crop_y = max(0, (new_h - height) // 4)
                cropped = resized.crop((crop_x, crop_y, crop_x + width, crop_y + height))

                # Градиент затухания в белый цвет (построчное заполнение вместо попиксельного)
                alpha_mask = Image.new("L", (width, height), 255)
                for y in range(height):
                    if y < fade_start_y:
                        alpha = 220
                    else:
                        progress = (y - fade_start_y) / float(height - fade_start_y)
                        alpha = max(0, min(255, int(220 * (1.0 - (progress ** 1.4)))))
                    alpha_mask.paste(alpha, (0, y, width, y + 1))

                # Совмещаем с белым фоном
                banner.paste(cropped, (0, 0), alpha_mask)
        except Exception:
            pass

    return banner


def load_app_fonts() -> Dict[str, ImageFont.FreeTypeFont]:
    """
    Загружает шрифты из папки fonts/ с гарантированной поддержкой кириллицы.
    Возвращает словарь начертаний: huge, h1, h2, bold, medium, body, small_b, small.
    """
    global _FONTS_CACHE
    if _FONTS_CACHE is not None:
        return _FONTS_CACHE

    bold_p = os.path.join(FONTS_DIR, "Montserrat-Bold.ttf")
    sbold_p = os.path.join(FONTS_DIR, "Montserrat-SemiBold.ttf")
    medium_p = os.path.join(FONTS_DIR, "FuturaPTMedium.ttf")
    if not os.path.isfile(medium_p):
        medium_p = os.path.join(FONTS_DIR, "Montserrat-Medium.ttf")
    regular_p = os.path.join(FONTS_DIR, "Montserrat-Regular.ttf")

    # Фолбэки
    if not os.path.isfile(bold_p):
        bold_p = medium_p if os.path.isfile(medium_p) else regular_p
    if not os.path.isfile(regular_p):
        regular_p = bold_p

    try:
        fonts = {
            "huge": ImageFont.truetype(bold_p, 48),
            "h1": ImageFont.truetype(bold_p, 26),
            "h2": ImageFont.truetype(sbold_p, 20),
            "bold": ImageFont.truetype(sbold_p, 16),
            "medium": ImageFont.truetype(medium_p, 15),
            "body": ImageFont.truetype(regular_p, 14),
            "small_b": ImageFont.truetype(sbold_p, 13),
            "small": ImageFont.truetype(regular_p, 12),
            "tiny": ImageFont.truetype(regular_p, 11),
        }
    except Exception:
        d = ImageFont.load_default()
        fonts = {k: d for k in ["huge", "h1", "h2", "bold", "medium", "body", "small_b", "small", "tiny"]}

    _FONTS_CACHE = fonts
    return fonts

