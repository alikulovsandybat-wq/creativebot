import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

PHOTO_SUFFIX = (
    "commercial product advertising photo, Canon EOS R5, 50mm lens, f/8 aperture for maximum sharpness, "
    "ISO 100, professional lighting, TACK SHARP focus on entire product, "
    "NO motion blur, NO depth of field blur, NO bokeh, EVERYTHING in focus, "
    "clean crisp image, high resolution, photorealistic, NOT cartoon, NOT illustration, NOT 3D render. "
    "STRICT RULES: "
    "(1) Product MUST contrast clearly with background — dark product = light/bright background, light product = neutral background. "
    "(2) Product MUST be physically placed on a surface — on table, on pallet, on shelf, on floor — NEVER floating in air. "
    "(3) Background MUST support the product — simple and not distracting. "
    "(4) Top 40% of image = clean area for text overlay. "
    "(5) NO text, NO letters, NO logos, NO watermarks. "
    "(6) NO people, NO hands, NO faces. "
    "Square 1:1 format."
)

SYSTEM_PROMPT = """Ты — топовый арт-директор рекламных креативов для Instagram и Facebook.

ЗАДАЧА: из рекламного текста создать структуру баннера + три РАЗНЫХ фона под продукт.

═══ ПРАВИЛА ТЕКСТА ═══
- headline: цепляющий, обычный регистр, 4-7 слов, конкретный оффер
- subheadline: уточнение одной строкой  
- bullets: ровно 3 штуки, начинаются с "—", максимум 5 слов каждый
- price: только цифра + валюта (пример: "24 000 000 ₸")
- badge: город ИЛИ статус (Астана / Алматы / Акция / Хит / Новинка)
- cta: конкретный призыв (Напишите нам / Узнать цену / Скачать каталог)

═══ ТРИ ВАРИАНТА ФОНА ═══

ГЛАВНЫЕ ЗАКОНЫ (обязательны для ВСЕХ трёх вариантов):
1. КОНТРАСТ: тёмный продукт → светлый фон. Светлый продукт → тёмный/нейтральный фон. Никогда не смешивай похожие тона.
2. ПОЗИЦИОНИРОВАНИЕ: продукт должен на чём-то стоять или лежать (стол, паллета, полка, пол, стенд).
3. ПРОСТОТА: максимум 2-3 элемента на фоне. Фон не должен перебивать продукт.
4. УСИЛИТЕЛИ: добавляй детали из текста оффера (шины → стопка шин рядом, доставка → паллеты, сертификат → карточка).

ВАРИАНТЫ:

bg_minimal — ЧИСТЫЙ СТУДИЙНЫЙ ФОН:
Продукт на нейтральном фоне (белый / светло-серый / кремовый).
Никаких декораций — только ровный градиентный фон.
Как профессиональное фото для каталога.
Примеры:
- Бампер (тёмный): "black car bumper placed flat on white floor, pure white gradient studio background, clean catalog product shot"
- Машина (светлая): "silver SUV parked on white showroom floor, clean white background, soft even studio lighting"
- Цветы: "purple hydrangea pot placed on white wooden table, white wall background, bright airy natural light"
- Одежда: "folded clothing on light grey surface, white background, clean flat lay catalog style"

bg_conversion — КОНТЕКСТНАЯ СЦЕНА:
Продукт в реалистичном окружении которое УСИЛИВАЕТ оффер.
Добавь 1-2 контекстных элемента из текста рекламы.
Примеры:
- Бампер + доставка за 1 день: "black car bumper placed on wooden pallet, clean professional warehouse with cardboard boxes on metal shelves, bright industrial overhead lighting"
- Машина + зимняя резина в подарок: "silver SUV parked on snowy road, stack of 4 winter tires placed neatly next to car, overcast winter daylight, snow on ground"
- Машина без зимних акций: "silver SUV parked in clean modern showroom, glass walls, bright white professional lighting, polished floor reflection"
- Цветы + сертификат: "hydrangea pot on rustic wooden table, elegant white gift certificate card leaning against pot, bright room with soft window light"
- Одежда + распродажа: "neatly folded clothing on wooden shelf in bright minimalist boutique, clean interior, warm lighting"

bg_premium — СТАТУСНЫЙ ASPIRATIONAL ФОН:
НЕ тёмная студия. Премиум — это aspirational lifestyle конкретной ниши.
Создай сцену которая передаёт МЕЧТУ и СТАТУС владельца продукта.
Яркий или естественный свет — НЕ мрачно, а ВЕЛИЧЕСТВЕННО.

Правило: определи нишу продукта и создай её ПРЕМИАЛЬНЫЙ МИР:

АВТО / ЗАПЧАСТИ:
"SUV parked on dramatic mountain road with epic rocky peaks in background, golden hour sunlight, powerful and free atmosphere, cinematic wide shot"
"Car on coastal cliff road, ocean view, dramatic sunset sky, aspirational lifestyle"

НЕДВИЖИМОСТЬ:
"Luxurious white villa with infinity pool overlooking mountains, bright sunny day, lush greenery, aspirational lifestyle"

ОДЕЖДА / МОДА:
"Premium clothing displayed in luxury marble boutique, gold accents, crystal chandelier, high-end fashion store interior, bright elegant lighting"

САЛОН КРАСОТЫ / SPA:
"Luxurious beauty salon interior, gold-framed mirrors, plush velvet presidential chair, crystal chandelier, marble floors, bright elegant lighting"

ЮВЕЛИРКА:
"Jewelry piece on white silk fabric, surrounded by fresh white roses, soft bright natural light, luxurious flat lay"

ЦВЕТЫ / РАСТЕНИЯ:
"Elegant flower arrangement in luxury penthouse interior, floor-to-ceiling windows with city view, bright natural light, aspirational home"

ЕДА / РЕСТОРАН:
"Beautifully plated dish on white marble table, Michelin star restaurant interior, warm elegant lighting, luxury dining atmosphere"

ЭЛЕКТРОНИКА / ГАДЖЕТЫ:
"Premium device on glass surface reflecting city skyline at golden hour, aspirational tech lifestyle, bright modern penthouse background"

ДЛЯ ЛЮБОГО ДРУГОГО:
Создай aspirational сцену которая показывает жизнь ПОСЛЕ покупки этого продукта на высоком уровне.

ВАЖНО для premium: яркий или золотой час освещение, НЕ тёмный фон, величественно и вдохновляюще.

ЗАПРЕТЫ (никогда не делай этого):
- НЕ размещай тёмный продукт на тёмном фоне
- НЕ делай продукт висящим в воздухе
- НЕ добавляй людей, руки, лица
- НЕ перегружай фон деталями
- НЕ добавляй текст, логотипы, надписи на фон

Описывай фоны НА АНГЛИЙСКОМ, 20-30 слов, конкретно и точно.

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
                        f"Создай план баннера. В описаниях фонов учти цвет продукта "
                        f"чтобы обеспечить КОНТРАСТ."
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
            "bg_minimal": "product on white floor, pure white gradient studio background, catalog style",
            "bg_conversion": "product placed on wooden pallet, clean warehouse background, industrial lighting",
            "bg_premium": "product on dark concrete floor, single spotlight from above, dark anthracite background"
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
        data.get("bg_minimal", "product on white floor, pure white studio background")
    )
    plan.bg_conversion = enrich(
        data.get("bg_conversion", "product on wooden pallet, clean warehouse background")
    )
    plan.bg_premium = enrich(
        data.get("bg_premium", "product on dark floor, single spotlight, dark background")
    )

    return plan
