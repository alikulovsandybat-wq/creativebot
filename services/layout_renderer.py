import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from models.creative import CreativePlan

# ═══ РАЗМЕР CANVAS ═══
CANVAS_W = 1080
CANVAS_H = 1920

# ═══ ПОИСК ШРИФТОВ ═══
def _find_fonts_dir():
    """Ищет папку со шрифтами во всех возможных местах."""
    base = os.path.dirname(__file__)
    candidates = [
        # Скачанные при старте
        "/tmp/creative_fonts",
        # Из репозитория
        os.path.join(base, "fonts_all", "fonts"),
        os.path.join(base, "fonts_all"),
        os.path.join(base, "fonts"),
        os.path.join(base, "..", "fonts_all", "fonts"),
        os.path.join(base, "..", "fonts"),
        # Env переменная
        os.getenv("CREATIVE_FONTS_DIR", ""),
    ]
    for path in candidates:
        if path and os.path.isdir(path):
            # Проверяем что внутри есть хоть что-то полезное
            for sub in ["universal", "bold", "delicate", "cozy", "premium"]:
                if os.path.isdir(os.path.join(path, sub)):
                    return os.path.abspath(path)
            # Или прямо в папке лежат ttf файлы
            if any(f.endswith(".ttf") for f in os.listdir(path)):
                return os.path.abspath(path)
    return ""


FONTS_DIR = _find_fonts_dir()


def _get_font(size: int, weight: str = "regular", brand_style: str = "universal") -> ImageFont.FreeTypeFont:
    """
    Ищет шрифт в порядке приоритета:
    1. fonts_dir/brand_style/weight.ttf
    2. fonts_dir/universal/weight.ttf
    3. fonts_dir/weight.ttf (плоская структура — для /tmp/creative_fonts)
    4. Системные шрифты Noto/DejaVu
    5. Default
    """
    weight_map = {
        "bold": "bold.ttf",
        "semibold": "semibold.ttf",
        "regular": "regular.ttf",
        "light": "light.ttf",
    }
    filename = weight_map.get(weight, "regular.ttf")

    paths_to_try = []

    if FONTS_DIR:
        # Сначала пробуем brand_style папку
        paths_to_try.append(os.path.join(FONTS_DIR, brand_style, filename))
        # Потом universal
        paths_to_try.append(os.path.join(FONTS_DIR, "universal", filename))
        # Потом прямо в FONTS_DIR (для /tmp/creative_fonts где файлы плоско)
        paths_to_try.append(os.path.join(FONTS_DIR, filename))
        # NotoSans имена (если скачали как NotoSans-Bold.ttf)
        if weight in ("bold", "semibold"):
            paths_to_try.append(os.path.join(FONTS_DIR, "NotoSans-Bold.ttf"))
        else:
            paths_to_try.append(os.path.join(FONTS_DIR, "NotoSans-Regular.ttf"))

    # Системные шрифты Railway/Debian
    system_fonts = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if weight in ("bold", "semibold")
        else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight in ("bold", "semibold")
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if weight in ("bold", "semibold")
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    paths_to_try.extend(system_fonts)

    for path in paths_to_try:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Последний resort
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# ═══ ТЕМЫ ═══
THEMES = {
    "minimal": {
        "text_primary": (15, 15, 15),
        "text_secondary": (50, 50, 50),
        "badge_bg": (15, 15, 15),
        "badge_text": (255, 255, 255),
        "cta_bg": (255, 255, 255),
        "cta_text": (15, 15, 15),
        "cta_border": (15, 15, 15),
        "price_color": (15, 15, 15),
        "overlay": True,
        "overlay_light": True,
        "bg_fallback": (252, 251, 248),
        "text_shadow": False,
    },
    "premium": {
        "text_primary": (255, 255, 255),
        "text_secondary": (235, 225, 200),
        "badge_bg": (212, 175, 55),
        "badge_text": (0, 0, 0),
        "cta_bg": (212, 175, 55),
        "cta_text": (0, 0, 0),
        "cta_border": (212, 175, 55),
        "price_color": (212, 175, 55),
        "overlay": True,
        "overlay_light": False,
        "bg_fallback": (12, 12, 18),
        "text_shadow": True,
    },
    "conversion": {
        "text_primary": (255, 255, 255),
        "text_secondary": (240, 240, 240),
        "badge_bg": (220, 38, 38),
        "badge_text": (255, 255, 255),
        "cta_bg": (255, 255, 255),
        "cta_text": (15, 20, 40),
        "cta_border": (255, 255, 255),
        "price_color": (255, 255, 255),
        "overlay": True,
        "overlay_light": False,
        "bg_fallback": (15, 25, 50),
        "text_shadow": True,
    },
}


def _add_overlay(img: Image.Image, theme: dict, layout: str) -> Image.Image:
    """Добавляет градиентный оверлей для читаемости текста."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    W, H = img.size

    if layout == "A":
        # Тёмный/светлый градиент сверху (зона заголовка)
        top_zone = int(H * 0.35)
        for y in range(top_zone):
            t = 1.0 - (y / top_zone)
            alpha = int(160 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(0, y), (W, y)], fill=color)
        # Тёмный градиент снизу (зона CTA)
        bottom_start = int(H * 0.78)
        for y in range(bottom_start, H):
            t = (y - bottom_start) / (H - bottom_start)
            alpha = int(180 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(0, y), (W, y)], fill=color)

    elif layout == "B":
        # Тёмный/светлый градиент сверху большой (зона большого заголовка)
        top_zone = int(H * 0.45)
        for y in range(top_zone):
            t = 1.0 - (y / top_zone)
            alpha = int(170 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(0, y), (W, y)], fill=color)
        # Снизу для CTA
        bottom_start = int(H * 0.82)
        for y in range(bottom_start, H):
            t = (y - bottom_start) / (H - bottom_start)
            alpha = int(170 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(0, y), (W, y)], fill=color)

    elif layout == "C":
        # Левая полоса для текста
        left_zone = int(W * 0.52)
        for x in range(left_zone):
            t = 1.0 - (x / left_zone)
            alpha = int(150 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(x, 0), (x, H)], fill=color)
        # Снизу для CTA
        bottom_start = int(H * 0.82)
        for y in range(bottom_start, H):
            t = (y - bottom_start) / (H - bottom_start)
            alpha = int(160 * t)
            color = (255, 255, 255, alpha) if theme.get("overlay_light") else (0, 0, 0, alpha)
            draw.line([(0, y), (W, y)], fill=color)

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _draw_shadow_text(draw, pos, text, font, fill, offset=2, opacity=160):
    """Рисует текст с тенью."""
    x, y = pos
    shadow_color = (0, 0, 0, opacity)
    for dx, dy in [(offset, offset), (offset + 1, offset + 1)]:
        draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)


def _text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _draw_layout_a(draw, plan, theme, brand_style, W, H):
    """
    Layout A: заголовок сверху, буллеты, цена, CTA снизу по центру.
    Продукт в центре (обрабатывается в image_transformer).
    """
    use_shadow = theme.get("text_shadow", False)
    PAD = 60
    max_w = W - PAD * 2
    y = PAD

    # BADGE
    if plan.badge:
        font = _get_font(26, "semibold", brand_style)
        bbox = draw.textbbox((0, 0), plan.badge, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px, py = 16, 8
        draw.rounded_rectangle([PAD, y, PAD + tw + px * 2, y + th + py * 2],
                                radius=6, fill=theme["badge_bg"])
        draw.text((PAD + px, y + py), plan.badge, font=font, fill=theme["badge_text"])
        y += th + py * 2 + 24

    # HEADLINE
    if plan.headline:
        font = _get_font(76, "bold", brand_style)
        chars = max(8, int(max_w / (76 * 0.52)))
        for line in textwrap.wrap(plan.headline, width=chars)[:3]:
            if use_shadow:
                _draw_shadow_text(draw, (PAD, y), line, font, theme["text_primary"])
            else:
                draw.text((PAD, y), line, font=font, fill=theme["text_primary"])
            y += _text_height(draw, line, font) + 8
        y += 14

    # SUBHEADLINE
    if plan.subheadline:
        font = _get_font(32, "light", brand_style)
        if use_shadow:
            _draw_shadow_text(draw, (PAD, y), plan.subheadline, font, theme["text_secondary"])
        else:
            draw.text((PAD, y), plan.subheadline, font=font, fill=theme["text_secondary"])
        y += _text_height(draw, plan.subheadline, font) + 20

    # ЦЕНА
    if plan.price:
        font = _get_font(58, "bold", brand_style)
        if use_shadow:
            _draw_shadow_text(draw, (PAD, y), plan.price, font, theme["price_color"], offset=3, opacity=200)
        else:
            draw.text((PAD, y), plan.price, font=font, fill=theme["price_color"])
        y += _text_height(draw, plan.price, font) + 22

    # БУЛЛЕТЫ — после продукта (нижняя часть)
    bullet_y = int(H * 0.72)
    if plan.bullets:
        font = _get_font(30, "regular", brand_style)
        for bullet in plan.bullets[:3]:
            text = bullet if bullet.startswith("—") else f"— {bullet}"
            if use_shadow:
                _draw_shadow_text(draw, (PAD, bullet_y), text, font, theme["text_secondary"])
            else:
                draw.text((PAD, bullet_y), text, font=font, fill=theme["text_secondary"])
            bullet_y += _text_height(draw, text, font) + 14

    # CTA — внизу по центру
    _draw_cta(draw, plan, theme, brand_style, W, H)


def _draw_layout_b(draw, plan, theme, brand_style, W, H):
    """
    Layout B: большой заголовок сверху (40% экрана), продукт снизу-центр, CTA внизу.
    """
    use_shadow = theme.get("text_shadow", False)
    PAD = 60
    max_w = W - PAD * 2
    y = PAD

    # BADGE
    if plan.badge:
        font = _get_font(26, "semibold", brand_style)
        bbox = draw.textbbox((0, 0), plan.badge, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px, py = 16, 8
        # Центрируем badge
        badge_x = (W - tw - px * 2) // 2
        draw.rounded_rectangle([badge_x, y, badge_x + tw + px * 2, y + th + py * 2],
                                radius=6, fill=theme["badge_bg"])
        draw.text((badge_x + px, y + py), plan.badge, font=font, fill=theme["badge_text"])
        y += th + py * 2 + 24

    # HEADLINE — крупный, по центру
    if plan.headline:
        font = _get_font(96, "bold", brand_style)
        chars = max(6, int(max_w / (96 * 0.52)))
        lines = textwrap.wrap(plan.headline, width=chars)[:3]
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw = bbox[2] - bbox[0]
            lx = (W - lw) // 2
            if use_shadow:
                _draw_shadow_text(draw, (lx, y), line, font, theme["text_primary"])
            else:
                draw.text((lx, y), line, font=font, fill=theme["text_primary"])
            y += _text_height(draw, line, font) + 10
        y += 16

    # SUBHEADLINE — по центру
    if plan.subheadline:
        font = _get_font(34, "light", brand_style)
        bbox = draw.textbbox((0, 0), plan.subheadline, font=font)
        lw = bbox[2] - bbox[0]
        lx = (W - lw) // 2
        if use_shadow:
            _draw_shadow_text(draw, (lx, y), plan.subheadline, font, theme["text_secondary"])
        else:
            draw.text((lx, y), plan.subheadline, font=font, fill=theme["text_secondary"])
        y += _text_height(draw, plan.subheadline, font) + 20

    # ЦЕНА — по центру
    if plan.price:
        font = _get_font(62, "bold", brand_style)
        bbox = draw.textbbox((0, 0), plan.price, font=font)
        lw = bbox[2] - bbox[0]
        lx = (W - lw) // 2
        if use_shadow:
            _draw_shadow_text(draw, (lx, y), plan.price, font, theme["price_color"], offset=3, opacity=200)
        else:
            draw.text((lx, y), plan.price, font=font, fill=theme["price_color"])

    # CTA внизу
    _draw_cta(draw, plan, theme, brand_style, W, H)


def _draw_layout_c(draw, plan, theme, brand_style, W, H):
    """
    Layout C: текст слева (40% ширины), продукт справа, CTA внизу.
    """
    use_shadow = theme.get("text_shadow", False)
    PAD = 50
    max_w = int(W * 0.46) - PAD
    y = int(H * 0.18)  # Начинаем не с самого верха

    # BADGE
    if plan.badge:
        font = _get_font(24, "semibold", brand_style)
        bbox = draw.textbbox((0, 0), plan.badge, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px, py = 14, 7
        draw.rounded_rectangle([PAD, y, PAD + tw + px * 2, y + th + py * 2],
                                radius=6, fill=theme["badge_bg"])
        draw.text((PAD + px, y + py), plan.badge, font=font, fill=theme["badge_text"])
        y += th + py * 2 + 20

    # HEADLINE — слева
    if plan.headline:
        font = _get_font(68, "bold", brand_style)
        chars = max(5, int(max_w / (68 * 0.52)))
        for line in textwrap.wrap(plan.headline, width=chars)[:4]:
            if use_shadow:
                _draw_shadow_text(draw, (PAD, y), line, font, theme["text_primary"])
            else:
                draw.text((PAD, y), line, font=font, fill=theme["text_primary"])
            y += _text_height(draw, line, font) + 8
        y += 14

    # SUBHEADLINE
    if plan.subheadline:
        font = _get_font(28, "light", brand_style)
        chars = max(8, int(max_w / (28 * 0.52)))
        for line in textwrap.wrap(plan.subheadline, width=chars)[:2]:
            if use_shadow:
                _draw_shadow_text(draw, (PAD, y), line, font, theme["text_secondary"])
            else:
                draw.text((PAD, y), line, font=font, fill=theme["text_secondary"])
            y += _text_height(draw, line, font) + 8
        y += 16

    # ЦЕНА
    if plan.price:
        font = _get_font(52, "bold", brand_style)
        if use_shadow:
            _draw_shadow_text(draw, (PAD, y), plan.price, font, theme["price_color"], offset=3, opacity=200)
        else:
            draw.text((PAD, y), plan.price, font=font, fill=theme["price_color"])
        y += _text_height(draw, plan.price, font) + 18

    # БУЛЛЕТЫ слева
    if plan.bullets:
        font = _get_font(26, "regular", brand_style)
        chars = max(8, int(max_w / (26 * 0.52)))
        for bullet in plan.bullets[:3]:
            text = bullet if bullet.startswith("—") else f"— {bullet}"
            for line in textwrap.wrap(text, width=chars)[:2]:
                if use_shadow:
                    _draw_shadow_text(draw, (PAD, y), line, font, theme["text_secondary"])
                else:
                    draw.text((PAD, y), line, font=font, fill=theme["text_secondary"])
                y += _text_height(draw, line, font) + 10

    # CTA внизу
    _draw_cta(draw, plan, theme, brand_style, W, H)


def _draw_cta(draw, plan, theme, brand_style, W, H):
    """CTA кнопка внизу по центру — общая для всех layout."""
    if not plan.cta:
        return
    font = _get_font(32, "semibold", brand_style)
    bbox = draw.textbbox((0, 0), plan.cta, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 50, 20
    btn_w = min(tw + px * 2, W - 120)
    cta_x = (W - btn_w) // 2
    cta_y = H - th - py * 2 - 60

    draw.rounded_rectangle(
        [cta_x, cta_y, cta_x + btn_w, cta_y + th + py * 2],
        radius=14, fill=theme["cta_bg"]
    )
    if theme.get("cta_border"):
        draw.rounded_rectangle(
            [cta_x, cta_y, cta_x + btn_w, cta_y + th + py * 2],
            radius=14, outline=theme["cta_border"], width=2
        )
    draw.text(
        (cta_x + (btn_w - tw) // 2, cta_y + py),
        plan.cta, font=font, fill=theme["cta_text"]
    )


def render_banner(plan: CreativePlan,
                  source_image_path: str = None,
                  output_path: str = "output.png",
                  layout: str = "A") -> str:
    """
    Рендерит финальный баннер 1080x1920.
    layout: "A", "B", или "C"
    source_image_path: уже скомпонованное изображение (фон + продукт)
    """
    W, H = CANVAS_W, CANVAS_H
    theme = THEMES.get(plan.style, THEMES["minimal"])
    brand_style = getattr(plan, "brand_style", "universal")

    # ФОН (уже скомпонованный из image_transformer)
    if source_image_path and os.path.exists(source_image_path):
        bg = Image.open(source_image_path).convert("RGB")
        bg = bg.resize((W, H), Image.LANCZOS)
    else:
        bg = Image.new("RGB", (W, H), theme["bg_fallback"])

    # Оверлей для читаемости текста
    bg = _add_overlay(bg, theme, layout)
    bg = bg.convert("RGB")
    draw = ImageDraw.Draw(bg)

    # Рисуем текст согласно layout
    if layout == "A":
        _draw_layout_a(draw, plan, theme, brand_style, W, H)
    elif layout == "B":
        _draw_layout_b(draw, plan, theme, brand_style, W, H)
    elif layout == "C":
        _draw_layout_c(draw, plan, theme, brand_style, W, H)
    else:
        _draw_layout_a(draw, plan, theme, brand_style, W, H)

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )
    bg.save(output_path, "PNG", quality=95)
    return output_path
