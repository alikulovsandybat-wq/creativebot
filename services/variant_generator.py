import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import (
    remove_background_api,
    generate_background,
    generate_image_from_text,
    _download_image,
    _composite,
    CANVAS_SIZE as DEFAULT_CANVAS,
)
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

# Один стиль темы — определяется по brand_style пользователя
# minimal / conversion / premium — маппинг из brand_style
BRAND_TO_STYLE = {
    "delicate": "minimal",
    "cozy": "minimal",
    "universal": "minimal",
    "bold": "conversion",
    "premium_brand": "premium",
}


async def generate_variants(plan: CreativePlan,
                             source_image_path: str = None,
                             output_dir: str = "/tmp/creative_outputs",
                             ad_text: str = "",
                             send_callback=None,
                             layout: str = "A",
                             canvas_size: tuple = None) -> list[str]:
    """
    Генерирует один баннер (не три) согласно выбранному layout и формату.

    layout: "A", "B", "C"
    canvas_size: (1080, 1080) для квадрата или (1080, 1920) для Stories
    """
    os.makedirs(output_dir, exist_ok=True)

    # Определяем размер canvas
    if canvas_size is None:
        canvas_size = DEFAULT_CANVAS

    # Определяем стиль темы из brand_style
    brand_style = getattr(plan, "brand_style", "universal")
    theme_style = BRAND_TO_STYLE.get(brand_style, "minimal")

    # Берём промпт фона из плана (уже определён в creative_planner)
    bg_prompt = getattr(plan, "bg_prompt", "")
    niche = getattr(plan, "niche", "universal")

    logger.info(f"generate_variants: layout={layout}, canvas={canvas_size}, "
                f"niche={niche}, theme={theme_style}")

    output_paths = []

    try:
        if source_image_path and os.path.exists(source_image_path):
            # ── РЕЖИМ С ФОТО ──
            # Параллельно: remove.bg + генерация фона
            logger.info("Mode: photo + background")

            bg_url_coro = generate_background(bg_prompt, layout)
            obj_coro = remove_background_api(source_image_path)
            bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

            # Скачиваем фон
            bg_path = os.path.join(output_dir, f"bg_{layout}.png")
            await _download_image(bg_url, bg_path)
            bg_img = Image.open(bg_path).convert("RGB")

            # Компонуем фон + продукт
            result = _composite(bg_img, obj_img, layout)
            result = ImageEnhance.Contrast(result).enhance(1.05)

            # Ресайз под нужный canvas если квадрат
            if canvas_size != DEFAULT_CANVAS:
                result = result.resize(canvas_size, Image.LANCZOS)

            comp_path = os.path.join(output_dir, f"composite_{layout}.png")
            result.save(comp_path, "PNG", quality=95)

        else:
            # ── РЕЖИМ БЕЗ ФОТО ──
            logger.info("Mode: background only (no photo)")

            comp_path = await generate_image_from_text(bg_prompt, layout)

            # Ресайз под нужный canvas если квадрат
            if canvas_size != DEFAULT_CANVAS:
                img = Image.open(comp_path)
                img = img.resize(canvas_size, Image.LANCZOS)
                img.save(comp_path, "PNG", quality=95)

        # ── РЕНДЕР ТЕКСТА ──
        variant = copy.deepcopy(plan)
        variant.style = theme_style

        out_path = os.path.join(output_dir, f"banner_{layout}.png")
        await asyncio.to_thread(
            render_banner, variant, comp_path, out_path, layout
        )
        output_paths.append(out_path)
        logger.info(f"Banner ready: {out_path} ✅")

        if send_callback and os.path.exists(out_path):
            fmt_label = "⬛ Квадрат" if canvas_size == (1080, 1080) else "📱 Stories"
            await send_callback(out_path, f"Layout {layout} · {fmt_label}")

    except Exception as e:
        logger.error(f"generate_variants failed: {e}", exc_info=True)

    return output_paths
