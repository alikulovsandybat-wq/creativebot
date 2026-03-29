import asyncio
import copy
import os
from models.creative import CreativePlan
from services.layout_renderer import render_banner


STYLES = ["premium", "conversion", "minimal"]


async def generate_variants(plan: CreativePlan,
                            source_image_path: str = None,
                            output_dir: str = "outputs") -> list[str]:
    """
    Генерирует 3 варианта баннера параллельно.
    Возвращает список путей к готовым файлам.
    """
    os.makedirs(output_dir, exist_ok=True)

    tasks = []
    paths = []

    for style in STYLES:
        variant = copy.deepcopy(plan)
        variant.style = style
        out_path = os.path.join(output_dir, f"banner_{style}.png")
        paths.append(out_path)
        tasks.append(
            asyncio.to_thread(render_banner, variant, source_image_path, out_path)
        )

    await asyncio.gather(*tasks)
    return paths
