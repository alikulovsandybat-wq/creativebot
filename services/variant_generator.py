import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import (
    _generate_background, _download_image,
    _get_decoration_hint, _analyze_subject,
    generate_image_from_text, _composite,
    _generate_background_from_prompt
)
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)
STYLES = ["minimal", "conversion", "premium"]


def _remove_bg(source_path: str) -> Image.Image:
    try:
        from rembg import remove
        with open(source_path, "rb") as f:
            result = remove(f.read())
        import io
        return Image.open(io.BytesIO(result)).convert("RGBA")
    except Exception as e:
        logger.warning(f"rembg unavailable: {e}")
        return Image.open(source_path).convert("RGBA")


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "/tmp/creative_outputs",
                            ad_text: str = "",
                            send_callback=None,
                            replace_bg: bool = False) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []

    labels = {
        "minimal": "🤍 Minimal",
        "conversion": "🎯 Conversion",
        "premium": "✨ Premium"
    }

    if source_image_path and os.path.exists(source_image_path):

        if replace_bg:
            # Режим замены фона — rembg + DALL-E
            subject_desc = await _analyze_subject(source_image_path)
            logger.info(f"Replace BG mode. Subject: {subject_desc}")

            logger.info("Removing background...")
            obj_img = await asyncio.to_thread(_remove_bg, source_path=source_image_path)
            logger.info("Background removed ✅")

            # Карта промптов по стилям
            bg_prompts = {
                "minimal": getattr(plan, "bg_minimal", ""),
                "conversion": getattr(plan, "bg_conversion", ""),
                "premium": getattr(plan, "bg_premium", ""),
            }

            for style in STYLES:
                try:
                    logger.info(f"Generating {style}...")
                    bg_prompt = bg_prompts.get(style, "")

                    if bg_prompt:
                        # Используем смысловой промпт от GPT
                        bg_url = await _generate_background_from_prompt(
                            bg_prompt, style, ""
                        )
                    else:
                        # Fallback
                        bg_url = await _generate_background(
                            style, subject_desc, ""
                        )
                    bg_path = os.path.join(output_dir, f"bg_{style}.png")
                    await _download_image(bg_url, bg_path)
                    bg_img = Image.open(bg_path).convert("RGB")

                    result = _composite(bg_img, obj_img, (1080, 1080))
                    result = ImageEnhance.Contrast(result).enhance(1.03)
                    comp_path = os.path.join(output_dir, f"composite_{style}.png")
                    result.save(comp_path, "PNG", quality=95)

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
            # Режим сохранения фото — просто накладываем текст
            logger.info("Keep photo mode — overlay text only")
            for style in STYLES:
                try:
                    variant = copy.deepcopy(plan)
                    variant.style = style
                    out_path = os.path.join(output_dir, f"banner_{style}.png")
                    await asyncio.to_thread(
                        render_banner, variant, source_image_path, out_path
                    )
                    output_paths.append(out_path)
                    logger.info(f"Done: {style} ✅")

                    if send_callback and os.path.exists(out_path):
                        await send_callback(out_path, labels[style])
                except Exception as e:
                    logger.error(f"Failed {style}: {e}", exc_info=True)

    else:
        logger.info("No photo — generating from text")

        # Карта промптов по стилям
        bg_prompts = {
            "minimal": getattr(plan, "bg_minimal", ""),
            "conversion": getattr(plan, "bg_conversion", ""),
            "premium": getattr(plan, "bg_premium", ""),
        }

        for style in STYLES:
            try:
                bg_prompt = bg_prompts.get(style, "")

                if bg_prompt:
                    bg_url = await _generate_background_from_prompt(
                        bg_prompt, style, ""
                    )
                    bg_path = os.path.join(output_dir, f"bg_text_{style}.png")
                    await _download_image(bg_url, bg_path)
                    img = Image.open(bg_path).resize((1080, 1080), Image.LANCZOS)
                    img.save(bg_path, "PNG", quality=95)
                else:
                    bg_path = await generate_image_from_text(
                        ad_text or plan.headline, style
                    )

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
