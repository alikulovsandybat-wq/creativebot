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

BACKGROUND_PROMPTS = {
    "premium": (
        "Empty luxury studio background, elegant focused spotlight, "
        "dark grey and black tones, soft gradient floor reflection, "
        "sophisticated premium atmosphere, hyperrealistic photography background, "
        "NOT gloomy, NOT horror, NO objects, NO people, NO text, just empty background, "
        "shot on Canon EOS R5, studio strobe lighting, photorealistic, NOT CGI"
    ),
    "conversion": (
        "Empty bright modern interior or outdoor scene, warm natural sunlight, "
        "vibrant clean colors, fresh modern environment, bright and cheerful, "
        "hyperrealistic photography, NO objects, NO people, NO text, just empty background, "
        "shot on Canon EOS R5, natural light, photorealistic, NOT CGI"
    ),
    "minimal": (
        "Empty clean bright studio, soft natural window light through large windows, "
        "light cream or white wall, clean light wooden surface, "
        "airy minimalist Scandinavian atmosphere, sunny and fresh, "
        "hyperrealistic photography background, NOT dark, NOT moody, "
        "NO objects, NO people, NO text, just empty background, "
        "shot on Canon EOS R5, softbox lighting, photorealistic, NOT CGI"
    ),
}

DECORATION_HINTS = {
    "шин": "with winter tires stacked as gift on the side",
    "резин": "with winter tires stacked as gift on the side",
    "подарок": "with gift box with ribbon on the side",
    "сертификат": "with elegant gift certificate card nearby",
    "скидк": "with sale tag visible",
    "зим": "with light snow on the surface",
    "8 март": "with spring flowers and gift box nearby",
    "новый год": "with christmas decorations nearby",
}


def _get_decoration_hint(ad_text: str) -> str:
    if not ad_text:
        return ""
    text_lower = ad_text.lower()
    for keyword, hint in DECORATION_HINTS.items():
        if keyword in text_lower:
            return hint
    return ""


async def remove_background_api(source_path: str) -> Image.Image:
    """
    Убирает фон через remove.bg API.
    Качественное вырезание без нагрузки на сервер.
    """
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
                    logger.info("remove.bg: background removed successfully ✅")
                    return img
                else:
                    error = await resp.text()
                    logger.error(f"remove.bg error {resp.status}: {error}")
                    return await asyncio.to_thread(_remove_bg_local, source_path)

    except Exception as e:
        logger.error(f"remove.bg API failed: {e}")
        return await asyncio.to_thread(_remove_bg_local, source_path)


def _remove_bg_local(source_path: str) -> Image.Image:
    """Fallback — локальный rembg если API недоступен."""
    try:
        from rembg import remove
        with open(source_path, "rb") as f:
            result = remove(f.read())
        return Image.open(io.BytesIO(result)).convert("RGBA")
    except Exception as e:
        logger.error(f"rembg also failed: {e}")
        return Image.open(source_path).convert("RGBA")


async def _generate_background(style: str, subject_desc: str,
                                decoration_hint: str) -> str:
    bg_prompt = BACKGROUND_PROMPTS.get(style, BACKGROUND_PROMPTS["minimal"])
    if decoration_hint:
        bg_prompt = bg_prompt.replace("just empty background",
                                      f"just background, {decoration_hint}")
    if any(w in subject_desc.lower() for w in ["car", "auto", "vehicle"]):
        bg_prompt += " Wide showroom floor visible."
    elif any(w in subject_desc.lower() for w in ["flower", "plant", "bouquet"]):
        bg_prompt += " Garden shelf or wooden table visible."

    response = await client.images.generate(
        model="dall-e-3", prompt=bg_prompt,
        size="1024x1024", quality="standard", n=1
    )
    return response.data[0].url


async def _generate_background_from_prompt(base_prompt: str, style: str,
                                            decoration_hint: str = "") -> str:
    style_additions = {
        "premium": "dramatic lighting, dark elegant atmosphere, luxury feel",
        "conversion": "bright vibrant colors, energetic, eye-catching",
        "minimal": "soft natural light, clean minimal, airy",
    }
    style_add = style_additions.get(style, style_additions["minimal"])
    decoration = f", {decoration_hint}" if decoration_hint else ""

    full_prompt = (
        f"{base_prompt}, {style_add}{decoration}. "
        f"Square format 1:1. Bottom area slightly darker for text. "
        f"Hyperrealistic commercial photography, shot on Canon EOS R5. "
        f"NOT cartoon, NOT CGI. NO text, NO words, NO letters."
    )

    logger.info(f"BG prompt ({style}): {full_prompt[:100]}...")

    response = await client.images.generate(
        model="dall-e-3", prompt=full_prompt,
        size="1024x1024", quality="standard", n=1
    )
    return response.data[0].url


async def _download_image(url: str, save_path: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, "wb") as f:
                    f.write(await resp.read())


def _composite(bg: Image.Image, obj: Image.Image,
               canvas_size: tuple) -> Image.Image:
    W, H = canvas_size
    bg = bg.resize((W, H), Image.LANCZOS)

    max_obj_h = int(H * 0.62)
    max_obj_w = int(W * 0.85)
    ratio = obj.width / obj.height
    if obj.width / max_obj_w > obj.height / max_obj_h:
        new_w, new_h = max_obj_w, int(max_obj_w / ratio)
    else:
        new_h, new_w = max_obj_h, int(max_obj_h * ratio)

    obj_resized = obj.resize((new_w, new_h), Image.LANCZOS)

    # Тень под объект
    sh_h = max(int(new_h * 0.05), 15)
    shadow = Image.new("RGBA", (new_w, sh_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [new_w//6, 0, new_w*5//6, sh_h], fill=(0, 0, 0, 45)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))

    ox = (W - new_w) // 2
    oy = H - new_h - 30

    result = bg.convert("RGBA")
    result.paste(shadow, (ox, oy + new_h - sh_h // 2), shadow)
    result.paste(obj_resized, (ox, oy), obj_resized)
    return result.convert("RGB")


async def _analyze_subject(image_path: str) -> str:
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        response = await client.chat.completions.create(
            model="gpt-4o", max_tokens=30,
            messages=[{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_data}",
                               "detail": "low"}},
                {"type": "text",
                 "text": "In 5 words, what is the main product? English only."}
            ]}]
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "product"


async def transform_image(source_path: str, style: str,
                          canvas_size: tuple = (1080, 1080),
                          ad_text: str = "") -> str:
    logger.info(f"Compositing: {source_path}, style: {style}")
    try:
        subject_desc = await _analyze_subject(source_path)
        decoration_hint = _get_decoration_hint(ad_text)

        # Параллельно: remove.bg + генерация фона
        bg_url_coro = _generate_background(style, subject_desc, decoration_hint)
        obj_coro = remove_background_api(source_path)
        bg_url, obj_img = await asyncio.gather(bg_url_coro, obj_coro)

        out_dir = os.path.dirname(source_path)
        bg_path = os.path.join(out_dir, f"bg_{style}.png")
        await _download_image(bg_url, bg_path)
        bg_img = Image.open(bg_path).convert("RGB")

        result = _composite(bg_img, obj_img, canvas_size)
        result = ImageEnhance.Contrast(result).enhance(1.05)

        out_path = os.path.join(out_dir, f"composite_{style}.png")
        result.save(out_path, "PNG", quality=95)
        return out_path

    except Exception as e:
        logger.error(f"transform_image failed: {e}", exc_info=True)
        return await _fallback(source_path, style, canvas_size)


async def generate_image_from_text(ad_text: str, style: str,
                                   canvas_size: tuple = (1080, 1080)) -> str:
    try:
        decoration = _get_decoration_hint(ad_text)
        bg_base = BACKGROUND_PROMPTS.get(style, BACKGROUND_PROMPTS["minimal"])

        resp = await client.chat.completions.create(
            model="gpt-4o", max_tokens=60,
            messages=[{"role": "user", "content": (
                f"In 15 words max, describe a hyperrealistic product for this ad "
                f"(English, no text in image): {ad_text}"
            )}]
        )
        product_desc = resp.choices[0].message.content.strip()

        prompt = (
            f"Hyperrealistic commercial photo: {product_desc}. "
            f"{decoration}. {bg_base}. Square format. "
            f"Bottom third darker. NO text, NO words."
        )
        img_resp = await client.images.generate(
            model="dall-e-3", prompt=prompt,
            size="1024x1024", quality="standard", n=1
        )
        out_path = f"/tmp/creative_temp/generated_{style}.png"
        os.makedirs("/tmp/creative_temp", exist_ok=True)
        await _download_image(img_resp.data[0].url, out_path)
        Image.open(out_path).resize(canvas_size, Image.LANCZOS).save(
            out_path, "PNG", quality=95)
        return out_path

    except Exception as e:
        logger.error(f"Text gen failed: {e}")
        return await _fallback(None, style, canvas_size)


async def _fallback(source_path, style, canvas_size):
    return await asyncio.to_thread(_fallback_sync, source_path, style, canvas_size)


def _fallback_sync(source_path, style, canvas_size):
    COLORS = {
        "premium": [(10, 10, 20), (30, 20, 50)],
        "conversion": [(15, 25, 50), (20, 40, 80)],
        "minimal": [(245, 243, 238), (225, 222, 215)],
    }
    W, H = canvas_size
    c1, c2 = COLORS.get(style, COLORS["minimal"])
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
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
        new_h = int(H * 0.6)
        new_w = min(int(new_h * ratio), W)
        new_h = int(new_w / ratio)
        src = src.resize((new_w, new_h), Image.LANCZOS)
        bg.paste(src, ((W-new_w)//2, H-new_h-30))
    out_dir = "/tmp/creative_temp"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"composite_{style}.png")
    bg.save(out_path, "PNG", quality=95)
    return out_path
