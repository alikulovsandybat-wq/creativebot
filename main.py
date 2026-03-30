import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(__file__))
logger = logging.getLogger(__name__)


async def warmup_rembg():
    """Предзагружаем rembg модель при старте — до первого запроса."""
    try:
        logger.info("Warming up rembg model...")
        from rembg import new_session
        session = new_session("u2net")
        logger.info("✅ rembg model ready")
    except Exception as e:
        logger.warning(f"rembg warmup failed (will retry on first use): {e}")


async def main():
    from bot.handlers import dp, bot
    print("🚀 Creative Bot запущен...")

    # Прогреваем модель в фоне пока бот стартует
    asyncio.create_task(warmup_rembg())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
