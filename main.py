import asyncio
import sys
import os
import logging
import urllib.request
from aiohttp import web

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══ ШРИФТЫ ═══
FONT_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), "fonts_all", "fonts", "universal"),
    os.path.join(os.path.dirname(__file__), "fonts", "universal"),
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
    for search_path in FONT_SEARCH_PATHS:
        bold = os.path.join(search_path, "bold.ttf")
        regular = os.path.join(search_path, "regular.ttf")
        if os.path.exists(bold) and os.path.exists(regular):
            logger.info(f"✅ Fonts found at: {search_path}")
            os.environ["CREATIVE_FONTS_DIR"] = search_path
            return True

    fonts_dir = "/tmp/creative_fonts"
    os.makedirs(fonts_dir, exist_ok=True)
    logger.info("Downloading fonts to /tmp/creative_fonts...")

    try:
        for filename, url in FONT_URLS.items():
            path = os.path.join(fonts_dir, filename)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
                logger.info(f"✅ Downloaded: {filename}")

        # Копируем с нужными именами (без симлинков — они падают при перезапуске)
        import shutil
        bold_src = os.path.join(fonts_dir, "NotoSans-Bold.ttf")
        reg_src = os.path.join(fonts_dir, "NotoSans-Regular.ttf")
        for name in ["bold.ttf", "semibold.ttf"]:
            dst = os.path.join(fonts_dir, name)
            if not os.path.exists(dst):
                shutil.copy2(bold_src, dst)
        for name in ["regular.ttf", "light.ttf"]:
            dst = os.path.join(fonts_dir, name)
            if not os.path.exists(dst):
                shutil.copy2(reg_src, dst)

        os.environ["CREATIVE_FONTS_DIR"] = fonts_dir
        logger.info(f"✅ Fonts ready at: {fonts_dir}")
        return True
    except Exception as e:
        logger.warning(f"Font download failed: {e} — will use system fonts")
        return False


# ═══ WEB SERVER для editor.html ═══
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


async def handle_editor(request):
    """Отдаёт editor.html с подстановкой параметров из URL."""
    editor_path = os.path.join(STATIC_DIR, "editor.html")
    if not os.path.exists(editor_path):
        return web.Response(text="Editor not found", status=404)
    with open(editor_path, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(
        text=content,
        content_type="text/html",
        charset="utf-8"
    )


async def handle_health(request):
    """Health check для Railway."""
    return web.Response(text="OK")


async def handle_output_file(request):
    """Отдаёт сгенерированные файлы (фон, продукт) для редактора."""
    filename = request.match_info.get("filename", "")
    # Ищем файл в tmp директориях
    search_dirs = [
        "/tmp/creative_outputs",
        "/tmp/creative_temp",
    ]
    for d in search_dirs:
        for root, dirs, files in os.walk(d):
            if filename in files:
                filepath = os.path.join(root, filename)
                return web.FileResponse(filepath)
    return web.Response(text="File not found", status=404)


async def start_web_server():
    """Запускает aiohttp веб-сервер."""
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/editor", handle_editor)
    app.router.add_get("/editor.html", handle_editor)
    app.router.add_get("/files/{filename}", handle_output_file)

    # Статические файлы если папка есть
    if os.path.exists(STATIC_DIR):
        app.router.add_static("/static", STATIC_DIR)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Web server started on port {port}")
    return runner


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

    # 1. Шрифты — до всего
    ensure_fonts()

    # 2. Веб-сервер для редактора
    await start_web_server()

    # 3. rembg в фоне
    asyncio.create_task(warmup_rembg())

    # 4. Бот
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
