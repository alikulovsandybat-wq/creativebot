import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from services.creative_planner import build_creative_plan
from services.variant_generator import generate_variants

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class CreativeFlow(StatesGroup):
    choosing_brand_style = State()
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


def brand_style_keyboard():
    buttons = []
    for key, label in BRAND_STYLES.items():
        buttons.append([InlineKeyboardButton(
            text=f"{label} — {BRAND_DESCRIPTIONS[key]}",
            callback_data=f"brand_{key}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ещё 3 варианта", callback_data="regenerate")],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="change_text"),
         InlineKeyboardButton(text="🖼 Изменить фото", callback_data="change_photo")],
        [InlineKeyboardButton(text="🎨 Изменить стиль бренда", callback_data="change_brand")],
    ])


@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я создаю рекламные креативы.\n\n"
        "Сначала выбери стиль своего бренда:",
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
        f"Отлично! Стиль: {label}\n\n"
        f"Теперь отправь мне:\n"
        f"📸 <b>Фото</b> товара или услуги\n"
        f"или\n"
        f"💬 <b>Текст</b> с описанием",
        parse_mode="HTML"
    )
    await state.set_state(CreativeFlow.waiting_for_photo_or_prompt)


@dp.callback_query(F.data == "change_brand")
async def change_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "Выбери новый стиль бренда:",
        reply_markup=brand_style_keyboard()
    )
    await state.set_state(CreativeFlow.choosing_brand_style)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    os.makedirs("/tmp/creative_temp", exist_ok=True)
    image_path = f"/tmp/creative_temp/{message.from_user.id}_source.jpg"
    await bot.download_file(file.file_path, image_path)
    await state.update_data(image_path=image_path)
    await message.answer(
        "✅ Фото получил!\n\n"
        "Напиши рекламный текст — что продаём, цена, акции, выгоды:"
    )
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.text)
async def handle_prompt(message: Message, state: FSMContext):
    await state.update_data(image_path=None, ad_text=message.text)
    await message.answer(
        "✅ Принял!\n\n"
        "Добавь подробности: цена, акции, выгоды (или отправь как есть):"
    )
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.message(CreativeFlow.waiting_for_ad_text, F.text)
async def handle_ad_text(message: Message, state: FSMContext):
    data = await state.get_data()
    image_path = data.get("image_path")
    existing_text = data.get("ad_text", "")
    ad_text = existing_text + "\n" + message.text if existing_text else message.text
    await state.update_data(ad_text=ad_text)
    await _generate_and_send(message, state, image_path, ad_text)


async def _generate_and_send(message: Message, state: FSMContext,
                              image_path: str, ad_text: str):
    status = await message.answer("⚡ Генерирую 3 варианта креатива...")
    try:
        data = await state.get_data()
        brand_style = data.get("brand_style", "universal")

        plan = await build_creative_plan(ad_text, image_path)
        plan.brand_style = brand_style
        await state.update_data(plan=plan.__dict__)

        output_dir = f"/tmp/creative_outputs/{message.from_user.id}"
        os.makedirs(output_dir, exist_ok=True)

        paths = await generate_variants(plan, image_path, output_dir, ad_text=ad_text)

        try:
            await status.delete()
        except Exception:
            pass

        from aiogram.types import BufferedInputFile
        labels = ["✨ Premium", "🎯 Conversion", "🤍 Minimal"]
        sent = 0
        for path, label in zip(paths, labels):
            if os.path.exists(path):
                with open(path, "rb") as f:
                    photo_data = f.read()
                file_obj = BufferedInputFile(photo_data, filename="banner.png")
                await message.answer_photo(file_obj, caption=label)
                sent += 1

        if sent == 0:
            await message.answer("⚠️ Не удалось создать баннеры. Попробуй ещё раз.")
            return

        await message.answer(
            "Вот твои 3 варианта! Выбери или:",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        try:
            await status.edit_text(f"❌ Ошибка: {e}")
        except Exception:
            await message.answer(f"❌ Ошибка: {e}")


@dp.callback_query(F.data == "regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer()
    await _generate_and_send(
        callback.message, state,
        data.get("image_path"), data.get("ad_text", "")
    )


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
