import asyncio
import copy
import os
import logging
from models.creative import CreativePlan
from services.layout_renderer import render_banner
from services.image_transformer import transform_image, generate_image_from_text

logger = logging.getLogger(__name__)
STYLES = ["premium", "conversion", "minimal"]


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "/tmp/creative_outputs",
                            ad_text: str = "") -> list[str]:
    os.makedirs(output_dir, exist_ok=True)

    if source_image_path and os.path.exists(source_image_path):
        logger.info("Using compositing with source photo")
        transform_tasks = [
            transform_image(source_image_path, style,
                          ad_text=ad_text)
            for style in STYLES
        ]
    else:
        logger.info("No photo — generating from text")
        transform_tasks = [
            generate_image_from_text(ad_text or plan.headline, style)
            for style in STYLES
        ]

    transformed_paths = await asyncio.gather(*transform_tasks, return_exceptions=True)

    render_tasks = []
    output_paths = []

    for style, transformed_path in zip(STYLES, transformed_paths):
        variant = copy.deepcopy(plan)
        variant.style = style
        out_path = os.path.join(output_dir, f"banner_{style}.png")
        output_paths.append(out_path)

        bg_path = transformed_path if isinstance(transformed_path, str) else None
        logger.info(f"Rendering {style}, bg: {bg_path}")

        render_tasks.append(
            asyncio.to_thread(render_banner, variant, bg_path, out_path)
        )

    await asyncio.gather(*render_tasks)
    return output_paths
