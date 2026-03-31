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

CANVAS_SIZE = (1080, 1920)


# ═══════════════════════════════════════════════
# PHOTOROOM API — органичное наложение продукта
# ═══════════════════════════════════════════════

async def photoroom_generate_scene(source_path: str, scene_prompt: str) -> Image.Image:
    """
    Photoroom Image Editing API:
    - Вырезает продукт
    - Генерирует сцену по промпту
    - Добавляет тени и освещение автоматически
    Возвращает готовое изображение с продуктом в сцене.
    """
    api_key = os.getenv("PHOTOROOM_API_KEY", "")
    if not api_key:
        logger.warning("PHOTOROOM_API_KEY not set, falling back")
        return None

    try:
        with open(source_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field(
                "imageFile", image_data,
                filename="product.jpg",
                content_type="image/jpeg"
            )
            # Промпт сцены — Photoroom генерирует фон вокруг продукта
            data.add_field("background.prompt", scene_prompt)
            # Автоматические тени
            data.add_field("shadow.mode", "ai.soft")
            # Формат вывода
            data.add_field("outputSize", "1080x1920")
            data.add_field("outputFormat", "png")

            async with session.post(
                "https://image-api.photoroom.com/v2/edit",
                headers={"x-api-key": api_key},
                data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.read()
                    img = Image.open(io.BytesIO(result)).convert("RGBA")
                    logger.info("Photoroom: scene generated ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"Photoroom error {resp.status}: {error}")
                    return None

    except Exception as e:
        logger.error(f"Photoroom API failed: {e}")
        return None


async def photoroom_remove_bg(source_path: str) -> Image.Image:
    """
    Photoroom Remove Background API (Basic план).
    Используется как fallback если scene generation недоступна.
    """
    api_key = os.getenv("PHOTOROOM_API_KEY", "")
    if not api_key:
        return await asyncio.to_thread(_remove_bg_local, source_path)

    try:
        with open(source_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field(
                "imageFile", image_data,
                filename="product.jpg",
                content_type="image/jpeg"
            )

            async with session.post(
                "https://image-api.photoroom.com/v1/segment",
                headers={"x-api-key": api_key},
                data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.read()
                    img = Image.open(io.BytesIO(result)).convert("RGBA")
                    logger.info("Photoroom remove bg ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"Photoroom remove bg error {resp.status}: {error}")
                    return await asyncio.to_thread(_remove_bg_local, source_path)

    except Exception as e:
        logger.error(f"Photoroom remove bg failed: {e}")
        return await asyncio.to_thread(_remove_bg_local, source_path)


# ═══════════════════════════════════════════════
# REMOVE.BG FALLBACK
# ═══════════════════════════════════════════════

async def remove_background_api(source_path: str) -> Image.Image:
    """
    Пробует Photoroom сначала, потом remove.bg, потом локальный rembg.
    """
    # Сначала Photoroom
    photoroom_key = os.getenv("PHOTOROOM_API_KEY", "")
    if photoroom_key:
        result = await photoroom_remove_bg(source_path)
        if result:
            return result

    # Потом remove.bg
    removebg_key = os.getenv("REMOVEBG_API_KEY", "")
    if removebg_key:
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
                    headers={"X-Api-Key": removebg_key},
                    data=data
                ) as resp:
                    if resp.status == 200:
                        result_data = await resp.read()
                        img = Image.open(io.BytesIO(result_data)).convert("RGBA")
                        logger.info("remove.bg ✅")
                        return img
        except Exception as e:
            logger.error(f"remove.bg failed: {e}")

    return await asyncio.to_thread(_remove_bg_local, source_path)


def _remove_bg_local(source_path: str) -> Image.Image:
    try:
        from rembg import remove
        with open(source_path, "rb") as f:
            result = remove(f.read())
        return Image.open(io.BytesIO(result)).convert("RGBA")
    except Exception as e:
        logger.error(f"rembg failed: {e}")
        return Image.open(source_path).convert("RGBA")


# ═══════════════════════════════════════════════
# ГЕНЕРАЦИЯ ФОНА (DALL-E)
# ═══════════════════════════════════════════════

async def generate_background(bg_prompt: str, layout: str = "A") -> str:
    """Генерирует фон через DALL-E 3."""
    logger.info(f"Generating DALL-E background, layout={layout}")
    response = await client.images.generate(
        model="dall-e-3",
        prompt=bg_prompt,
        size="1024x1792",
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


# ═══════════════════════════════════════════════
# COMPOSITE — наложение продукта на фон
# ═══════════════════════════════════════════════

def _composite(bg: Image.Image, obj: Image.Image, layout: str = "A") -> Image.Image:
    """Накладывает вырезанный продукт на фон с тенью."""
    W, H = CANVAS_SIZE
    bg = bg.resize((W, H), Image.LANCZOS)

    if layout == "C":
        max_obj_w = int(W * 0.50)
        max_obj_h = int(H * 0.45)
    else:
        max_obj_w = int(W * 0.80)
        max_obj_h = int(H * 0.45)

    ratio = obj.width / obj.height
    if obj.width / max_obj_w > obj.height / max_obj_h:
        new_w = max_obj_w; new_h = int(max_obj_w / ratio)
    else:
        new_h = max_obj_h; new_w = int(max_obj_h * ratio)

    obj_resized = obj.resize((new_w, new_h), Image.LANCZOS)

    if layout == "A":
        ox = (W - new_w) // 2; oy = int(H * 0.55) - new_h // 2
    elif layout == "B":
        ox = (W - new_w) // 2; oy = int(H * 0.70) - new_h // 2
    elif layout == "C":
        ox = int(W * 0.50); oy = int(H * 0.55) - new_h // 2
    else:
        ox = (W - new_w) // 2; oy = int(H * 0.55) - new_h // 2

    # Тень
    sh_h = max(int(new_h * 0.04), 20)
    shadow = Image.new("RGBA", (new_w, sh_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([new_w//6, 0, new_w*5//6, sh_h], fill=(0, 0, 0, 50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))

    result = bg.convert("RGBA")
    result.paste(shadow, (ox, oy + new_h - sh_h // 2), shadow)
    result.paste(obj_resized, (ox, oy), obj_resized)
    return ImageEnhance.Contrast(result.convert("RGB")).enhance(1.05)


# ═══════════════════════════════════════════════
# ОСНОВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════

async def transform_image(source_path: str,
                          bg_prompt: str,
                          layout: str = "A",
                          ad_text: str = "") -> str:
    """
    Главная функция обработки изображения.

    Если есть PHOTOROOM_API_KEY с Plus планом:
      → Photoroom генерирует сцену сразу (продукт + фон + тени)

    Если только Basic Photoroom или нет ключа:
      → remove.bg + DALL-E + Pillow composite
    """
    logger.info(f"transform_image: layout={layout}, source={source_path}")
    out_dir = os.path.dirname(source_path)

    try:
        photoroom_key = os.getenv("PHOTOROOM_API_KEY", "")

        if photoroom_key:
            # ── PHOTOROOM PLUS: органичная сцена одним вызовом ──
            logger.info("Using Photoroom scene generation")
            scene_img = await photoroom_generate_scene(source_path, bg_prompt)

            if scene_img:
                # Ресайз до нашего canvas
                scene_img = scene_img.convert("RGB")
                scene_img = scene_img.resize(CANVAS_SIZE, Image.LANCZOS)
                out_path = os.path.join(out_dir, f"composite_{layout}.png")
                scene_img.save(out_path, "PNG", quality=95)
                logger.info(f"Photoroom scene saved: {out_path} ✅")
                return out_path
            else:
                logger.warning("Photoroom scene failed, falling back to DALL-E")

        # ── FALLBACK: remove.bg + DALL-E + Pillow ──
        logger.info("Using DALL-E + remove.bg composite")

        bg_url_coro = generate_background(bg_prompt, layout)
        obj_coro = remove_background_api(source_path)
        bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

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


async def generate_image_from_text(bg_prompt: str, layout: str = "A") -> str:
    """Только фон без продукта."""
    try:
        response = await client.images.generate(
            model="dall-e-3", prompt=bg_prompt,
            size="1024x1792", quality="standard", n=1
        )
        out_dir = "/tmp/creative_temp"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"bg_only_{layout}.png")
        await _download_image(response.data[0].url, out_path)
        img = Image.open(out_path).resize(CANVAS_SIZE, Image.LANCZOS)
        img.save(out_path, "PNG", quality=95)
        return out_path
    except Exception as e:
        logger.error(f"generate_image_from_text failed: {e}")
        return await _fallback(None, layout)


async def _fallback(source_path, layout):
    return await asyncio.to_thread(_fallback_sync, source_path, layout)


def _fallback_sync(source_path, layout):
    W, H = CANVAS_SIZE
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    c1, c2 = (245, 243, 238), (225, 222, 215)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(
            int(c1[0]+(c2[0]-c1[0])*t),
            int(c1[1]+(c2[1]-c1[1])*t),
            int(c1[2]+(c2[2]-c1[2])*t)
        ))
    if source_path and os.path.exists(source_path):
        src = Image.open(source_path).convert("RGB")
        ratio = src.width / src.height
        new_h = int(H * 0.45); new_w = min(int(new_h * ratio), W)
        new_h = int(new_w / ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        bg.paste(src, ((W-new_w)//2, int(H*0.55)-new_h//2))
    out_dir = "/tmp/creative_temp"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"composite_{layout}.png")
    bg.save(out_path, "PNG", quality=95)
    return out_path
