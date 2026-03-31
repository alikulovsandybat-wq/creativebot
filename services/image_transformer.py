import os
import base64
import asyncio
import logging
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from openai import AsyncOpenAI
import io

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# Размер Stories формат
CANVAS_SIZE = (1080, 1920)


async def remove_background_api(source_path: str) -> Image.Image:
    """Убирает фон через remove.bg API."""
    api_key = os.getenv("REMOVEBG_API_KEY", "")

    if not api_key:
        logger.warning("REMOVEBG_API_KEY not set, falling back to rembg")
        return await asyncio.to_thread(_remove_bg_local, source_path)

    try:
        with open(source_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("image_file", image_data,
                           filename="image.jpg",
                           content_type="image/jpeg")
            data.add_field("size", "auto")

            async with session.post(
                "https://api.remove.bg/v1.0/removebg",
                headers={"X-Api-Key": api_key},
                data=data
            ) as resp:
                if resp.status == 200:
                    result_data = await resp.read()
                    img = Image.open(io.BytesIO(result_data)).convert("RGBA")
                    logger.info("remove.bg: background removed ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"remove.bg error {resp.status}: {error}")
                    return await asyncio.to_thread(_remove_bg_local, source_path)

    except Exception as e:
        logger.error(f"remove.bg API failed: {e}")
        return await asyncio.to_thread(_remove_bg_local, source_path)


def _remove_bg_local(source_path: str) -> Image.Image:
    """Fallback — локальный rembg."""
    try:
        from rembg import remove
        with open(source_path, "rb") as f:
            result = remove(f.read())
        return Image.open(io.BytesIO(result)).convert("RGBA")
    except Exception as e:
        logger.error(f"rembg also failed: {e}")
        return Image.open(source_path).convert("RGBA")


async def generate_background(bg_prompt: str, layout: str = "A") -> str:
    """
    Генерирует фон по готовому промпту из словаря.
    layout определяет размер: всегда 9:16 (1024x1792).
    """
    logger.info(f"Generating background, layout={layout}: {bg_prompt[:80]}...")

    response = await client.images.generate(
        model="dall-e-3",
        prompt=bg_prompt,
        size="1024x1792",   # 9:16 вертикальный формат
        quality="standard",
        n=1
    )
    return response.data[0].url


async def _download_image(url: str, save_path: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, "wb") as f:
                    f.write(await resp.read())


def _composite(bg: Image.Image, obj: Image.Image,
               layout: str = "A") -> Image.Image:
    """
    Накладывает объект на фон согласно layout.
    Layout A: продукт центр (60% высоты от верха)
    Layout B: продукт снизу-центр (75% высоты от верха)
    Layout C: продукт справа (60% высоты от верха)
    """
    W, H = CANVAS_SIZE
    bg = bg.resize((W, H), Image.LANCZOS)

    # Размер объекта
    if layout == "C":
        max_obj_w = int(W * 0.50)
        max_obj_h = int(H * 0.45)
    else:
        max_obj_w = int(W * 0.80)
        max_obj_h = int(H * 0.45)

    ratio = obj.width / obj.height
    if obj.width / max_obj_w > obj.height / max_obj_h:
        new_w = max_obj_w
        new_h = int(max_obj_w / ratio)
    else:
        new_h = max_obj_h
        new_w = int(max_obj_h * ratio)

    obj_resized = obj.resize((new_w, new_h), Image.LANCZOS)

    # Позиция по layout
    if layout == "A":
        # Центр по горизонтали, 55% сверху
        ox = (W - new_w) // 2
        oy = int(H * 0.55) - new_h // 2
    elif layout == "B":
        # Центр по горизонтали, 70% сверху (ближе к низу)
        ox = (W - new_w) // 2
        oy = int(H * 0.70) - new_h // 2
    elif layout == "C":
        # Правая половина, 55% сверху
        ox = int(W * 0.50)
        oy = int(H * 0.55) - new_h // 2
    else:
        ox = (W - new_w) // 2
        oy = int(H * 0.55) - new_h // 2

    # Тень под объект
    sh_h = max(int(new_h * 0.04), 20)
    shadow = Image.new("RGBA", (new_w, sh_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [new_w // 6, 0, new_w * 5 // 6, sh_h],
        fill=(0, 0, 0, 50)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))

    result = bg.convert("RGBA")
    shadow_y = oy + new_h - sh_h // 2
    result.paste(shadow, (ox, shadow_y), shadow)
    result.paste(obj_resized, (ox, oy), obj_resized)

    # Лёгкое улучшение контраста
    result = result.convert("RGB")
    result = ImageEnhance.Contrast(result).enhance(1.05)
    return result


async def transform_image(source_path: str,
                          bg_prompt: str,
                          layout: str = "A",
                          ad_text: str = "") -> str:
    """
    Основная функция: вырезает фон продукта + генерирует фон + компонует.
    bg_prompt — готовый промпт из словаря NICHE_BACKGROUNDS.
    layout — "A", "B", или "C".
    """
    logger.info(f"transform_image: layout={layout}, source={source_path}")

    try:
        # Параллельно: remove.bg + генерация фона
        bg_url_coro = generate_background(bg_prompt, layout)
        obj_coro = remove_background_api(source_path)
        bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

        out_dir = os.path.dirname(source_path)
        bg_path = os.path.join(out_dir, f"bg_{layout}.png")
        await _download_image(bg_url, bg_path)
        bg_img = Image.open(bg_path).convert("RGB")

        result = _composite(bg_img, obj_img, layout)

        out_path = os.path.join(out_dir, f"composite_{layout}.png")
        result.save(out_path, "PNG", quality=95)
        logger.info(f"Composite saved: {out_path} ✅")
        return out_path

    except Exception as e:
        logger.error(f"transform_image failed: {e}", exc_info=True)
        return await _fallback(source_path, layout)


async def generate_image_from_text(bg_prompt: str,
                                    layout: str = "A") -> str:
    """Когда пользователь не прислал фото — генерируем только фон."""
    try:
        response = await client.images.generate(
            model="dall-e-3",
            prompt=bg_prompt,
            size="1024x1792",
            quality="standard",
            n=1
        )
        out_dir = "/tmp/creative_temp"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"bg_only_{layout}.png")
        await _download_image(response.data[0].url, out_path)

        # Ресайз до нашего canvas
        img = Image.open(out_path)
        img = img.resize(CANVAS_SIZE, Image.LANCZOS)
        img.save(out_path, "PNG", quality=95)
        return out_path

    except Exception as e:
        logger.error(f"generate_image_from_text failed: {e}")
        return await _fallback(None, layout)


async def _fallback(source_path, layout):
    return await asyncio.to_thread(_fallback_sync, source_path, layout)


def _fallback_sync(source_path, layout):
    """Запасной вариант — градиентный фон если всё сломалось."""
    COLORS = {
        "A": [(245, 243, 238), (225, 222, 215)],
        "B": [(238, 245, 243), (215, 225, 222)],
        "C": [(238, 240, 245), (215, 218, 225)],
    }
    W, H = CANVAS_SIZE
    c1, c2 = COLORS.get(layout, COLORS["A"])
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t)
        ))
    if source_path and os.path.exists(source_path):
        src = Image.open(source_path).convert("RGB")
        ratio = src.width / src.height
        new_h = int(H * 0.45)
        new_w = min(int(new_h * ratio), W)
        new_h = int(new_w / ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        ox = (W - new_w) // 2
        oy = int(H * 0.55) - new_h // 2
        bg.paste(src, (ox, oy))

    out_dir = "/tmp/creative_temp"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"composite_{layout}.png")
    bg.save(out_path, "PNG", quality=95)
    return out_path
