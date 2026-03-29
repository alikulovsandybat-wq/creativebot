import os
import base64
import asyncio
import logging
import aiohttp
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

STYLE_PROMPTS = {
    "premium": (
        "luxury dark background, dramatic studio lighting, deep shadows, "
        "elegant atmosphere, high-end commercial photography, black and gold tones, "
        "cinematic depth of field, premium product advertisement"
    ),
    "conversion": (
        "bright dynamic background, vibrant colors, energetic commercial photography, "
        "clean modern style, bold advertising visual, product spotlight, "
        "professional ad campaign, eye-catching composition"
    ),
    "minimal": (
        "clean white or light grey background, soft natural lighting, "
        "minimalist product photography, airy and fresh aesthetic, "
        "Scandinavian style, negative space, elegant simplicity"
    ),
}


async def _analyze_image(image_path: str) -> dict:
    """
    GPT-4 Vision анализирует фото:
    - что за продукт
    - какие визуальные элементы добавить исходя из контекста
    - цвета и стиль
    """
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}",
                        "detail": "low"
                    }
                },
                {
                    "type": "text",
                    "text": (
                        "Describe this product/subject for a commercial photo shoot. "
                        "Return JSON only:\n"
                        "{\n"
                        '  "subject": "exact description of main subject",\n'
                        '  "category": "product category (car/clothing/food/beauty/etc)",\n'
                        '  "colors": "main colors of subject",\n'
                        '  "additions": "what props/elements to add around it for advertising (e.g. gift ribbon, snow, flowers)"\n'
                        "}"
                    )
                }
            ]
        }]
    )

    import json
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except Exception:
        return {
            "subject": "product",
            "category": "product",
            "colors": "neutral",
            "additions": "decorative elements"
        }


async def _generate_scene(analysis: dict, style: str, canvas_size: tuple) -> str:
    """
    DALL-E 3 генерирует рекламную сцену на основе анализа.
    Возвращает URL сгенерированного изображения.
    """
    style_desc = STYLE_PROMPTS.get(style, STYLE_PROMPTS["conversion"])
    w, h = canvas_size

    prompt = (
        f"Professional advertising photograph: {analysis['subject']} "
        f"({analysis['colors']} colors) with {analysis['additions']}. "
        f"Style: {style_desc}. "
        f"Leave the bottom third of the image darker/blurred for text overlay. "
        f"No text, no words, no letters in the image. "
        f"Square format, ultra high quality commercial photography."
    )

    logger.info(f"DALL-E prompt: {prompt[:100]}...")

    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1
    )

    return response.data[0].url


async def _download_image(url: str, save_path: str):
    """Скачивает сгенерированное изображение."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, "wb") as f:
                    f.write(await resp.read())


async def transform_image(source_path: str, style: str,
                          canvas_size: tuple = (1080, 1080)) -> str:
    """
    Полный пайплайн трансформации:
    1. GPT-4 Vision анализирует фото
    2. DALL-E генерирует рекламную сцену
    3. Возвращает путь к готовому фону
    """
    logger.info(f"Transforming image: {source_path}, style: {style}")

    try:
        # Шаг 1 — анализируем фото
        analysis = await _analyze_image(source_path)
        logger.info(f"Analysis: {analysis}")

        # Шаг 2 — генерируем сцену
        image_url = await _generate_scene(analysis, style, canvas_size)
        logger.info(f"Generated URL: {image_url[:50]}...")

        # Шаг 3 — скачиваем
        out_dir = os.path.dirname(source_path)
        out_path = os.path.join(out_dir, f"transformed_{style}.png")
        await _download_image(image_url, out_path)

        # Шаг 4 — ресайз под canvas
        img = Image.open(out_path).convert("RGB")
        img = img.resize(canvas_size, Image.LANCZOS)
        img.save(out_path, "PNG", quality=95)

        logger.info(f"Transformed image saved: {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"Transform failed: {e}, using gradient fallback")
        return await _gradient_fallback(source_path, style, canvas_size)


async def _gradient_fallback(source_path: str, style: str,
                             canvas_size: tuple) -> str:
    """
    Fallback если DALL-E недоступен —
    красивый градиентный фон с исходным фото.
    """
    return await asyncio.to_thread(
        _gradient_fallback_sync, source_path, style, canvas_size
    )


def _gradient_fallback_sync(source_path: str, style: str,
                             canvas_size: tuple) -> str:
    BACKGROUNDS = {
        "premium": [(10, 10, 20), (30, 20, 50)],
        "conversion": [(15, 25, 50), (20, 40, 80)],
        "minimal": [(240, 238, 230), (220, 218, 210)],
    }
    W, H = canvas_size
    colors = BACKGROUNDS.get(style, BACKGROUNDS["conversion"])
    c1, c2 = colors

    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    if source_path and os.path.exists(source_path):
        src = Image.open(source_path).convert("RGB")
        max_w, max_h = int(W * 0.9), int(H * 0.6)
        ratio = src.width / src.height
        new_w = min(max_w, int(max_h * ratio))
        new_h = int(new_w / ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        ox = (W - new_w) // 2
        oy = H - new_h - 40
        bg.paste(src, (ox, oy))

    out_dir = os.path.dirname(source_path) if source_path else "/tmp"
    out_path = os.path.join(out_dir, f"transformed_{style}.png")
    bg.save(out_path, "PNG", quality=95)
    return out_path


async def generate_image_from_text(ad_text: str, style: str,
                                   canvas_size: tuple = (1080, 1080)) -> str:
    """
    Когда пользователь дал только текст без фото —
    GPT придумывает визуал, DALL-E рисует.
    """
    style_desc = STYLE_PROMPTS.get(style, STYLE_PROMPTS["conversion"])

    # GPT придумывает что нарисовать
    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"Based on this ad text, describe a perfect product/scene for a DALL-E image. "
                f"Return only a short English description (max 50 words) of what to show visually. "
                f"No text in image. Ad text: {ad_text}"
            )
        }]
    )

    visual_desc = response.choices[0].message.content.strip()
    logger.info(f"Visual description: {visual_desc}")

    prompt = (
        f"{visual_desc}. "
        f"Style: {style_desc}. "
        f"Leave bottom third darker for text overlay. "
        f"No text, no words. Square format, ultra high quality commercial photography."
    )

    img_response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1
    )

    url = img_response.data[0].url
    out_path = f"/tmp/creative_temp/generated_{style}.png"
    os.makedirs("/tmp/creative_temp", exist_ok=True)
    await _download_image(url, out_path)

    img = Image.open(out_path).resize(canvas_size, Image.LANCZOS)
    img.save(out_path, "PNG", quality=95)

    return out_path
