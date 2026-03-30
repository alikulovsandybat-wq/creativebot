import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import (
    _remove_background, _generate_background,
    _composite, _download_image, _get_decoration_hint,
    _analyze_subject, generate_image_from_text
)
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)
STYLES = ["minimal", "conversion", "premium"]


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "/tmp/creative_outputs",
                            ad_text: str = "",
                            send_callback=None) -> list[str]:
    """
    Генерирует баннеры по одному.
    send_callback(path, label) — вызывается сразу после каждого баннера.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []

    if source_image_path and os.path.exists(source_image_path):
        logger.info("Removing background ONCE...")
        obj_img = await asyncio.to_thread(_remove_background, source_path=source_image_path)

        subject_desc = await _analyze_subject(source_image_path)
        decoration_hint = _get_decoration_hint(ad_text)
        logger.info(f"Subject: {subject_desc}")

        labels = {"minimal": "🤍 Minimal", "conversion": "🎯 Conversion", "premium": "✨ Premium"}

        for style in STYLES:
            try:
                logger.info(f"Generating {style}...")

                # Генерируем фон
                bg_url = await _generate_background(style, subject_desc, decoration_hint)

                # Скачиваем фон
                bg_path = os.path.join(output_dir, f"bg_{style}.png")
                await _download_image(bg_url, bg_path)
                bg_img = Image.open(bg_path).convert("RGB")

                # Композитинг
                result = _composite(bg_img, obj_img, (1080, 1080))
                result = ImageEnhance.Contrast(result).enhance(1.05)
                comp_path = os.path.join(output_dir, f"composite_{style}.png")
                result.save(comp_path, "PNG", quality=95)

                # Рендерим текст
                variant = copy.deepcopy(plan)
                variant.style = style
                out_path = os.path.join(output_dir, f"banner_{style}.png")
                await asyncio.to_thread(render_banner, variant, comp_path, out_path)

                output_paths.append(out_path)
                logger.info(f"Done: {style}")

                # Сразу отправляем пользователю
                if send_callback and os.path.exists(out_path):
                    await send_callback(out_path, labels[style])

            except Exception as e:
                logger.error(f"Failed {style}: {e}", exc_info=True)

    else:
        logger.info("No photo — generating from text one by one")
        labels = {"minimal": "🤍 Minimal", "conversion": "🎯 Conversion", "premium": "✨ Premium"}

        for style in STYLES:
            try:
                bg_path = await generate_image_from_text(ad_text or plan.headline, style)

                variant = copy.deepcopy(plan)
                variant.style = style
                out_path = os.path.join(output_dir, f"banner_{style}.png")
                await asyncio.to_thread(render_banner, variant, bg_path, out_path)

                output_paths.append(out_path)

                if send_callback and os.path.exists(out_path):
                    await send_callback(out_path, labels[style])

            except Exception as e:
                logger.error(f"Failed {style}: {e}", exc_info=True)

    return output_paths
