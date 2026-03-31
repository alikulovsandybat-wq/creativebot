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

# Ниши где Photoroom лучше — органичная сцена с тенями
PHOTOROOM_NICHES = ["auto", "auto_parts", "tech", "home", "food", "health", "medical"]
# Ниши где DALL-E лучше — красивый градиентный фон
DALLE_NICHES = ["beauty", "flowers", "perfume", "fashion", "kids",
                "psychology", "legal", "education", "kids_education",
                "photo", "travel", "realestate", "universal"]


# ═══════════════════════════════════════════════
# PHOTOROOM API
# ═══════════════════════════════════════════════

async def photoroom_generate_scene(source_path: str, scene_prompt: str) -> Image.Image | None:
    """
    Photoroom Image Editing API v2 (Pro план).
    Вырезает продукт + генерирует сцену + добавляет тени.
    """
    api_key = os.getenv("PHOTOROOM_API_KEY", "")
    if not api_key:
        return None

    try:
        with open(source_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("imageFile", image_data,
                           filename="product.jpg", content_type="image/jpeg")
            form.add_field("background.prompt", scene_prompt)
            form.add_field("shadow.mode", "ai.soft")
            form.add_field("outputFormat", "png")

            async with session.post(
                "https://image-api.photoroom.com/v2/edit",
                headers={"x-api-key": api_key, "Accept": "image/png"},
                data=form
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    logger.info("Photoroom scene generated ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"Photoroom scene error {resp.status}: {error}")
                    return None

    except Exception as e:
        logger.error(f"Photoroom scene failed: {e}")
        return None


async def photoroom_remove_bg(source_path: str) -> Image.Image | None:
    """Photoroom Remove Background (работает на всех планах)."""
    api_key = os.getenv("PHOTOROOM_API_KEY", "")
    if not api_key:
        return None

    try:
        with open(source_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("imageFile", image_data,
                           filename="product.jpg", content_type="image/jpeg")

            async with session.post(
                "https://image-api.photoroom.com/v1/segment",
                headers={"x-api-key": api_key, "Accept": "image/png"},
                data=form
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    logger.info("Photoroom remove bg ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"Photoroom remove bg error {resp.status}: {error}")
                    return None

    except Exception as e:
        logger.error(f"Photoroom remove bg failed: {e}")
        return None


# ═══════════════════════════════════════════════
# REMOVE BACKGROUND — умный fallback цепочка
# ═══════════════════════════════════════════════

async def remove_background_api(source_path: str) -> Image.Image:
    """Photoroom → remove.bg → rembg локальный."""

    # 1. Photoroom
    result = await photoroom_remove_bg(source_path)
    if result:
        return result

    # 2. remove.bg
    removebg_key = os.getenv("REMOVEBG_API_KEY", "")
    if removebg_key:
        try:
            with open(source_path, "rb") as f:
                image_data = f.read()
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("image_file", image_data,
                               filename="image.jpg", content_type="image/jpeg")
                form.add_field("size", "auto")
                async with session.post(
                    "https://api.remove.bg/v1.0/removebg",
                    headers={"X-Api-Key": removebg_key},
                    data=form
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        logger.info("remove.bg ✅")
                        return img
        except Exception as e:
            logger.error(f"remove.bg failed: {e}")

    # 3. Локальный rembg
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
# DALL-E ФОН
# ═══════════════════════════════════════════════

async def generate_background(bg_prompt: str, layout: str = "A") -> str:
    logger.info(f"Generating DALL-E background layout={layout}")
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
# COVER FIT — умный ресайз без полос
# ═══════════════════════════════════════════════

def _cover_fit(img: Image.Image, target_size: tuple) -> Image.Image:
    """Заполняет canvas без искажений, обрезает по центру."""
    tw, th = target_size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


# ═══════════════════════════════════════════════
# COMPOSITE — Pillow наложение
# ═══════════════════════════════════════════════

def _composite(bg: Image.Image, obj: Image.Image, layout: str = "A") -> Image.Image:
    W, H = CANVAS_SIZE
    bg = bg.resize((W, H), Image.LANCZOS)

    max_obj_w = int(W * 0.50) if layout == "C" else int(W * 0.80)
    max_obj_h = int(H * 0.45)

    ratio = obj.width / obj.height
    if obj.width / max_obj_w > obj.height / max_obj_h:
        new_w = max_obj_w; new_h = int(max_obj_w / ratio)
    else:
        new_h = max_obj_h; new_w = int(max_obj_h * ratio)

    obj_r = obj.resize((new_w, new_h), Image.LANCZOS)

    if layout == "A":   ox = (W-new_w)//2; oy = int(H*0.55) - new_h//2
    elif layout == "B": ox = (W-new_w)//2; oy = int(H*0.70) - new_h//2
    elif layout == "C": ox = int(W*0.50);  oy = int(H*0.55) - new_h//2
    else:               ox = (W-new_w)//2; oy = int(H*0.55) - new_h//2

    sh_h = max(int(new_h*0.04), 20)
    shadow = Image.new("RGBA", (new_w, sh_h), (0,0,0,0))
    ImageDraw.Draw(shadow).ellipse([new_w//6, 0, new_w*5//6, sh_h], fill=(0,0,0,50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))

    result = bg.convert("RGBA")
    result.paste(shadow, (ox, oy + new_h - sh_h//2), shadow)
    result.paste(obj_r, (ox, oy), obj_r)
    return ImageEnhance.Contrast(result.convert("RGB")).enhance(1.05)


# ═══════════════════════════════════════════════
# ОСНОВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════

async def transform_image(source_path: str,
                          bg_prompt: str,
                          layout: str = "A",
                          ad_text: str = "",
                          niche: str = "universal") -> str:
    """
    Умно выбирает инструмент по нише:
    - Photoroom → авто, техника, еда, дом (органичная сцена с тенями)
    - DALL-E + remove bg → красота, цветы, парфюм (красивый фон)
    """
    logger.info(f"transform_image: niche={niche}, layout={layout}")
    out_dir = os.path.dirname(source_path)
    if not out_dir:
        out_dir = "/tmp/creative_temp"
    os.makedirs(out_dir, exist_ok=True)

    photoroom_key = os.getenv("PHOTOROOM_API_KEY", "")
    use_photoroom = niche in PHOTOROOM_NICHES and bool(photoroom_key)

    try:
        if use_photoroom:
            # ── PHOTOROOM: органичная сцена ──
            logger.info(f"→ Photoroom scene (niche={niche})")
            scene_img = await photoroom_generate_scene(source_path, bg_prompt)
            if scene_img:
                result = _cover_fit(scene_img.convert("RGB"), CANVAS_SIZE)
                out_path = os.path.join(out_dir, f"composite_{layout}.png")
                result.save(out_path, "PNG", quality=95)
                logger.info(f"Photoroom scene saved ✅")
                return out_path
            logger.warning("Photoroom scene failed → DALL-E fallback")

        # ── DALL-E + remove bg ──
        logger.info(f"→ DALL-E composite (niche={niche})")
        bg_url_coro = generate_background(bg_prompt, layout)
        obj_coro = remove_background_api(source_path)
        bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

        bg_path = os.path.join(out_dir, f"bg_{layout}.png")
        await _download_image(bg_url, bg_path)
        bg_img = Image.open(bg_path).convert("RGB")

        result = _composite(bg_img, obj_img, layout)
        out_path = os.path.join(out_dir, f"composite_{layout}.png")
        result.save(out_path, "PNG", quality=95)
        logger.info(f"DALL-E composite saved ✅")
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
        new_h = int(H*0.45); new_w = min(int(new_h*ratio), W)
        new_h = int(new_w/ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        bg.paste(src, ((W-new_w)//2, int(H*0.55)-new_h//2))
    out_dir = "/tmp/creative_temp"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"composite_{layout}.png")
    bg.save(out_path, "PNG", quality=95)
    return out_path
