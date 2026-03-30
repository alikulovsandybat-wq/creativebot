import asyncio
import sys
import os
import logging
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути к шрифтам — проверяем все возможные места
FONT_SEARCH_PATHS = [
    # Папка проекта (из репозитория)
    os.path.join(os.path.dirname(__file__), "fonts_all", "fonts", "universal"),
    os.path.join(os.path.dirname(__file__), "fonts", "universal"),
    # Системные пути Railway/Debian
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/noto",
    "/usr/share/fonts/truetype/liberation",
    "/app/fonts/universal",
]

FONT_URLS = {
    "NotoSans-Bold.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    "NotoSans-Regular.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
}


def ensure_fonts():
    """Проверяем есть ли шрифты. Если нет — скачиваем."""
    # Сначала ищем в проекте
    for search_path in FONT_SEARCH_PATHS:
        bold = os.path.join(search_path, "bold.ttf")
        regular = os.path.join(search_path, "regular.ttf")
        if os.path.exists(bold) and os.path.exists(regular):
            logger.info(f"✅ Fonts found at: {search_path}")
            return True

    # Не нашли — скачиваем в /tmp/fonts
    fonts_dir = "/tmp/creative_fonts"
    os.makedirs(fonts_dir, exist_ok=True)

    logger.info("Downloading fonts to /tmp/creative_fonts...")
    try:
        for filename, url in FONT_URLS.items():
            path = os.path.join(fonts_dir, filename)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
                logger.info(f"✅ Downloaded: {filename}")

        # Создаём симлинки с нужными именами
        bold_src = os.path.join(fonts_dir, "NotoSans-Bold.ttf")
        reg_src = os.path.join(fonts_dir, "NotoSans-Regular.ttf")
        if os.path.exists(bold_src):
            os.symlink(bold_src, os.path.join(fonts_dir, "bold.ttf"))
            os.symlink(bold_src, os.path.join(fonts_dir, "semibold.ttf"))
            os.symlink(reg_src, os.path.join(fonts_dir, "regular.ttf"))
            os.symlink(reg_src, os.path.join(fonts_dir, "light.ttf"))

        # Говорим renderer где искать
        os.environ["CREATIVE_FONTS_DIR"] = fonts_dir
        logger.info(f"✅ Fonts ready at: {fonts_dir}")
        return True
    except Exception as e:
        logger.warning(f"Font download failed: {e} — will use system fonts")
        return False


async def warmup_rembg():
    """Предзагружаем rembg модель при старте."""
    try:
        logger.info("Warming up rembg model...")
        from rembg import new_session
        new_session("u2net")
        logger.info("✅ rembg model ready")
    except Exception as e:
        logger.warning(f"rembg warmup skipped: {e}")


async def main():
    from bot.handlers import dp, bot
    print("🚀 Creative Bot запущен...")

    # Шрифты
    ensure_fonts()

    # rembg в фоне
    asyncio.create_task(warmup_rembg())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
