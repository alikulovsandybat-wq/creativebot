import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# Суффикс фотостиля — добавляется к каждому промпту фона
PHOTO_SUFFIX = (
    "photorealistic advertising photo, shot on Canon EOS R5, 85mm lens, "
    "professional studio lighting tailored to the product, sharp focus, "
    "commercial photography style, "
    "NO cartoon, NO CGI render, NO illustration, NO anime, NO painting, "
    "NO cluttered background, NO people. "
    "Clean area at top 40% of image for text overlay. "
    "NO text, NO words, NO letters in the image itself. "
    "1:1 square format."
)

SYSTEM_PROMPT = """Ты — топовый арт-директор рекламных креативов для Instagram и Facebook.

ЗАДАЧА: из рекламного текста создать структуру баннера + три РАЗНЫХ целостных композиции.

═══ ПРАВИЛА ТЕКСТА ═══
- headline: цепляющий, обычный регистр, 4-7 слов, конкретный оффер
- subheadline: уточнение одной строкой
- bullets: ровно 3 штуки, начинаются с "—", максимум 5 слов каждый
- price: только цифра + валюта (пример: "24 000 000 ₸")
- badge: город ИЛИ статус (Астана / Алматы / Акция / Хит / Новинка)
- cta: конкретный призыв (Напишите нам / Узнать цену / Скачать каталог)

═══ ТРИ ВАРИАНТА ФОНА ═══

Создавай мизансцену где продукт является ГЛАВНЫМ ГЕРОЕМ сцены.
Продукт должен быть естественно интегрирован — с правильными тенями и освещением.
Добавляй УСИЛИТЕЛИ КОНТЕКСТА из текста оффера:

УСИЛИТЕЛИ (примеры):
- "зимняя резина / шины" → стопка зимних шин рядом, снег на земле
- "подарок / сертификат" → красивая карточка сертификата или подарочная коробка рядом
- "доставка за 1 день" → коробки на паллете, чистый склад
- "запчасти" → детали аккуратно разложены, профессиональный бокс
- "8 марта / весна" → весенние цветы, пастельные тона
- "кредит / рассрочка" → нейтральная финансовая атмосфера, современный офис
Если в тексте нет специфических деталей — просто чистая сцена ниши.

ВАРИАНТЫ:

bg_minimal: Светлый, чистый, скандинавский стиль.
Продукт крупным планом в белом/кремовом интерьере или на светлом фоне.
Фокус только на продукте, минимум деталей. Много воздуха.
Верхняя часть кадра — светлая чистая зона для текста.

bg_conversion: Контекстный, сторителлинг, динамичный.
Продукт в реалистичной сцене с усилителями контекста из оффера.
Яркий заливающий свет. Сцена рассказывает историю продукта.
Зона для текста вверху с лёгким светлым перекрытием.

bg_premium: Тёмный, драматичный, статусный.
Продукт как арт-объект на тёмном фоне (антрацит / чёрный).
Chiaroscuro освещение — резкие тени, акцентный свет на продукте.
Дорогие текстуры: мрамор, металл, тёмное дерево.
Верхняя зона кадра — тёмная для белого текста.

ВАЖНО:
- Описывай на АНГЛИЙСКОМ, 20-30 слов
- НЕТ людей в кадре
- НЕТ текста и логотипов в кадре
- Фон не должен перебивать продукт

Отвечай ТОЛЬКО валидным JSON без markdown:
{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["— ...", "— ...", "— ..."],
  "price": "...",
  "badge": "...",
  "cta": "...",
  "bg_minimal": "...",
  "bg_conversion": "...",
  "bg_premium": "..."
}"""


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
                        f"Посмотри на фото продукта и создай план баннера. "
                        f"Учти продукт при описании фонов."
                    )
                }
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": (
                f"Рекламный текст:\n{ad_text}\n\n"
                f"Создай план баннера с тремя подходящими фонами."
            )
        })

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=700,
        temperature=0.6
    )

    raw = response.choices[0].message.content.strip()

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
            "bullets": ["— Высокое качество", "— Быстрая доставка", "— Лучшая цена"],
            "price": "",
            "badge": "Акция",
            "cta": "Напишите нам",
            "bg_minimal": "clean bright studio, white background, product as hero, natural light",
            "bg_conversion": "product in context scene, warm lighting, lifestyle atmosphere",
            "bg_premium": "product on dark elegant background, dramatic spotlight, luxury feel"
        }

    def enrich(scene_desc: str) -> str:
        return f"{scene_desc}. {PHOTO_SUFFIX}"

    plan = CreativePlan(
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        bullets=data.get("bullets", []),
        price=data.get("price", ""),
        badge=data.get("badge", ""),
        cta=data.get("cta", "Узнать подробнее"),
        style="minimal",
    )

    plan.bg_minimal = enrich(
        data.get("bg_minimal", "clean bright studio, white background, natural light")
    )
    plan.bg_conversion = enrich(
        data.get("bg_conversion", "product in realistic context scene, warm lighting")
    )
    plan.bg_premium = enrich(
        data.get("bg_premium", "dark elegant background, dramatic spotlight, luxury")
    )

    return plan
