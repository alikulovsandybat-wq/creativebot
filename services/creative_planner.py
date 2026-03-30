import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# Визуальные профили по нишам — что генерировать для каждой
NICHE_VISUAL_PROFILES = {
    "beauty": {
        "keywords": ["салон", "красот", "маникюр", "педикюр", "брови", "ресниц", "массаж", "spa", "спа", "косметолог", "визажист"],
        "dalle_prompt": "Bright airy beauty salon interior, white marble surfaces, fresh pink and white flowers, soft natural window light, elegant mirrors, pastel pink and cream tones, clean commercial photography, bright and cheerful, NOT dark, NOT moody, NOT cinematic, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "minimal",
        "mood": "нежный, женственный, уходовый"
    },
    "flowers": {
        "keywords": ["цвет", "букет", "флорист", "растен", "сад", "горшоч"],
        "dalle_prompt": "Bright flower shop with beautiful fresh hydrangeas and roses, sunny natural daylight, white wooden surfaces, linen textures, spring botanical atmosphere, light and airy, clean lifestyle photography, NOT dark, NOT moody, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "minimal",
        "mood": "свежий, природный, живой"
    },
    "auto": {
        "keywords": ["авто", "машин", "автомобил", "кредит", "лизинг", "car", "dealer"],
        "dalle_prompt": "Sleek modern car showroom, clean polished white floor with reflections, bright professional studio lighting, white and grey elegant background, premium atmosphere, hyperrealistic commercial photography, bright and clean, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "premium",
        "mood": "статусный, мощный, современный"
    },
    "food": {
        "keywords": ["еда", "кафе", "ресторан", "доставк", "пицц", "суши", "бург", "вкусн", "food"],
        "dalle_prompt": "Beautiful food flat lay on bright wooden table, warm natural sunlight, fresh colorful ingredients, appetizing clean composition, bright and vibrant, professional food photography, NOT dark, NOT moody, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "conversion",
        "mood": "аппетитный, тёплый, уютный"
    },
    "clothes": {
        "keywords": ["одежд", "платье", "костюм", "футболк", "fashion", "стиль", "бренд", "коллекц"],
        "dalle_prompt": "Clean bright white fashion studio, soft natural daylight, minimal light grey backdrop, fresh and modern, professional fashion photography, bright and crisp, NOT dark, NOT cinematic, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "minimal",
        "mood": "стильный, чистый, современный"
    },
    "jewelry": {
        "keywords": ["ювелир", "золото", "серебро", "кольц", "серьг", "украшен", "брасл"],
        "dalle_prompt": "Luxury jewelry on soft dark velvet surface, elegant focused spotlight, gold and black tones, beautiful bokeh background, premium commercial photography, sophisticated NOT gloomy, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "premium",
        "mood": "люксовый, сияющий, дорогой"
    },
    "fitness": {
        "keywords": ["фитнес", "спорт", "трениров", "зал", "gym", "йога", "пилатес"],
        "dalle_prompt": "Modern gym interior with equipment, motivating atmosphere, dynamic lighting, clean and energetic space, professional fitness photography, hyperrealistic, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "conversion",
        "mood": "энергичный, мотивирующий, динамичный"
    },
    "realty": {
        "keywords": ["недвижим", "квартир", "дом", "жильё", "аренд", "продаж", "апартамент"],
        "dalle_prompt": "Luxurious modern apartment interior, large windows with city view, elegant furniture, warm evening lighting, premium real estate photography, hyperrealistic, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "premium",
        "mood": "статусный, уютный, просторный"
    },
    "education": {
        "keywords": ["курс", "обучен", "школ", "урок", "онлайн", "учёба", "навык"],
        "dalle_prompt": "Modern study environment, clean desk with laptop and notebooks, natural daylight, motivating atmosphere, professional educational photography, hyperrealistic, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
        "style": "conversion",
        "mood": "профессиональный, вдохновляющий, современный"
    },
}

DEFAULT_VISUAL = {
    "dalle_prompt": "Clean bright professional studio background, soft natural window light, minimal elegant white composition, airy and fresh, commercial photography, bright and clear, NOT dark, shot on Canon EOS R5, 85mm lens, f/2.0 aperture, studio strobe lighting with softbox, sharp crisp focus, professional commercial photo shoot, editorial style, 2024 advertising campaign, vivid natural colors, NOT AI generated look, NOT painting, NOT illustration, NOT CGI, NO text",
    "style": "minimal",
    "mood": "профессиональный, чистый"
}


def _detect_niche(text: str) -> dict:
    """Определяет нишу по ключевым словам в тексте."""
    text_lower = text.lower()
    for niche, profile in NICHE_VISUAL_PROFILES.items():
        for keyword in profile["keywords"]:
            if keyword in text_lower:
                return profile
    return DEFAULT_VISUAL


SYSTEM_PROMPT = """Ты — топовый арт-директор рекламных креативов.
Твоя задача: из любого, даже самого простого запроса создать структуру продающего баннера.

ГЛАВНЫЕ ПРАВИЛА:
- Текст СВЕРХУ, фото СНИЗУ
- Заголовок цепляющий, в обычном регистре, 4-7 слов
- Цена выделяется крупно
- Буллеты короткие — 3-5 слов каждый, начинаются с "—"
- CTA конкретный и простой
- Стиль: "minimal" по умолчанию (светлый, чистый)

ПРАВИЛА ПО СТИЛЯМ:
- "minimal" — светлый фон, тёмный текст (красота, цветы, мода, еда)
- "premium" — тёмный фон, золото (авто, ювелирка, люкс, недвижимость)
- "conversion" — яркий, энергичный (акции, скидки, фитнес, курсы)

Отвечай ТОЛЬКО валидным JSON без markdown:
{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["— ...", "— ...", "— ..."],
  "price": "...",
  "badge": "...",
  "cta": "...",
  "style": "minimal"
}"""


async def build_creative_plan(ad_text: str,
                               image_path: str = None) -> CreativePlan:
    """
    Строит план креатива.
    Также определяет визуальный профиль для DALL-E генерации фона.
    """
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
                    "text": f"Рекламный текст:\n{ad_text}\n\nПосмотри на фото и создай план баннера."
                }
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": f"Рекламный текст:\n{ad_text}\n\nСоздай план баннера."
        })

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=500,
        temperature=0.7
    )

    raw = response.choices[0].message.content.strip()

    # Чистим ответ от markdown
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
            "style": "minimal"
        }

    # Определяем визуальный профиль по нише
    visual_profile = _detect_niche(ad_text)

    plan = CreativePlan(
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        bullets=data.get("bullets", []),
        price=data.get("price", ""),
        badge=data.get("badge", ""),
        cta=data.get("cta", "Узнать подробнее"),
        style=data.get("style", visual_profile.get("style", "minimal")),
    )

    # Сохраняем визуальный промпт для DALL-E в план
    plan.dalle_bg_prompt = visual_profile.get("dalle_prompt", DEFAULT_VISUAL["dalle_prompt"])

    return plan
