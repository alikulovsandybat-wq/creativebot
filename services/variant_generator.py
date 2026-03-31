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
                             canvas_size: tuple = None) -> dict:
    """
    Возвращает dict:
      {
        "banner": path к финальному баннеру,
        "bg": path к фону (без продукта),
        "product": path к вырезанному продукту (если есть),
      }
    """
    os.makedirs(output_dir, exist_ok=True)

    if canvas_size is None:
        canvas_size = DEFAULT_CANVAS

    brand_style = getattr(plan, "brand_style", "universal")
    theme_style = BRAND_TO_STYLE.get(brand_style, "minimal")
    bg_prompt = getattr(plan, "bg_prompt", "")
    photoroom_prompt = getattr(plan, "photoroom_prompt", bg_prompt)
    niche = getattr(plan, "niche", "universal")

    logger.info(f"generate_variants: layout={layout}, canvas={canvas_size}, niche={niche}")

    result_paths = {"banner": None, "bg": None, "product": None}

    try:
        bg_path = os.path.join(output_dir, f"bg_{layout}.png")
        prod_path = os.path.join(output_dir, f"product_{layout}.png")

        if source_image_path and os.path.exists(source_image_path):
            # ── РЕЖИМ С ФОТО ──
            logger.info("Mode: photo + background")

            bg_url_coro = generate_background(bg_prompt, layout)
            obj_coro = remove_background_api(source_image_path)
            bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

            # Сохраняем чистый фон отдельно
            await _download_image(bg_url, bg_path)
            result_paths["bg"] = bg_path

            # Сохраняем вырезанный продукт отдельно
            obj_img.save(prod_path, "PNG")
            result_paths["product"] = prod_path

            # Компонуем через transform_image с умным выбором инструмента
            from services.image_transformer import transform_image
            comp_path = await transform_image(
                source_image_path,
                photoroom_prompt if niche in ["auto","auto_parts","tech","home","food","health","medical","fashion","beauty","perfume","flowers","kids"] else bg_prompt,
                layout=layout,
                niche=niche
            )

            if canvas_size != DEFAULT_CANVAS:
                img = Image.open(comp_path)
                img = img.resize(canvas_size, Image.LANCZOS)
                img.save(comp_path, "PNG", quality=95)

        else:
            # ── РЕЖИМ БЕЗ ФОТО ──
            logger.info("Mode: background only (no photo)")
            comp_path = await generate_image_from_text(bg_prompt, layout)
            if canvas_size != DEFAULT_CANVAS:
                img = Image.open(comp_path)
                img = img.resize(canvas_size, Image.LANCZOS)
                img.save(comp_path, "PNG", quality=95)

            # Копируем как bg для редактора
            import shutil
            shutil.copy2(comp_path, bg_path)
            result_paths["bg"] = bg_path

        # ── РЕНДЕР ТЕКСТА ──
        variant = copy.deepcopy(plan)
        variant.style = theme_style

        out_path = os.path.join(output_dir, f"banner_{layout}.png")
        await asyncio.to_thread(render_banner, variant, comp_path, out_path, layout)
        result_paths["banner"] = out_path
        logger.info(f"Banner ready: {out_path} ✅")

        if send_callback and os.path.exists(out_path):
            fmt_label = "⬛ Квадрат" if canvas_size == (1080, 1080) else "📱 Stories"
            await send_callback(out_path, f"Layout {layout} · {fmt_label}")

    except Exception as e:
        logger.error(f"generate_variants failed: {e}", exc_info=True)

    return result_paths

