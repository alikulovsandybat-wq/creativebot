import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
from models.creative import CreativePlan

def _find_fonts_dir():
    """Ищет папку со шрифтами — поддерживает разные структуры репозитория."""
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "..", "fonts"),           # /fonts/
        os.path.join(base, "..", "fonts_all", "fonts"),  # /fonts_all/fonts/
        os.path.join(base, "..", "fonts_all"),        # /fonts_all/
    ]
    for path in candidates:
        if os.path.isdir(path):
            # Проверяем что там есть подпапки со шрифтами
            if any(os.path.isdir(os.path.join(path, sub))
                   for sub in ["universal", "bold", "delicate"]):
                return os.path.abspath(path)
    return os.path.join(base, "..", "fonts")  # fallback

FONTS_DIR = _find_fonts_dir()

BRAND_FONT_DIRS = {
    "delicate": "delicate",
    "bold": "bold",
    "cozy": "cozy",
    "premium": "premium",
    "universal": "universal",
}

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
        "overlay": False,
        "bg_fallback": (252, 251, 248),
    },
    "premium": {
        "text_primary": (255, 255, 255),
        "text_secondary": (220, 210, 180),
        "badge_bg": (212, 175, 55),
        "badge_text": (0, 0, 0),
        "cta_bg": (212, 175, 55),
        "cta_text": (0, 0, 0),
        "cta_border": (212, 175, 55),
        "price_color": (212, 175, 55),
        "overlay": True,
        "bg_fallback": (12, 12, 18),
    },
    "conversion": {
        "text_primary": (255, 255, 255),
        "text_secondary": (220, 230, 255),
        "badge_bg": (220, 38, 38),
        "badge_text": (255, 255, 255),
        "cta_bg": (255, 255, 255),
        "cta_text": (15, 20, 40),
        "cta_border": (255, 255, 255),
        "price_color": (255, 255, 255),
        "overlay": True,
        "bg_fallback": (15, 25, 50),
    },
}

# Системные пути для разных ОС — Railway использует Debian/Ubuntu
SYSTEM_FONT_PATHS = [
    # Noto Sans (устанавливается через nixpacks на Railway)
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    # DejaVu — почти всегда есть
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # Liberation — альтернатива
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

def _find_system_font(bold: bool = False) -> str | None:
    """Ищет любой доступный системный шрифт."""
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_font(size, weight="regular", brand_style="universal"):
    weight_map = {
        "bold": "bold.ttf",
        "semibold": "semibold.ttf",
        "regular": "regular.ttf",
        "light": "light.ttf",
    }
    subdir = BRAND_FONT_DIRS.get(brand_style, "universal")
    filename = weight_map.get(weight, "regular.ttf")

    # Сначала пробуем папку проекта (fonts/)
    for folder in [subdir, "universal"]:
        path = os.path.join(FONTS_DIR, folder, filename)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Fallback на системные шрифты
    is_bold = weight in ("bold", "semibold")
    system_path = _find_system_font(bold=is_bold)
    if system_path:
        try:
            return ImageFont.truetype(system_path, size)
        except Exception:
            pass

    # Последний резерв — Pillow default (мелкий но не падает)
    try:
        # Pillow 10+ поддерживает size в load_default
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _add_overlay(img, style):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    W, H = img.size
    if style == "minimal":
        for y in range(int(H * 0.58)):
            alpha = int(200 * (1.0 - y / (H * 0.58)))
            draw.line([(0, y), (W, y)], fill=(255, 255, 255, alpha))
    else:
        start_y = int(H * 0.25)
        for y in range(start_y, H):
            progress = (y - start_y) / (H - start_y)
            alpha = int(190 * min(progress * 1.4, 1.0))
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def render_banner(plan: CreativePlan,
                  source_image_path: str = None,
                  output_path: str = "output.png") -> str:
    W, H = 1080, 1080
    theme = THEMES.get(plan.style, THEMES["minimal"])
    brand_style = getattr(plan, "brand_style", "universal")
    PAD = 52
    max_w = W - PAD * 2

    # ФОН
    if source_image_path and os.path.exists(source_image_path):
        bg = Image.open(source_image_path).convert("RGB")
        img_ratio = bg.width / bg.height
        if img_ratio > 1:
            new_h, new_w = H, int(H * img_ratio)
        else:
            new_w, new_h = W, int(W / img_ratio)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - W) // 2
        top = (new_h - H) // 2
        bg = bg.crop((left, top, left + W, top + H))
    else:
        bg = Image.new("RGB", (W, H), theme["bg_fallback"])

    bg = _add_overlay(bg, plan.style).convert("RGB")
    draw = ImageDraw.Draw(bg)

    x, y = PAD, PAD

    # BADGE
    if plan.badge:
        font = _get_font(22, "semibold", brand_style)
        bbox = draw.textbbox((0, 0), plan.badge, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        px, py = 14, 7
        draw.rounded_rectangle(
            [x, y, x+tw+px*2, y+th+py*2],
            radius=5, fill=theme["badge_bg"]
        )
        draw.text((x+px, y+py), plan.badge, font=font, fill=theme["badge_text"])
        y += th + py*2 + 20

    # HEADLINE
    if plan.headline:
        font = _get_font(66, "bold", brand_style)
        chars = max(8, int(max_w / (66 * 0.52)))
        for line in textwrap.wrap(plan.headline, width=chars)[:3]:
            draw.text((x, y), line, font=font, fill=theme["text_primary"])
            bbox = draw.textbbox((x, y), line, font=font)
            y += (bbox[3]-bbox[1]) + 6
        y += 12

    # SUBHEADLINE
    if plan.subheadline:
        font = _get_font(26, "light", brand_style)
        draw.text((x, y), plan.subheadline, font=font, fill=theme["text_secondary"])
        bbox = draw.textbbox((x, y), plan.subheadline, font=font)
        y += (bbox[3]-bbox[1]) + 18

    # PRICE
    if plan.price:
        font = _get_font(44, "bold", brand_style)
        bbox = draw.textbbox((x, y), plan.price, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        px, py = 16, 8
        draw.rounded_rectangle(
            [x-px, y-py, x+tw+px, y+th+py],
            radius=6, outline=theme["price_color"], width=2
        )
        draw.text((x, y), plan.price, font=font, fill=theme["price_color"])
        y += th + py + 22

    # BULLETS
    if plan.bullets:
        font = _get_font(26, "regular", brand_style)
        for bullet in plan.bullets[:3]:
            text = bullet if bullet.startswith("—") else f"— {bullet}"
            draw.text((x, y), text, font=font, fill=theme["text_secondary"])
            bbox = draw.textbbox((x, y), text, font=font)
            y += (bbox[3]-bbox[1]) + 10
        y += 8

    # CTA
    if plan.cta:
        font = _get_font(26, "semibold", brand_style)
        bbox = draw.textbbox((0, 0), plan.cta, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        px, py = 32, 14
        btn_w = min(tw + px*2, max_w)
        cta_y = min(y + 10, int(H * 0.55))
        rect = [x, cta_y, x+btn_w, cta_y+th+py*2]
        draw.rounded_rectangle(rect, radius=8, fill=theme["cta_bg"])
        if plan.style == "minimal":
            draw.rounded_rectangle(
                rect, radius=8,
                outline=theme["cta_border"], width=2
            )
        draw.text(
            (x + (btn_w-tw)//2, cta_y+py),
            plan.cta, font=font, fill=theme["cta_text"]
        )

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )
    bg.save(output_path, "PNG", quality=95)
    return output_path
