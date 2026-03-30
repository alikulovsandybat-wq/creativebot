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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{label} — {BRAND_DESCRIPTIONS[key]}",
            callback_data=f"brand_{key}"
        )] for key, label in BRAND_STYLES.items()
    ])


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
        f"Стиль: {label}\n\nОтправь:\n📸 <b>Фото</b> товара\nили\n💬 <b>Текст</b> с описанием",
        parse_mode="HTML"
    )
    await state.set_state(CreativeFlow.waiting_for_photo_or_prompt)


@dp.callback_query(F.data == "change_brand")
async def change_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выбери новый стиль:", reply_markup=brand_style_keyboard())
    await state.set_state(CreativeFlow.choosing_brand_style)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    os.makedirs("/tmp/creative_temp", exist_ok=True)
    image_path = f"/tmp/creative_temp/{message.from_user.id}_source.jpg"
    await bot.download_file(file.file_path, image_path)
    await state.update_data(image_path=image_path, replace_bg=False)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎨 Заменить фон через AI",
            callback_data="bg_replace"
        )],
        [InlineKeyboardButton(
            text="📸 Оставить моё фото как есть",
            callback_data="bg_keep"
        )],
    ])
    await message.answer("✅ Фото получил!\n\nЧто делаем с фоном?", reply_markup=kb)


@dp.callback_query(F.data.in_({"bg_replace", "bg_keep"}))
async def handle_bg_choice(callback: CallbackQuery, state: FSMContext):
    replace_bg = callback.data == "bg_replace"
    await state.update_data(replace_bg=replace_bg)
    await callback.answer()
    label = "🎨 Фон заменим через AI" if replace_bg else "📸 Фото оставим как есть"
    await callback.message.edit_text(
        f"{label}\n\nТеперь напиши рекламный текст — что продаём, цена, акции:"
    )
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
    await _generate_and_send(message, state, data.get("image_path"), ad_text)


async def _generate_and_send(message: Message, state: FSMContext,
                              image_path: str, ad_text: str):
    status = await message.answer("⚡ Начинаю генерацию — первый баннер придёт через ~30 сек...")

    try:
        data = await state.get_data()
        brand_style = data.get("brand_style", "universal")
        replace_bg = data.get("replace_bg", False)

        plan = await build_creative_plan(ad_text, image_path)
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
                # Удаляем статус после первого баннера
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
            replace_bg=replace_bg
        )

        if sent_count == 0:
            await status.edit_text("⚠️ Не удалось создать баннеры. Попробуй ещё раз.")
            return

        await message.answer(
            f"Готово! Отправил {sent_count} варианта 👆",
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
