import os
import textwrap
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from models.creative import CreativePlan
from services.typography_presets import PRESETS, TypographyPreset

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Загружает шрифт. Если нет кастомного — использует дефолтный."""
    name = "bold.ttf" if bold else "regular.ttf"
    path = os.path.join(FONTS_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        # Fallback на системный
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                                      else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _draw_gradient_overlay(img: Image.Image, preset: TypographyPreset) -> Image.Image:
    """Рисует градиентное затемнение снизу для читаемости текста."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    h = img.height
    start_y = int(h * preset.gradient_from_y)

    for y in range(start_y, h):
        progress = (y - start_y) / (h - start_y)
        alpha = int(preset.overlay_alpha * min(progress * 1.5, 1.0))
        r, g, b = preset.overlay_color
        draw.line([(0, y), (img.width, y)], fill=(r, g, b, alpha))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _draw_badge(draw: ImageDraw.Draw, text: str, x: int, y: int,
                preset: TypographyPreset) -> int:
    """Рисует бейдж. Возвращает высоту блока."""
    if not text:
        return 0
    font = _get_font(preset.badge_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    pad_x, pad_y = 20, 10
    rect = [x, y, x + tw + pad_x * 2, y + (bbox[3] - bbox[1]) + pad_y * 2]
    draw.rounded_rectangle(rect, radius=6, fill=preset.badge_bg)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=preset.badge_text)
    return rect[3] - rect[1] + 16


def _draw_text_block(draw: ImageDraw.Draw, plan: CreativePlan,
                     preset: TypographyPreset, canvas_w: int, canvas_h: int):
    """Рисует все текстовые элементы на баннере."""
    x = preset.text_zone_x
    y = preset.text_zone_y
    max_w = preset.text_zone_width

    # HEADLINE
    if plan.headline:
        font = _get_font(preset.headline_size, bold=True)
        # Перенос строк если слишком длинный
        chars_per_line = max(10, int(max_w / (preset.headline_size * 0.55)))
        lines = textwrap.wrap(plan.headline.upper(), width=chars_per_line)
        for line in lines[:3]:
            # Тень для читаемости
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 120))
            draw.text((x, y), line, font=font, fill=preset.text_primary)
            bbox = draw.textbbox((x, y), line, font=font)
            y += (bbox[3] - bbox[1]) + 8
        y += 12

    # SUBHEADLINE
    if plan.subheadline:
        font = _get_font(preset.subheadline_size, bold=False)
        draw.text((x, y), plan.subheadline, font=font, fill=preset.text_secondary)
        bbox = draw.textbbox((x, y), plan.subheadline, font=font)
        y += (bbox[3] - bbox[1]) + 20

    # PRICE
    if plan.price:
        font = _get_font(preset.price_size, bold=True)
        draw.text((x + 2, y + 2), plan.price, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), plan.price, font=font, fill=preset.accent_color)
        bbox = draw.textbbox((x, y), plan.price, font=font)
        y += (bbox[3] - bbox[1]) + 16

    # BULLETS
    if plan.bullets:
        font = _get_font(preset.bullet_size, bold=False)
        for bullet in plan.bullets[:4]:
            text = f"— {bullet}"
            draw.text((x, y), text, font=font, fill=preset.text_secondary)
            bbox = draw.textbbox((x, y), text, font=font)
            y += (bbox[3] - bbox[1]) + 10
        y += 16

    # CTA BUTTON
    if plan.cta:
        font = _get_font(preset.cta_size, bold=True)
        bbox = draw.textbbox((0, 0), plan.cta, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 36, 16
        btn_w = tw + pad_x * 2
        btn_h = th + pad_y * 2

        # Не выходим за пределы холста
        btn_y = min(y, canvas_h - btn_h - 40)
        rect = [x, btn_y, x + btn_w, btn_y + btn_h]
        draw.rounded_rectangle(rect, radius=8, fill=preset.cta_bg)
        draw.text((x + pad_x, btn_y + pad_y), plan.cta,
                  font=font, fill=preset.cta_text)


def render_banner(plan: CreativePlan, source_image_path: str = None,
                  output_path: str = "output.png") -> str:
    """
    Собирает финальный баннер.
    source_image_path — путь к фото пользователя (опционально).
    output_path — куда сохранить результат.
    Возвращает путь к готовому файлу.
    """
    preset = PRESETS.get(plan.style, PRESETS["conversion"])
    W, H = preset.canvas_w, preset.canvas_h

    # --- ФОНОВОЕ ИЗОБРАЖЕНИЕ ---
    if source_image_path and os.path.exists(source_image_path):
        bg = Image.open(source_image_path).convert("RGB")
        # Масштабируем с сохранением пропорций (cover)
        img_ratio = bg.width / bg.height
        canvas_ratio = W / H
        if img_ratio > canvas_ratio:
            new_h = H
            new_w = int(H * img_ratio)
        else:
            new_w = W
            new_h = int(W / img_ratio)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        # Кропаем по центру
        left = (new_w - W) // 2
        top = (new_h - H) // 2
        bg = bg.crop((left, top, left + W, top + H))
    else:
        # Генерируем градиентный фон
        bg = Image.new("RGB", (W, H), preset.bg_color)
        draw_bg = ImageDraw.Draw(bg)
        # Простой градиент
        r1, g1, b1 = preset.bg_color
        for y in range(H):
            factor = y / H
            r = int(r1 * (1 - factor * 0.3))
            g = int(g1 * (1 - factor * 0.3))
            b = int(b1 * (1 - factor * 0.3))
            draw_bg.line([(0, y), (W, y)], fill=(r, g, b))

    # Лёгкое размытие фона для глубины
    bg = bg.filter(ImageFilter.GaussianBlur(radius=1))

    # --- ГРАДИЕНТНЫЙ ОВЕРЛЕЙ ---
    bg = _draw_gradient_overlay(bg, preset).convert("RGB")

    # --- ТЕКСТОВЫЕ ЭЛЕМЕНТЫ ---
    draw = ImageDraw.Draw(bg)

    # Бейдж сверху
    _draw_badge(draw, plan.badge, preset.badge_x, preset.badge_y, preset)

    # Основной текстовый блок
    _draw_text_block(draw, plan, preset, W, H)

    # --- СОХРАНЯЕМ ---
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    bg.save(output_path, "PNG", quality=95)
    return output_path
