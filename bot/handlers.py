import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from services.creative_planner import build_creative_plan
from services.variant_generator import generate_variants

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══ ДОМЕН ═══
# После того как Railway сгенерирует домен — вставь его сюда
EDITOR_BASE_URL = os.getenv("EDITOR_URL", "https://YOUR_DOMAIN.up.railway.app")

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class CreativeFlow(StatesGroup):
    choosing_brand_style = State()
    choosing_format = State()        # НОВЫЙ ШАГ: квадрат или stories
    choosing_layout = State()        # НОВЫЙ ШАГ: layout A, B или C
    waiting_for_photo_or_prompt = State()
    waiting_for_ad_text = State()


BRAND_STYLES = {
    "delicate": "🌸 Нежный",
    "bold": "⚡ Дерзкий",
    "cozy": "🍃 Уютный",
    "premium_brand": "💎 Премиум",
    "universal": "✨ Универсальный",
}

BRAND_DESCRIPTIONS = {
    "delicate": "Салоны красоты, цветы, свадьбы, мода",
    "bold": "Авто, спорт, техника, мужской бренд",
    "cozy": "Еда, кафе, дом, детские товары",
    "premium_brand": "Ювелирка, люкс, недвижимость",
    "universal": "Подходит для любого бизнеса",
}

# Описания layout для пользователя
LAYOUT_DESCRIPTIONS = {
    "A": "📌 Заголовок сверху · Продукт по центру · CTA снизу",
    "B": "🔠 Большой заголовок сверху · Продукт снизу · CTA внизу",
    "C": "↔️ Текст слева · Продукт справа · CTA снизу",
}


# ═══ КЛАВИАТУРЫ ═══

def brand_style_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{label} — {BRAND_DESCRIPTIONS[key]}",
            callback_data=f"brand_{key}"
        )] for key, label in BRAND_STYLES.items()
    ])


def format_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⬛ Квадрат (1:1) — Посты в ленте, Telegram",
            callback_data="format_square"
        )],
        [InlineKeyboardButton(
            text="📱 Stories (9:16) — Instagram, TikTok, Reels",
            callback_data="format_stories"
        )],
    ])


def layout_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Layout A — {LAYOUT_DESCRIPTIONS['A']}",
            callback_data="layout_A"
        )],
        [InlineKeyboardButton(
            text=f"Layout B — {LAYOUT_DESCRIPTIONS['B']}",
            callback_data="layout_B"
        )],
        [InlineKeyboardButton(
            text=f"Layout C — {LAYOUT_DESCRIPTIONS['C']}",
            callback_data="layout_C"
        )],
    ])


def main_keyboard(editor_url: str = None):
    buttons = []
    if editor_url:
        buttons.append([InlineKeyboardButton(text="✏️ Править вручную", url=editor_url)])
    buttons += [
        [InlineKeyboardButton(text="🔄 Ещё варианты", callback_data="regenerate")],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="change_text"),
         InlineKeyboardButton(text="🖼 Изменить фото", callback_data="change_photo")],
        [InlineKeyboardButton(text="📐 Изменить layout", callback_data="change_layout")],
        [InlineKeyboardButton(text="📏 Изменить формат", callback_data="change_format")],
        [InlineKeyboardButton(text="🎨 Изменить стиль", callback_data="change_brand")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══ ХЭНДЛЕРЫ ═══

@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я создаю рекламные креативы.\n\nВыбери стиль бренда:",
        reply_markup=brand_style_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_brand_style)


@dp.callback_query(F.data.startswith("brand_"))
async def handle_brand_choice(callback: CallbackQuery, state: FSMContext):
    brand = callback.data.replace("brand_", "")
    label = BRAND_STYLES.get(brand, "✨ Универсальный")
    await state.update_data(brand_style=brand)
    await callback.answer()
    await callback.message.edit_text(
        f"Стиль: {label} ✅\n\nТеперь выбери формат баннера:",
        reply_markup=format_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_format)


@dp.callback_query(F.data.startswith("format_"))
async def handle_format_choice(callback: CallbackQuery, state: FSMContext):
    fmt = callback.data.replace("format_", "")  # "square" или "stories"
    canvas = (1080, 1080) if fmt == "square" else (1080, 1920)
    await state.update_data(format=fmt, canvas_size=canvas)
    await callback.answer()
    await callback.message.edit_text(
        f"Формат: {'⬛ Квадрат 1:1' if fmt == 'square' else '📱 Stories 9:16'} ✅\n\n"
        f"Выбери расположение элементов:",
        reply_markup=layout_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_layout)


@dp.callback_query(F.data.startswith("layout_"))
async def handle_layout_choice(callback: CallbackQuery, state: FSMContext):
    layout = callback.data.replace("layout_", "")  # "A", "B", "C"
    await state.update_data(layout=layout)
    await callback.answer()
    await callback.message.edit_text(
        f"Layout {layout} ✅ — {LAYOUT_DESCRIPTIONS[layout]}\n\n"
        f"Отправь:\n📸 <b>Фото</b> товара\nили\n💬 <b>Текст</b> с описанием",
        parse_mode="HTML"
    )
    await state.set_state(CreativeFlow.waiting_for_photo_or_prompt)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    os.makedirs("/tmp/creative_temp", exist_ok=True)
    image_path = f"/tmp/creative_temp/{message.from_user.id}_source.jpg"
    await bot.download_file(file.file_path, image_path)
    await state.update_data(image_path=image_path)
    await message.answer("✅ Фото получил!\n\nНапиши рекламный текст — что продаём, цена, акции:")
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.text)
async def handle_prompt(message: Message, state: FSMContext):
    await state.update_data(image_path=None, ad_text=message.text)
    await message.answer("✅ Принял!\n\nДобавь подробности или отправь как есть:")
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.message(CreativeFlow.waiting_for_ad_text, F.text)
async def handle_ad_text(message: Message, state: FSMContext):
    data = await state.get_data()
    existing = data.get("ad_text", "")
    ad_text = existing + "\n" + message.text if existing else message.text
    await state.update_data(ad_text=ad_text)
    await _generate_and_send(message, state)


async def _generate_and_send(message: Message, state: FSMContext):
    data = await state.get_data()
    image_path = data.get("image_path")
    ad_text = data.get("ad_text", "")
    brand_style = data.get("brand_style", "universal")
    layout = data.get("layout", "A")
    canvas_size = data.get("canvas_size", (1080, 1080))

    fmt_label = "⬛ Квадрат" if canvas_size == (1080, 1080) else "📱 Stories"
    status = await message.answer(
        f"⚡ Генерирую... {fmt_label} · Layout {layout}\n~30 сек, жди!"
    )

    try:
        plan = await build_creative_plan(ad_text, image_path, layout=layout)
        plan.brand_style = brand_style
        await state.update_data(plan=plan.__dict__)

        output_dir = f"/tmp/creative_outputs/{message.from_user.id}"
        os.makedirs(output_dir, exist_ok=True)

        sent_count = 0

        async def send_banner(path: str, label: str):
            nonlocal sent_count
            try:
                with open(path, "rb") as f:
                    photo_data = f.read()
                file_obj = BufferedInputFile(photo_data, filename="banner.png")
                await message.answer_photo(file_obj, caption=label)
                sent_count += 1
                if sent_count == 1:
                    try:
                        await status.delete()
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Failed to send banner: {e}")

        await generate_variants(
            plan, image_path, output_dir,
            ad_text=ad_text,
            send_callback=send_banner,
            layout=layout,
            canvas_size=canvas_size,
        )

        if sent_count == 0:
            await status.edit_text("⚠️ Не удалось создать баннер. Попробуй ещё раз.")
            return

        # Строим URL редактора
        editor_url = None
        try:
            import urllib.parse
            params = {
                "fmt": "square" if canvas_size == (1080, 1080) else "stories",
                "headline": plan.headline or "",
                "sub": plan.subheadline or "",
                "price": plan.price or "",
                "badge": plan.badge or "",
                "cta": plan.cta or "",
                "bullets": "|".join(plan.bullets or []),
            }
            query = urllib.parse.urlencode(params)
            editor_url = f"{EDITOR_BASE_URL}/editor?{query}"
        except Exception as e:
            logger.warning(f"Editor URL build failed: {e}")

        fmt_label = "⬛ Квадрат" if canvas_size == (1080, 1080) else "📱 Stories"
        await message.answer(
            f"Готово! 🎉\nФормат: {fmt_label} · Layout {layout}",
            reply_markup=main_keyboard(editor_url)
        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        try:
            await status.edit_text(f"❌ Ошибка: {e}")
        except Exception:
            await message.answer(f"❌ Ошибка: {e}")


# ═══ КНОПКИ ИЗМЕНЕНИЯ ═══

@dp.callback_query(F.data == "regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _generate_and_send(callback.message, state)


@dp.callback_query(F.data == "change_text")
async def change_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("✏️ Напиши новый рекламный текст:")
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.callback_query(F.data == "change_photo")
async def change_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🖼 Отправь новое фото:")
    await state.set_state(CreativeFlow.waiting_for_photo_or_prompt)


@dp.callback_query(F.data == "change_layout")
async def change_layout(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "📐 Выбери новое расположение элементов:",
        reply_markup=layout_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_layout)


@dp.callback_query(F.data == "change_format")
async def change_format(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "📏 Выбери формат:",
        reply_markup=format_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_format)


@dp.callback_query(F.data == "change_brand")
async def change_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "🎨 Выбери новый стиль бренда:",
        reply_markup=brand_style_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_brand_style)


@dp.message()
async def fallback_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Давай создадим крутой креатив!\n\nВыбери стиль бренда:",
        reply_markup=brand_style_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_brand_style)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
