import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import (
    transform_image_with_obj, generate_image_from_text,
    _remove_background, _generate_background,
    _composite, _download_image, _get_decoration_hint,
    _analyze_subject
)
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)
STYLES = ["premium", "conversion", "minimal"]


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "/tmp/creative_outputs",
                            ad_text: str = "") -> list[str]:
    os.makedirs(output_dir, exist_ok=True)

    if source_image_path and os.path.exists(source_image_path):
        logger.info("Compositing: removing background ONCE, then generating 3 backgrounds")

        # Шаг 1 — вырезаем объект ОДИН РАЗ
        obj_img = await asyncio.to_thread(_remove_background, source_path=source_image_path)
        logger.info("Object extracted successfully")

        # Шаг 2 — анализируем объект и декорации
        subject_desc = await _analyze_subject(source_image_path)
        decoration_hint = _get_decoration_hint(ad_text)
        logger.info(f"Subject: {subject_desc}, decoration: {decoration_hint}")

        # Шаг 3 — генерируем 3 фона параллельно (без rembg — только DALL-E)
        bg_tasks = [
            _generate_background(style, subject_desc, decoration_hint)
            for style in STYLES
        ]
        bg_urls = await asyncio.gather(*bg_tasks)

        # Шаг 4 — скачиваем фоны и делаем композитинг
        composite_paths = []
        for style, bg_url in zip(STYLES, bg_urls):
            bg_path = os.path.join(output_dir, f"bg_{style}.png")
            await _download_image(bg_url, bg_path)
            bg_img = Image.open(bg_path).convert("RGB")

            result = _composite(bg_img, obj_img, (1080, 1080))
            result = ImageEnhance.Contrast(result).enhance(1.05)

            comp_path = os.path.join(output_dir, f"composite_{style}.png")
            result.save(comp_path, "PNG", quality=95)
            composite_paths.append(comp_path)
            logger.info(f"Composite done: {style}")

        transformed_paths = composite_paths

    else:
        logger.info("No photo — generating from text")
        transform_tasks = [
            generate_image_from_text(ad_text or plan.headline, style)
            for style in STYLES
        ]
        transformed_paths = await asyncio.gather(*transform_tasks, return_exceptions=True)

    # Рендерим текст поверх
    render_tasks = []
    output_paths = []

    for style, transformed_path in zip(STYLES, transformed_paths):
        variant = copy.deepcopy(plan)
        variant.style = style
        out_path = os.path.join(output_dir, f"banner_{style}.png")
        output_paths.append(out_path)

        bg_path = transformed_path if isinstance(transformed_path, str) else None
        render_tasks.append(
            asyncio.to_thread(render_banner, variant, bg_path, out_path)
        )

    await asyncio.gather(*render_tasks)
    return output_paths
