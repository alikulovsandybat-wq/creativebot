import json
import base64
import logging
from openai import AsyncOpenAI
from models.creative import CreativePlan

logger = logging.getLogger(__name__)
client = AsyncOpenAI()

# ═══ СЛОВАРЬ ПРОМПТОВ ПО НИШАМ ═══
# Каждая ниша: layout_A, layout_B, layout_C
# A: заголовок сверху тёмная зона, продукт центр, CTA снизу
# B: большой заголовок сверху, продукт снизу-центр
# C: текст слева, продукт справа

NICHE_BACKGROUNDS = {
    "beauty": {
        "A": "Elegant beauty spa background. Soft sage green and cream white gradient. TOP 30%: slightly deeper sage tone for text overlay. CENTER: completely empty clean space for product. BOTTOM 20%: pale cream with rose petal scatter for CTA zone. Delicate water droplets, soft bokeh, botanical leaves on edges only. Photorealistic, 8k, Canon EOS R5, f/2.8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Luxury skincare background. Soft pink blush gradient top to bottom, warm peachy tones. TOP 40%: clear light pink zone for large bold title. CENTER-BOTTOM: subtle marble texture surface, clean platform for product. Delicate cream swirls, soft light flares on edges only. Photorealistic, 8k, Canon EOS R5, f/4. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Fresh natural skincare background. Aqua blue water ripple texture, crystal clear, cool mint tones. LEFT 40%: softer darker aqua zone for white text. RIGHT: brighter water surface, clean space for product. Subtle water splash hints at bottom corners. Photorealistic, 8k, Canon EOS R5, f/5.6. NO product, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "perfume": {
        "A": "Luxury perfume background. Deep warm amber and cognac brown gradient, golden light beam from top center. TOP 30%: rich dark amber zone for gold or white text. CENTER: completely empty elegant space for bottle. BOTTOM 20%: warmer tone with dried botanicals for CTA. Gold dust particles, liquid amber splash on side edges only. Photorealistic, 8k, Canon EOS R5, f/2.8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Premium fragrance background. Soft champagne gold and ivory gradient, ethereal misty atmosphere. TOP 40%: pale champagne zone for large title. CENTER-BOTTOM: polished reflective surface for bottle. Delicate white flower petals floating, golden bokeh lights. Photorealistic, 8k, Canon EOS R5, f/2.8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Aspirational perfume background. Deep violet purple fading to warm rose gold, moody romantic atmosphere. LEFT 40%: deeper violet zone for light text. RIGHT: warm rose gold zone, clear space for bottle. Scattered rose petals, gold dust, soft purple smoke on edges. Photorealistic, 8k, Canon EOS R5, f/2.8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "fashion": {
        "A": "Fashion boutique background. Warm ivory and soft taupe gradient, minimalist editorial aesthetic. TOP 30%: deeper warm beige for dark or white text. CENTER: completely empty neutral space for clothing. BOTTOM 20%: light cream with subtle linen texture for CTA. Minimal geometric shadow lines, soft natural light. Photorealistic, 8k, Canon EOS R5, f/8. NO clothing, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Luxury fashion background. Pure white to soft pearl gradient, high-key editorial style. TOP 40%: bright white clean zone for large fashion title. CENTER-BOTTOM: subtle shadow casting surface, polished floor. Minimal diagonal light rays, soft shadow geometry. Photorealistic, 8k, Canon EOS R5, f/11. NO clothing, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Contemporary fashion background. Dusty rose and warm terracotta gradient, artistic editorial mood. LEFT 40%: deeper terracotta zone for white or cream text. RIGHT: lighter rose warm zone for product. Abstract soft brush stroke hints, warm sunset light. Photorealistic, 8k, Canon EOS R5, f/5.6. NO clothing, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "auto": {
        "A": "Premium automotive background. Dark charcoal to deep slate grey gradient, dramatic cinematic atmosphere. TOP 30%: deepest dark zone for bright white text. CENTER: empty dark reflective surface, showroom floor. BOTTOM 20%: slightly lighter with subtle grid reflection for CTA. Dramatic light beams, subtle lens flares. Photorealistic, 8k, Canon EOS R5, f/8. NO car, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Dynamic automotive background. Silver metallic to cool blue-grey gradient, high-tech showroom. TOP 40%: deep metallic dark zone for bold white title. CENTER-BOTTOM: polished reflective floor, mirror-like surface. Geometric light lines, technological grid, cool blue accent light. Photorealistic, 8k, Canon EOS R5, f/8. NO car, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Futuristic automotive background. Deep navy blue fading to electric teal, futuristic mood. LEFT 40%: darkest navy zone for bright text. RIGHT: lighter teal gradient, dynamic space. Abstract speed lines, light trails, carbon fiber texture hints. Photorealistic, 8k, Canon EOS R5, f/5.6. NO car, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "food": {
        "A": "Warm food advertisement background. Cream beige and warm wheat gradient, cozy artisan aesthetic. TOP 30%: deeper warm brown tone for text. CENTER: clean warm surface, rustic wooden table feel. BOTTOM 20%: lighter cream with subtle linen cloth texture for CTA. Scattered flour dust, wheat ears corners, warm golden light. Photorealistic, 8k, Canon EOS R5, f/4. NO food, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Fresh food background. Soft mint green and fresh white gradient, clean healthy organic aesthetic. TOP 40%: deeper mint zone for large fresh title. CENTER-BOTTOM: clean white surface, minimal platform. Fresh herb leaves on far edges, soft morning light water droplets. Photorealistic, 8k, Canon EOS R5, f/5.6. NO food, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Premium restaurant background. Deep forest green and warm gold gradient, upscale dining atmosphere. LEFT 40%: deep green darker zone for gold or white text. RIGHT: warm golden lighter zone for dish. Subtle marble texture, gold cutlery hints on far edges, candlelight bokeh. Photorealistic, 8k, Canon EOS R5, f/2.8. NO food, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "health": {
        "A": "Clean medical health background. Pure white and soft sky blue gradient, clinical professional aesthetic. TOP 30%: deeper sky blue zone for text. CENTER: pristine white empty space, clinical surface. BOTTOM 20%: soft blue-white with subtle geometric pattern for CTA. Minimal clean lines, soft light flares. Photorealistic, 8k, Canon EOS R5, f/8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Natural wellness background. Soft sage green and warm cream gradient, organic health aesthetic. TOP 40%: deeper sage green zone for bold title. CENTER-BOTTOM: natural stone or wood surface, organic platform. Fresh green leaves far edges only, soft morning sunlight rays. Photorealistic, 8k, Canon EOS R5, f/4. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Premium clinic background. Deep teal and clean aqua gradient, modern medical spa aesthetic. LEFT 40%: deep teal darker zone for white text. RIGHT: lighter aqua clean zone, professional space. Subtle geometric details, soft lens flare, clean minimal. Photorealistic, 8k, Canon EOS R5, f/5.6. NO product, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "home": {
        "A": "Elegant interior design background. Warm greige and soft ivory gradient, Scandinavian minimalist. TOP 30%: deeper warm greige for dark or white text. CENTER: completely empty clean space, neutral floor. BOTTOM 20%: light ivory with subtle herringbone wood texture for CTA. Soft natural shadows, warm afternoon light. Photorealistic, 8k, Canon EOS R5, f/8. NO furniture, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Luxurious home decor background. Deep mocha brown and warm terracotta gradient, mediterranean mood. TOP 40%: deep mocha zone for elegant white title. CENTER-BOTTOM: warm polished surface for decor. Subtle arch architectural hints on sides, warm amber light. Photorealistic, 8k, Canon EOS R5, f/5.6. NO furniture, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Contemporary home background. Soft dusty blue and warm linen gradient, modern coastal aesthetic. LEFT 40%: deeper dusty blue for white or cream text. RIGHT: warm linen zone, airy space for furniture. Subtle rattan texture hints on far edges, soft diffused light. Photorealistic, 8k, Canon EOS R5, f/8. NO furniture, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "tech": {
        "A": "Premium tech background. Deep space grey and cool black gradient, Apple-style minimalist. TOP 30%: darkest zone for white or silver text. CENTER: empty dark reflective surface, sleek platform. BOTTOM 20%: slightly lighter grey with subtle grid for CTA. Minimal light beam, soft blue-white tech glow. Photorealistic, 8k, Canon EOS R5, f/8. NO device, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Futuristic technology background. Electric dark blue and deep indigo gradient, high-tech innovation. TOP 40%: deepest indigo zone for bold glowing title. CENTER-BOTTOM: subtle circuit texture, technological surface. Abstract digital light particles, neon blue accent lines on edges. Photorealistic, 8k, Canon EOS R5, f/5.6. NO device, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Sleek modern tech background. Pure white and soft silver gradient, clean Scandinavian aesthetic. LEFT 40%: soft silver grey for dark or colored text. RIGHT: brighter white clean zone for device. Subtle diagonal light reflections, clean geometric shadow lines. Photorealistic, 8k, Canon EOS R5, f/11. NO device, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "flowers": {
        "A": "Romantic flower shop background. Soft blush pink and warm ivory gradient, dreamy floral boutique. TOP 30%: deeper blush pink for white or dark text. CENTER: completely empty soft space for bouquet. BOTTOM 20%: pale ivory with scattered tiny petals for CTA. Soft out-of-focus flowers on far edges, warm golden bokeh. Photorealistic, 8k, Canon EOS R5, f/2.8. NO flowers, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Luxury gift background. Deep emerald green and warm champagne gradient, premium boutique. TOP 40%: rich emerald zone for gold title text. CENTER-BOTTOM: warm champagne surface for gift. Scattered gold ribbon hints on far edges, sparkle bokeh lights. Photorealistic, 8k, Canon EOS R5, f/2.8. NO flowers, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Fresh floral background. Bright white and soft lavender gradient, airy spring garden. LEFT 40%: deeper lavender for white or dark text. RIGHT: bright white airy zone for floral arrangement. Delicate wisteria hints on upper edges, soft morning light, dew droplets. Photorealistic, 8k, Canon EOS R5, f/2.8. NO flowers, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "kids": {
        "A": "Playful children product background. Soft sky blue and warm cloud white gradient, cheerful nursery. TOP 30%: deeper sky blue for colorful text. CENTER: completely empty soft space for toy or product. BOTTOM 20%: pale warm white with subtle polka dot pattern for CTA. Tiny stars and cloud shapes on far edges, soft sunlight. Photorealistic, 8k, Canon EOS R5, f/5.6. NO toy, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Cute children background. Warm peach and soft mint green gradient, gentle playful nursery. TOP 40%: deeper peach for fun colorful title. CENTER-BOTTOM: soft warm surface, gentle platform. Small geometric shapes, tiny stars, rainbow hints on far edges. Photorealistic, 8k, Canon EOS R5, f/5.6. NO toy, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Dreamy children background. Soft lilac purple and warm cream gradient, magical fairytale nursery. LEFT 40%: deeper lilac for white or yellow text. RIGHT: warm cream zone, magical space. Tiny floating stars, small cloud wisps, sparkle dust on far edges. Photorealistic, 8k, Canon EOS R5, f/4. NO toy, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "realestate": {
        "A": "Premium real estate background. Deep navy blue and warm gold gradient, prestigious architectural. TOP 30%: deep navy zone for gold or white text. CENTER: completely empty elegant space. BOTTOM 20%: warm gold with subtle marble texture for CTA. Abstract architectural lines, geometric shadows, warm golden light. Photorealistic, 8k, Canon EOS R5, f/8. NO building, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Luxury property background. Warm cream white and soft beige gradient, high-end real estate. TOP 40%: deeper warm beige for prestigious title. CENTER-BOTTOM: polished marble surface, luxurious platform. Subtle architectural arch hints on sides, warm afternoon sunlight. Photorealistic, 8k, Canon EOS R5, f/8. NO building, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Modern real estate background. Cool steel blue and clean white gradient, contemporary architectural. LEFT 40%: deeper steel blue for white text. RIGHT: clean white bright zone, modern space. Minimal geometric window light patterns, subtle glass reflection. Photorealistic, 8k, Canon EOS R5, f/11. NO building, NO text, NO people, NO logos. Vertical 9:16.",
    },
    "travel": {
        "A": "Dreamy travel background. Bright turquoise ocean and warm sandy beige gradient, Mediterranean paradise. TOP 30%: deeper turquoise sky zone for white text. CENTER: empty horizon space, open panoramic area. BOTTOM 20%: warm sandy texture for CTA. Subtle palm leaf hints on upper corners, soft tropical sunlight. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Romantic travel background. Golden sunset orange and warm coral gradient, dreamy wanderlust. TOP 40%: deep warm amber sky zone for white travel title. CENTER-BOTTOM: calm golden water reflection, magical surface. Soft sun rays, light cloud wisps, warm bokeh horizon glow. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Luxury travel background. Deep ocean blue and bright aqua gradient, aspirational lifestyle. LEFT 40%: deep ocean blue for white or gold text. RIGHT: bright turquoise zone, vivid space. Subtle white bougainvillea hints, Mediterranean white architecture edges. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "psychology": {
        "A": "Calm psychology background. Soft warm grey and gentle sage green gradient, mindful therapeutic. TOP 30%: deeper warm grey for white or dark text. CENTER: completely empty peaceful space. BOTTOM 20%: soft sage with subtle linen texture for CTA. Minimal dried pampas grass hints on far edges, soft warm morning light. Photorealistic, 8k, Canon EOS R5, f/4. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Peaceful coaching background. Warm sand beige and soft terracotta gradient, grounded mindfulness. TOP 40%: deeper sand for calm bold title. CENTER-BOTTOM: warm natural surface, earthy platform. Subtle dried botanical stems on far edges, warm golden afternoon light. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Serene wellness background. Soft lavender and warm cream white gradient, gentle healing. LEFT 40%: deeper lavender for dark or white text. RIGHT: warm cream zone, peaceful space. Delicate wildflower hints on edges, soft dreamy bokeh light orbs. Photorealistic, 8k, Canon EOS R5, f/2.8. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "legal": {
        "A": "Professional legal background. Deep charcoal and warm dark navy gradient, authoritative prestigious. TOP 30%: darkest charcoal for gold or white text. CENTER: completely empty dignified space. BOTTOM 20%: slightly lighter with subtle leather texture for CTA. Minimal architectural column shadows, dramatic single light beam. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Trustworthy law firm background. Rich dark burgundy and warm gold gradient, classic prestigious legal. TOP 40%: deep burgundy for gold title text. CENTER-BOTTOM: warm polished wood surface, distinguished platform. Subtle bookshelf shadow hints on far sides, warm amber light. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Modern legal background. Clean navy blue and crisp white gradient, contemporary professional. LEFT 40%: deep navy for white text. RIGHT: clean bright white zone, modern space. Subtle geometric justice scale shadow hints, minimal clean architectural lines. Photorealistic, 8k, Canon EOS R5, f/11. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "medical": {
        "A": "Clean modern clinic background. Pure white and soft sky blue gradient, professional medical. TOP 30%: deeper sky blue for dark or white text. CENTER: pristine white empty space, clinical surface. BOTTOM 20%: soft blue-white with hexagonal pattern for CTA. Minimal clean light reflections, fresh sterile atmosphere. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Welcoming dental clinic background. Soft aqua and warm cream white gradient, friendly modern medical. TOP 40%: deeper aqua for trustworthy title text. CENTER-BOTTOM: clean white polished surface, professional platform. Subtle soft geometric shapes on far edges, bright fresh morning light. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Premium medical background. Deep teal and clean mint green gradient, sophisticated healthcare. LEFT 40%: deep teal for white text. RIGHT: lighter mint clean zone, professional space. Minimal molecular or geometric pattern hints, cool clean light. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "education": {
        "A": "Modern online education background. Warm yellow and soft cream white gradient, energetic knowledge. TOP 30%: deeper warm amber for dark or white text. CENTER: completely empty bright space for visual. BOTTOM 20%: soft cream with subtle notebook texture for CTA. Small geometric shapes, tiny star accents, warm motivational sunlight. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Creative learning background. Deep purple and bright coral gradient, dynamic modern education. TOP 40%: deep purple for bold white title. CENTER-BOTTOM: warm coral surface, energetic platform. Abstract geometric shapes floating, bright accent light. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Professional online course background. Clean navy blue and bright sky blue gradient, trustworthy educational. LEFT 40%: deep navy for white or yellow text. RIGHT: bright sky blue zone, open space. Subtle book or diploma shadow hints, clean geometric light patterns. Photorealistic, 8k, Canon EOS R5, f/8. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "kids_education": {
        "A": "Bright children education background. Cheerful yellow and soft sky blue gradient, playful learning. TOP 30%: deeper sunny yellow for dark or white text. CENTER: completely empty playful space for product. BOTTOM 20%: soft blue with subtle ABC letter shadow pattern for CTA. Tiny pencil and star shapes on far edges, bright cheerful sunlight. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "B": "Magical children learning background. Soft mint green and warm sunshine yellow gradient, imaginative friendly. TOP 40%: deeper mint green for fun colorful title. CENTER-BOTTOM: warm yellow soft surface, magical platform. Tiny rainbow hints, small cloud shapes, sunshine rays. Photorealistic, 8k, Canon EOS R5, f/5.6. NO people, NO text, NO logos. Vertical 9:16.",
        "C": "Dreamy educational background. Soft coral peach and warm lavender gradient, gentle creative learning. LEFT 40%: deeper coral for white or dark text. RIGHT: soft lavender zone, imaginative space. Small floating book and star shapes, soft warm dreamy light. Photorealistic, 8k, Canon EOS R5, f/4. NO people, NO text, NO logos. Vertical 9:16.",
    },
    "photo": {
        "A": "Creative photography studio background. Deep matte black and warm charcoal gradient, professional creative. TOP 30%: darkest matte black for white or gold text. CENTER: completely empty dark space, dramatic backdrop. BOTTOM 20%: slightly lighter charcoal with subtle film grain for CTA. Single dramatic spotlight from top center, soft smoke wisps on far edges. Photorealistic, 8k, Canon EOS R5, f/2.8. NO people, NO camera, NO text, NO logos. Vertical 9:16.",
        "B": "Artistic photography background. Warm film orange and soft cream gradient, vintage cinematic. TOP 40%: deeper warm amber for elegant title text. CENTER-BOTTOM: warm cream surface, nostalgic platform. Subtle film strip hints on far edges, warm vintage light leak. Photorealistic, 8k, Canon EOS R5, f/2.8. NO people, NO camera, NO text, NO logos. Vertical 9:16.",
        "C": "Modern videography background. Electric blue and deep black gradient, cinematic production. LEFT 40%: deep black for bright white text. RIGHT: electric blue zone, dynamic space. Abstract light trail hints on edges, subtle lens flare, cinematic bokeh. Photorealistic, 8k, Canon EOS R5, f/2.8. NO people, NO camera, NO text, NO logos. Vertical 9:16.",
    },
    "universal": {
        "A": "Clean professional advertisement background. Warm cream and soft beige gradient, universal commercial aesthetic. TOP 30%: slightly deeper warm tone for text overlay. CENTER: completely empty clean space for product placement. BOTTOM 20%: light cream with subtle texture for CTA zone. Soft natural shadows, minimal elegant decor on far edges. Photorealistic, 8k, Canon EOS R5, f/5.6. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "B": "Elegant universal advertisement background. Soft grey and warm white gradient, clean modern aesthetic. TOP 40%: deeper grey for bold title text. CENTER-BOTTOM: clean polished surface, minimal platform. Subtle geometric light patterns, soft professional lighting. Photorealistic, 8k, Canon EOS R5, f/8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
        "C": "Modern universal advertisement background. Deep slate blue and clean silver gradient, contemporary. LEFT 40%: deeper slate for white or light text. RIGHT: lighter silver zone, clean space. Minimal abstract light lines on edges, professional studio feel. Photorealistic, 8k, Canon EOS R5, f/8. NO product, NO text, NO people, NO logos. Vertical 9:16.",
    },
}

# ═══ ОПРЕДЕЛЕНИЕ НИШИ ═══
NICHE_KEYWORDS = {
    "beauty": ["салон", "красот", "косметол", "массаж", "спа", "spa", "уход", "крем", "маска", "скраб", "ботокс", "эпиляц"],
    "perfume": ["парфюм", "духи", "аромат", "туалетн", "fragrance", "perfume"],
    "fashion": ["одежд", "платье", "костюм", "обувь", "сумк", "аксессуар", "мод", "бутик", "fashion"],
    "auto": ["авто", "машин", "автомобил", "шин", "резин", "запчаст", "кузов", "двигател", "car", "auto"],
    "food": ["еда", "ресторан", "кафе", "доставк", "пицц", "суши", "бургер", "выпечк", "торт", "food"],
    "health": ["здоровь", "витамин", "бад", "supplement", "аптек", "таблетк", "похуден"],
    "home": ["мебел", "декор", "интерьер", "диван", "стол", "кухн", "ремонт", "дом", "квартир"],
    "tech": ["телефон", "ноутбук", "планшет", "гаджет", "техник", "электрон", "смартфон", "наушник"],
    "flowers": ["цветы", "цветок", "букет", "флорист", "подарок", "розы", "тюльпан"],
    "kids": ["детск", "игрушк", "ребенок", "малыш", "младенец", "коляск"],
    "realestate": ["недвижимост", "квартир", "дом", "жилье", "аренд", "ипотек", "новостройк"],
    "travel": ["туризм", "тур", "путешеств", "отдых", "отель", "море", "travel", "визы"],
    "psychology": ["психолог", "коуч", "терапия", "консультац", "тренинг", "личностн"],
    "legal": ["юрист", "адвокат", "нотариус", "юридич", "правов", "договор"],
    "medical": ["стоматолог", "клиника", "врач", "медицин", "лечен", "зуб"],
    "education": ["курс", "обучен", "учеба", "репетитор", "урок", "онлайн-курс", "тренинг"],
    "kids_education": ["детск", "школ", "детсад", "развитие ребенк", "детское обучен"],
    "photo": ["фотограф", "видеограф", "съемк", "фото", "видео", "photographer"],
}


def detect_niche(ad_text: str) -> str:
    """Определяет нишу по ключевым словам в тексте."""
    text_lower = ad_text.lower()
    scores = {}
    for niche, keywords in NICHE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[niche] = score
    if scores:
        return max(scores, key=scores.get)
    return "universal"


def get_background_prompt(niche: str, layout: str) -> str:
    """Возвращает промпт фона для нужной ниши и layout."""
    niche_data = NICHE_BACKGROUNDS.get(niche, NICHE_BACKGROUNDS["universal"])
    return niche_data.get(layout, niche_data["A"])


# ═══ SYSTEM PROMPT ═══
SYSTEM_PROMPT = """Ты — топовый арт-директор рекламных креативов для Instagram.

ЗАДАЧА: из рекламного текста создать структуру баннера.

═══ ПРАВИЛА ТЕКСТА ═══
- headline: цепляющий, обычный регистр, 4-7 слов, конкретный оффер
- subheadline: уточнение одной строкой, макс 8 слов
- bullets: ровно 3 штуки, начинаются с "—", максимум 5 слов каждый
- price: только цифра + валюта (пример: "24 000 ₸") или пусто
- badge: город ИЛИ статус (Астана / Алматы / Акция / Хит / Новинка) или пусто
- cta: конкретный призыв (Напишите нам / Узнать цену / Записаться)

Отвечай ТОЛЬКО валидным JSON без markdown:
{
  "headline": "...",
  "subheadline": "...",
  "bullets": ["— ...", "— ...", "— ..."],
  "price": "...",
  "badge": "...",
  "cta": "..."
}"""


async def build_creative_plan(ad_text: str,
                               image_path: str = None,
                               layout: str = "A") -> CreativePlan:
    """
    Строит план баннера.
    layout: "A", "B", или "C"
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
                    "text": f"Рекламный текст:\n{ad_text}\n\nСоздай план баннера."
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
        }

    # Определяем нишу и берём промпт фона
    niche = detect_niche(ad_text)
    bg_prompt = get_background_prompt(niche, layout)
    logger.info(f"Detected niche: {niche}, layout: {layout}")

    plan = CreativePlan(
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        bullets=data.get("bullets", []),
        price=data.get("price", ""),
        badge=data.get("badge", ""),
        cta=data.get("cta", "Узнать подробнее"),
        style="minimal",
    )

    # Один промпт фона вместо трёх — по выбранному layout
    plan.bg_prompt = bg_prompt
    plan.niche = niche
    plan.layout = layout

    return plan
