import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# Базовый стиль фотографии — применяется ко всем промптам
PHOTO_STYLE = (
    "shot on Canon EOS R5, 85mm lens, f/2.0 aperture, "
    "studio strobe lighting with softbox, sharp crisp focus, "
    "professional commercial photo shoot, editorial advertising style, "
    "vivid natural colors, photorealistic, "
    "NOT cartoon, NOT anime, NOT illustration, NOT CGI, NOT 3D render, "
    "NOT AI generated look, NOT painting"
)

SYSTEM_PROMPT = f"""Ты — топовый арт-директор рекламных креативов.
Твоя задача: из рекламного текста создать структуру баннера И три разных визуальных сцены.

ГЛАВНЫЕ ПРАВИЛА ТЕКСТА:
- headline: цепляющий, обычный регистр, 4-7 слов
- subheadline: уточнение одной строкой
- bullets: 2-3 штуки, начинаются с "—", 3-5 слов каждый
- price: если есть в тексте
- badge: город или статус (Астана / Акция / Новинка)
- cta: конкретный призыв

ПРАВИЛА ДЛЯ ТРЁХ ВИЗУАЛЬНЫХ СЦЕН:
Создай три РАЗНЫХ сцены основываясь на СМЫСЛЕ рекламного текста.
Каждая сцена — другая интерпретация того же оффера.

Важно:
- Читай текст внимательно. Если написано "зимняя резина" — добавь снег и шины. Если нет — не добавляй.
- Если написано "8 марта" — добавь весеннее настроение. Если нет — просто нейтральный фон.
- Фон должен усиливать смысл оффера, а не противоречить ему.
- Все три сцены фотореалистичные, не мультяшные, студийный или lifestyle стиль.

Стили:
- "minimal": чистый, светлый, воздушный — студия или минималистичный интерьер
- "conversion": динамичный, яркий, энергичный — активная lifestyle сцена
- "premium": статусный, элегантный, дорогой — премиальный интерьер или драматическая сцена

Отвечай ТОЛЬКО валидным JSON без markdown:
{{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["— ...", "— ...", "— ..."],
  "price": "...",
  "badge": "...",
  "cta": "...",
  "bg_minimal": "English description of minimal style background scene, max 30 words",
  "bg_conversion": "English description of conversion style background scene, max 30 words",
  "bg_premium": "English description of premium style background scene, max 30 words"
}}"""


async def build_creative_plan(ad_text: str,
                               image_path: str = None) -> CreativePlan:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if image_path:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        messages.append({
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
                        f"Рекламный текст:\n{ad_text}\n\n"
                        f"Посмотри на фото и создай план баннера с тремя разными сценами."
                    )
                }
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": (
                f"Рекламный текст:\n{ad_text}\n\n"
                f"Создай план баннера с тремя разными сценами."
            )
        })

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=700,
        temperature=0.7
    )

    raw = response.choices[0].message.content.strip()

    # Чистим от markdown
    if "```" in raw:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1:
            raw = raw[start:end]
    if not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1:
            raw = raw[start:end]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed, using fallback")
        data = {
            "headline": ad_text[:40],
            "subheadline": "",
            "bullets": [],
            "price": "",
            "badge": "Акция",
            "cta": "Напишите нам",
            "bg_minimal": "clean bright studio, white background, natural light",
            "bg_conversion": "modern interior, bright colors, lifestyle",
            "bg_premium": "luxury dark studio, dramatic lighting, elegant"
        }

    # Добавляем фотостиль к каждому промпту
    def enrich_prompt(scene_desc: str) -> str:
        return (
            f"{scene_desc}. "
            f"{PHOTO_STYLE}. "
            f"Square format. Bottom area slightly darker for text overlay. "
            f"NO text, NO words, NO letters in image."
        )

    plan = CreativePlan(
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        bullets=data.get("bullets", []),
        price=data.get("price", ""),
        badge=data.get("badge", ""),
        cta=data.get("cta", "Узнать подробнее"),
        style="minimal",  # дефолт, будет переопределён по стилю
    )

    # Три разных промпта для трёх стилей
    plan.bg_minimal = enrich_prompt(data.get("bg_minimal", "clean bright studio"))
    plan.bg_conversion = enrich_prompt(data.get("bg_conversion", "bright modern scene"))
    plan.bg_premium = enrich_prompt(data.get("bg_premium", "luxury elegant studio"))

    return plan
