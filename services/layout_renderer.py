import os
import textwrap
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from models.creative import CreativePlan
from services.typography_presets import PRESETS, TypographyPreset

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def _get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    weight_map = {
        "bold": "bold.ttf",
        "semibold": "semibold.ttf",
        "regular": "regular.ttf",
        "light": "light.ttf",
    }
    path = os.path.join(FONTS_DIR, weight_map.get(weight, "regular.ttf"))
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        fallbacks = {
            "bold": "/usr/share/fonts/truetype/open-sans/OpenSans-ExtraBold.ttf",
            "semibold": "/usr/share/fonts/truetype/open-sans/OpenSans-Semibold.ttf",
            "regular": "/usr/share/fonts/truetype/open-sans/OpenSans-Regular.ttf",
            "light": "/usr/share/fonts/truetype/open-sans/OpenSans-Light.ttf",
        }
        try:
            return ImageFont.truetype(fallbacks.get(weight, fallbacks["regular"]), size)
        except Exception:
            return ImageFont.load_default()


# ── СТИЛИ ──────────────────────────────────────────────────────────────────

THEMES = {
    "minimal": {
        "bg": (252, 251, 248),          # тёплый белый
        "text_primary": (20, 20, 20),
        "text_secondary": (80, 80, 80),
        "text_muted": (140, 140, 140),
        "accent": (20, 20, 20),         # цена — тёмная
        "badge_bg": (20, 20, 20),
        "badge_text": (255, 255, 255),
        "cta_bg": (20, 20, 20),
        "cta_text": (255, 255, 255),
        "divider": (220, 218, 212),
        "price_color": (20, 20, 20),
    },
    "premium": {
        "bg": (12, 12, 18),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 195, 180),
        "text_muted": (140, 135, 120),
        "accent": (212, 175, 55),
        "badge_bg": (212, 175, 55),
        "badge_text": (0, 0, 0),
        "cta_bg": (212, 175, 55),
        "cta_text": (0, 0, 0),
        "divider": (50, 45, 35),
        "price_color": (212, 175, 55),
    },
    "conversion": {
        "bg": (255, 255, 255),
        "text_primary": (15, 20, 40),
        "text_secondary": (60, 70, 100),
        "text_muted": (120, 130, 160),
        "accent": (37, 99, 235),
        "badge_bg": (220, 38, 38),
        "badge_text": (255, 255, 255),
        "cta_bg": (37, 99, 235),
        "cta_text": (255, 255, 255),
        "divider": (220, 225, 240),
        "price_color": (37, 99, 235),
    },
}

# Размеры зон (доля от высоты холста)
TEXT_ZONE_RATIO = 0.46   # верхние 46% — текст
PHOTO_ZONE_RATIO = 0.54  # нижние 54% — фото


def _draw_badge(draw, text, x, y, theme, font_size=22):
    if not text:
        return y
    font = _get_font(font_size, "semibold")
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 14, 7
    rect = [x, y, x + tw + pad_x * 2, y + th + pad_y * 2]
    draw.rounded_rectangle(rect, radius=5, fill=theme["badge_bg"])
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=theme["badge_text"])
    return rect[3] + 20


def _draw_headline(draw, text, x, y, max_w, theme, size=68):
    if not text:
        return y
    font = _get_font(size, "bold")
    chars = max(8, int(max_w / (size * 0.52)))
    lines = textwrap.wrap(text, width=chars)
    for line in lines[:3]:
        draw.text((x, y), line, font=font, fill=theme["text_primary"])
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + 6
    return y + 10


def _draw_subheadline(draw, text, x, y, theme, size=28):
    if not text:
        return y
    font = _get_font(size, "light")
    draw.text((x, y), text, font=font, fill=theme["text_secondary"])
    bbox = draw.textbbox((x, y), text, font=font)
    return y + (bbox[3] - bbox[1]) + 16


def _draw_price(draw, text, x, y, theme, size=48):
    if not text:
        return y
    font = _get_font(size, "bold")
    # Рамка вокруг цены
    bbox = draw.textbbox((x, y), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 16, 8
    rect = [x - pad_x, y - pad_y,
            x + tw + pad_x, y + th + pad_y]
    draw.rounded_rectangle(rect, radius=6,
                           outline=theme["divider"], width=2,
                           fill=None)
    draw.text((x, y), text, font=font, fill=theme["price_color"])
    return y + th + pad_y + 20


def _draw_bullets(draw, bullets, x, y, theme, size=26):
    if not bullets:
        return y
    font = _get_font(size, "regular")
    for bullet in bullets[:4]:
        text = bullet if bullet.startswith("—") else f"— {bullet}"
        draw.text((x, y), text, font=font, fill=theme["text_secondary"])
        bbox = draw.textbbox((x, y), text, font=font)
        y += (bbox[3] - bbox[1]) + 10
    return y + 8


def _draw_cta(draw, text, x, y, max_w, theme, size=28):
    if not text:
        return
    font = _get_font(size, "semibold")
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 32, 14
    btn_w = min(tw + pad_x * 2, max_w)
    rect = [x, y, x + btn_w, y + th + pad_y * 2]
    draw.rounded_rectangle(rect, radius=8, fill=theme["cta_bg"])
    text_x = x + (btn_w - tw) // 2
    draw.text((text_x, y + pad_y), text, font=font, fill=theme["cta_text"])


def _place_photo_in_zone(bg: Image.Image, source_path: str,
                         zone_y: int, zone_h: int, W: int) -> Image.Image:
    """Вставляет фото в нижнюю зону, сохраняя пропорции."""
    if not source_path or not os.path.exists(source_path):
        return bg

    src = Image.open(source_path).convert("RGBA")

    # Масштаб под зону
    ratio = src.width / src.height
    max_h = zone_h - 20
    max_w = W
    if src.width / max_w > src.height / max_h:
        new_w = max_w
        new_h = int(max_w / ratio)
    else:
        new_h = max_h
        new_w = int(max_h * ratio)

    src = src.resize((new_w, new_h), Image.LANCZOS)

    # Центрируем по горизонтали, прижимаем к низу
    ox = (W - new_w) // 2
    oy = zone_y + (zone_h - new_h)

    if src.mode == "RGBA":
        bg.paste(src, (ox, oy), src)
    else:
        bg.paste(src, (ox, oy))

    return bg


def render_banner(plan: CreativePlan,
                  source_image_path: str = None,
                  output_path: str = "output.png") -> str:
    W, H = 1080, 1080
    theme = THEMES.get(plan.style, THEMES["minimal"])

    text_zone_h = int(H * TEXT_ZONE_RATIO)
    photo_zone_h = H - text_zone_h

    # ── ФОН ──────────────────────────────────────────────────────────────
    bg = Image.new("RGB", (W, H), theme["bg"])

    # Лёгкий разделитель между зонами
    draw_bg = ImageDraw.Draw(bg)
    draw_bg.line([(0, text_zone_h), (W, text_zone_h)],
                 fill=theme["divider"], width=1)

    # ── ФОТО В НИЖНЕЙ ЗОНЕ ───────────────────────────────────────────────
    if source_image_path and os.path.exists(source_image_path):
        bg = _place_photo_in_zone(bg, source_image_path,
                                  text_zone_h, photo_zone_h, W)

    # ── ТЕКСТОВЫЙ БЛОК СВЕРХУ ────────────────────────────────────────────
    draw = ImageDraw.Draw(bg)

    PAD = 52   # отступ от края
    x = PAD
    y = PAD
    max_w = W - PAD * 2

    # Бейдж (город или статус)
    y = _draw_badge(draw, plan.badge, x, y, theme)

    # Заголовок
    y = _draw_headline(draw, plan.headline, x, y, max_w, theme, size=64)

    # Подзаголовок
    y = _draw_subheadline(draw, plan.subheadline, x, y, theme, size=26)

    # Цена
    if plan.price:
        y = _draw_price(draw, plan.price, x, y, theme, size=44)

    # Буллеты
    y = _draw_bullets(draw, plan.bullets, x, y, theme, size=24)

    # CTA — прижимаем к границе фото зоны снизу текстового блока
    cta_y = text_zone_h - 70
    if y < cta_y:
        _draw_cta(draw, plan.cta, x, cta_y, max_w, theme, size=26)

    # ── СОХРАНЯЕМ ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    bg.save(output_path, "PNG", quality=95)
    return output_path
