import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import (
    _generate_background, _download_image,
    _get_decoration_hint, _analyze_subject,
    generate_image_from_text, _composite
)
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)
STYLES = ["minimal", "conversion", "premium"]


def _remove_bg(source_path: str) -> Image.Image:
    """Вырезает фон. Если rembg недоступен — возвращает исходник."""
    try:
        from rembg import remove
        with open(source_path, "rb") as f:
            result = remove(f.read())
        import io
        return Image.open(io.BytesIO(result)).convert("RGBA")
    except Exception as e:
        logger.warning(f"rembg unavailable: {e}, using original photo")
        return Image.open(source_path).convert("RGBA")


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "/tmp/creative_outputs",
                            ad_text: str = "",
                            send_callback=None) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []

    labels = {
        "minimal": "🤍 Minimal",
        "conversion": "🎯 Conversion",
        "premium": "✨ Premium"
    }

    if source_image_path and os.path.exists(source_image_path):
        # Анализируем фото
        subject_desc = await _analyze_subject(source_image_path)
        decoration_hint = _get_decoration_hint(ad_text)
        logger.info(f"Subject: {subject_desc}")

        # Вырезаем фон ОДИН РАЗ в отдельном потоке
        logger.info("Removing background...")
        obj_img = await asyncio.to_thread(_remove_bg, source_path=source_image_path)
        logger.info("Background removed ✅")

        for style in STYLES:
            try:
                logger.info(f"Generating {style}...")

                bg_url = await _generate_background(style, subject_desc, decoration_hint)
                bg_path = os.path.join(output_dir, f"bg_{style}.png")
                await _download_image(bg_url, bg_path)
                bg_img = Image.open(bg_path).convert("RGB")

                # Композитинг — объект на новый фон
                result = _composite(bg_img, obj_img, (1080, 1080))
                result = ImageEnhance.Contrast(result).enhance(1.03)

                comp_path = os.path.join(output_dir, f"composite_{style}.png")
                result.save(comp_path, "PNG", quality=95)

                # Текст поверх
                variant = copy.deepcopy(plan)
                variant.style = style
                out_path = os.path.join(output_dir, f"banner_{style}.png")
                await asyncio.to_thread(render_banner, variant, comp_path, out_path)

                output_paths.append(out_path)
                logger.info(f"Done: {style} ✅")

                if send_callback and os.path.exists(out_path):
                    await send_callback(out_path, labels[style])

            except Exception as e:
                logger.error(f"Failed {style}: {e}", exc_info=True)

    else:
        logger.info("No photo — generating from text")
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
