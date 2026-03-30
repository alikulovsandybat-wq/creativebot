import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# Gemini рекомендация: поверхность с тенями, не "пустой фон"
PHOTO_SUFFIX = (
    "Commercial product photography background. "
    "The image must feature a solid surface in the lower half "
    "(floor / table / wooden pallet / platform) "
    "with realistic contact shadows and ambient occlusion "
    "where a heavy object would sit. "
    "Surface has subtle realistic texture to ground the object. "
    "Center-bottom = product placement zone with soft shadow catching area. "
    "Sharp focus throughout, 8k, photorealistic, Canon EOS R5, f/8. "
    "NO people, NO hands, NO text, NO logos. "
    "NOT cartoon, NOT CGI. Square 1:1."
)

SYSTEM_PROMPT = """Ты — топовый арт-директор рекламных креативов для Instagram и Facebook.

ЗАДАЧА: из рекламного текста создать структуру баннера + три РАЗНЫХ фона.

═══ ПРАВИЛА ТЕКСТА ═══
- headline: цепляющий, обычный регистр, 4-7 слов, конкретный оффер
- subheadline: уточнение одной строкой
- bullets: ровно 3 штуки, начинаются с "—", максимум 5 слов каждый
- price: только цифра + валюта (пример: "24 000 000 ₸")
- badge: город ИЛИ статус (Астана / Алматы / Акция / Хит / Новинка)
- cta: конкретный призыв (Напишите нам / Узнать цену / Скачать каталог)

═══ ТРИ ВАРИАНТА ФОНА ═══

ГЛАВНЫЕ ЗАКОНЫ (для всех трёх вариантов):
1. КОНТРАСТ: светлый фон для тёмного продукта, тёмный/нейтральный для светлого.
2. ПОСАДОЧНАЯ ПЛОЩАДКА: всегда описывай конкретную поверхность на которой стоит/лежит продукт.
   Используй фразы: "wooden pallet in center", "white floor surface", "marble platform".
3. ТЕНИ: добавляй "soft contact shadows", "ambient occlusion shadows on surface" — это приземляет объект.
4. ПРОСТОТА: максимум 2-3 элемента фона. Не перегружай.
5. УСИЛИТЕЛИ: добавляй детали из текста оффера (шины → стопка шин, доставка → коробки).

bg_minimal — ЧИСТЫЙ СТУДИЙНЫЙ ФОН:
Нейтральный фон с чистой поверхностью. Описывай ТОЛЬКО фон и поверхность.
Примеры:
- Для авто/запчастей: "pure white seamless studio background, clean white polished floor with soft shadow catching area in center, subtle floor reflection, gradient white to light grey"
- Для цветов: "white wooden table surface with soft contact shadows in center, white wall background, soft natural window light"
- Для одежды: "light grey seamless studio backdrop, smooth surface with ambient occlusion in center, bright even lighting"
- Универсально: "pure white gradient studio background, polished floor surface with realistic shadow zone in center"

bg_conversion — КОНТЕКСТНАЯ СЦЕНА:
Реалистичная сцена которая усиливает оффер. Описывай окружение + посадочную площадку.
Примеры:
- Запчасти + доставка за 1 день: "professional warehouse interior, wooden pallet in center of frame with soft shadows underneath, cardboard boxes on metal shelves in background, bright LED industrial ceiling lighting, concrete floor"
- Авто + зимняя резина: "snowy road cleared spot in center ready for vehicle, soft shadows on snow surface, stack of 4 winter tires on the right, mountain landscape in background, overcast winter light"
- Авто без акций: "modern car showroom, clean polished white floor with reflection and shadow zone in center, glass walls in background, professional bright lighting"
- Цветы + сертификат: "rustic wooden table with shadow catching area in center, elegant gift certificate card on the left, soft window light, blurred garden background"
- Одежда: "bright minimalist boutique, clean wooden shelf with soft shadows in center, clothing racks in background, warm lighting"

bg_premium — СТАТУСНЫЙ ASPIRATIONAL ФОН:
НЕ тёмная студия. Величественная сцена + посадочная площадка в центре.
Определи нишу и создай её aspirational мир:
- Авто/запчасти: "dramatic mountain road, cleared flat spot in center with realistic asphalt surface and soft shadows, rocky peaks in background, golden hour sunlight"
- Одежда: "luxury marble boutique, marble platform in center with soft ambient shadows, gold accents on walls, crystal chandelier, bright elegant lighting"
- Салон красоты: "luxurious salon, marble platform in center with shadow zone, gold-framed mirrors, crystal chandelier, bright elegant lighting"
- Цветы: "luxury penthouse, glass table surface in center with shadow catching area, floor-to-ceiling windows with city view, bright natural light"
- Универсально: aspirational lifestyle сцена ниши + чёткая посадочная площадка в центре с тенями

ЗАПРЕТЫ:
- НЕ упоминай конкретный продукт в описании фона (не пиши "bumper", "car", "pot" — только фон)
- НЕ делай фон полностью пустым без текстуры поверхности
- НЕ добавляй людей, руки, лица
- НЕ добавляй текст и логотипы

Описывай фоны НА АНГЛИЙСКОМ, 25-35 слов, конкретно.

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
                        f"Посмотри на фото продукта. Определи его цвет и тон. "
                        f"Создай план баннера. В описаниях фонов обеспечь КОНТРАСТ "
                        f"с цветом продукта и опиши конкретную посадочную поверхность."
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
        temperature=0.5
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
            "bg_minimal": "pure white seamless studio background, polished floor with soft shadow zone in center",
            "bg_conversion": "professional warehouse, wooden pallet in center with contact shadows, boxes on shelves",
            "bg_premium": "dramatic landscape, flat cleared surface in center with ambient shadows, golden hour light"
        }

    # Gemini рекомендация: добавляем тени принудительно в каждый промпт
    def enrich(scene_desc: str) -> str:
        return (
            f"{scene_desc}. "
            f"Solid ground with realistic ambient occlusion shadows in center, "
            f"professional lighting setup for product placement. "
            f"{PHOTO_SUFFIX}"
        )

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
        data.get("bg_minimal", "pure white studio background, polished floor with shadow zone in center")
    )
    plan.bg_conversion = enrich(
        data.get("bg_conversion", "warehouse interior, wooden pallet in center with contact shadows")
    )
    plan.bg_premium = enrich(
        data.get("bg_premium", "aspirational lifestyle scene, flat surface in center with ambient shadows")
    )

    return plan
