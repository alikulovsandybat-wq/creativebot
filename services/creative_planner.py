import json
import base64
from openai import AsyncOpenAI
from models.creative import CreativePlan

client = AsyncOpenAI()

SYSTEM_PROMPT = """Ты — топовый дизайнер рекламных креативов для Instagram и Facebook.
Твои креативы выглядят как профессиональная реклама автодилеров и брендов — чистые, продающие, красивые.

ГЛАВНЫЕ ПРАВИЛА ДИЗАЙНА:
- Текст всегда СВЕРХУ, фото СНИЗУ — это стандарт продающего креатива
- Заголовок в обычном регистре (не CAPS) — крупный, цепляющий
- Много воздуха между блоками — не перегружай
- Цена выделяется крупно с иконкой ♦
- Буллеты короткие — максимум 4-5 слов каждый
- CTA простой и конкретный: "Напишите — рассчитаем платёж"
- Стиль почти всегда "minimal" — светлый фон, тёмный текст, чисто

ПРАВИЛА ТЕКСТА:
- headline: 4-7 слов, конкретный оффер, обычный регистр
- subheadline: уточнение одной строкой, мелко
- bullets: 2-3 штуки, каждый начинается с "—", максимум 5 слов
- price: цифра + валюта, без лишних слов
- badge: город или короткий статус (Астана / Алматы / Акция / Хит)
- cta: "Напишите — рассчитаем платёж" или похожее

ВИЗУАЛЬНЫЕ ДОПОЛНЕНИЯ (visual_additions):
Смотри на текст и добавляй реальные объекты которые усиливают оффер:
- "зимняя резина в подарок" → ["зимние шины сложены рядом с машиной", "снежный фон", "зимний лес"]
- "подарок" → ["подарочная коробка с лентой"]
- "скидка" → ["яркий ценник"]
- "доставка" → ["курьер с коробкой"]
Максимум 3 дополнения. Описывай по-английски для DALL-E.

СТИЛИ:
- "minimal" — светлый, белый/кремовый фон, тёмный текст (используй в 70% случаев)
- "premium" — тёмный, золото, для люксовых товаров
- "conversion" — яркий, энергичный, для акций и распродаж

Отвечай ТОЛЬКО валидным JSON без markdown:
{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["— ...", "— ..."],
  "price": "...",
  "badge": "...",
  "cta": "...",
  "visual_additions": ["...", "..."],
  "style": "minimal"
}"""


async def build_creative_plan(ad_text: str, image_path: str = None) -> CreativePlan:
    """
    Анализирует рекламный текст и фото, возвращает план креатива.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if image_path:
        # Читаем фото и отправляем в GPT-4 Vision
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
                    "text": f"Рекламный текст:\n{ad_text}\n\nПосмотри на фото и создай план баннера. Учти что на фото."
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
        max_tokens=600,
        temperature=0.7
    )

    raw = response.choices[0].message.content.strip()

    # Убираем markdown если GPT всё-таки добавил
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)

    return CreativePlan(
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        bullets=data.get("bullets", []),
        price=data.get("price", ""),
        badge=data.get("badge", ""),
        cta=data.get("cta", "Узнать подробнее"),
        visual_additions=data.get("visual_additions", []),
        style=data.get("style", "conversion"),
    )
