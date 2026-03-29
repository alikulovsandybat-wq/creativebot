import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from services.creative_planner import build_creative_plan
from services.variant_generator import generate_variants

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class CreativeFlow(StatesGroup):
    waiting_for_photo_or_prompt = State()
    waiting_for_ad_text = State()


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ещё 3 варианта", callback_data="regenerate")],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="change_text"),
         InlineKeyboardButton(text="🖼 Изменить фото", callback_data="change_photo")],
    ])


@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я создаю рекламные креативы.\n\n"
        "Отправь мне:\n"
        "📸 <b>Фото</b> товара или услуги\n"
        "или\n"
        "💬 <b>Текст</b> с описанием (я сам найду картинку)\n\n"
        "Начнём!",
        parse_mode="HTML"
    )
    await state.set_state(CreativeFlow.waiting_for_photo_or_prompt)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    # Скачиваем фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    os.makedirs("temp", exist_ok=True)
    image_path = f"temp/{message.from_user.id}_source.jpg"
    await bot.download_file(file.file_path, image_path)

    await state.update_data(image_path=image_path)
    await message.answer("✅ Фото получил!\n\nТеперь напиши рекламный текст — что продаём, цена, акции, выгоды:")
    await state.set_state(CreativeFlow.waiting_for_ad_text)


@dp.message(CreativeFlow.waiting_for_photo_or_prompt, F.text)
async def handle_prompt(message: Message, state: FSMContext):
    await state.update_data(image_path=None, ad_text=message.text)
    await message.answer("✅ Принял!\n\nДобавь подробности: цена, акции, выгоды (или отправь как есть):")
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
        # Планируем креатив
        plan = await build_creative_plan(ad_text, image_path)
        await state.update_data(plan=plan.__dict__)

        # Генерируем 3 варианта
        output_dir = f"outputs/{message.from_user.id}"
        paths = await generate_variants(plan, image_path, output_dir)

        await status.delete()

        # Отправляем все 3 баннера
        labels = ["✨ Premium", "🎯 Conversion", "🤍 Minimal"]
        for path, label in zip(paths, labels):
            if os.path.exists(path):
                with open(path, "rb") as f:
                    await message.answer_photo(f, caption=label)

        await message.answer(
            "Вот твои 3 варианта! Выбери понравившийся или:",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")


@dp.callback_query(F.data == "regenerate")
async def regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    image_path = data.get("image_path")
    ad_text = data.get("ad_text", "")
    await callback.answer()
    await _generate_and_send(callback.message, state, image_path, ad_text)


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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
