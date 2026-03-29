import json
import base64
from openai import AsyncOpenAI
from models.creative import CreativePlan

client = AsyncOpenAI()

SYSTEM_PROMPT = """Ты — эксперт по рекламным креативам. 
Твоя задача: проанализировать рекламный текст (и фото если есть) и вернуть структуру баннера.

Правила:
- headline: короткий, цепляющий, 3-6 слов
- subheadline: уточнение, 1 строка
- bullets: 2-4 конкретных выгоды, каждая 2-5 слов
- price: цена если есть в тексте
- badge: короткий бейдж (АКЦИЯ / ХИТ / НОВИНКА / LIMITED и т.д.)
- cta: призыв к действию (Напишите нам / Узнать цену / Получить каталог)
- visual_additions: что визуально добавить к фото (например ["шины в подарок", "снежный фон", "подарочная лента"])
- style: выбери один стиль:
  * "premium" — тёмный, дорого, минимум текста
  * "conversion" — яркий CTA, буллеты, цена крупно
  * "minimal" — светлый, чистый, типографика главная

Отвечай ТОЛЬКО валидным JSON без markdown:
{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["...", "..."],
  "price": "...",
  "badge": "...",
  "cta": "...",
  "visual_additions": ["..."],
  "style": "conversion"
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
