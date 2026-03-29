import asyncio
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(__file__))

from bot.handlers import dp, bot


async def main():
    print("🚀 Creative Bot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
