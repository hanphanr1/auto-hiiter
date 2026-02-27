import os
import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, PORT, WEBHOOK_URL
from commands import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)


async def on_shutdown(bot: Bot):
    from functions.charge_functions import close_session
    await close_session()
    from functions.co_functions import _co_session
    if _co_session and not _co_session.closed:
        await _co_session.close()
    logger.info("Bot shutdown complete")


async def health_check(request):
    return web.Response(text="OK")


def run_webhook():
    """Full webhook mode - Telegram pushes updates to our server."""
    webhook_path = f"/webhook/{BOT_TOKEN}"

    async def on_startup(bot: Bot):
        full_url = f"{WEBHOOK_URL}{webhook_path}"
        await bot.set_webhook(full_url, drop_pending_updates=True)
        logger.info("Webhook registered: %s", full_url)

    async def on_shutdown_hook(bot: Bot):
        await bot.delete_webhook()
        await on_shutdown(bot)

    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown_hook)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    logger.info("Starting webhook mode on port %d", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)


def run_polling_with_health():
    """Polling mode + health check server for Railway."""

    async def start():
        app = web.Application()
        app.router.add_get("/", health_check)
        app.router.add_get("/health", health_check)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info("Health check server on port %d", PORT)

        logger.info("Starting polling mode")
        try:
            await dp.start_polling(bot, skip_updates=True)
        finally:
            await on_shutdown(bot)
            await runner.cleanup()

    asyncio.run(start())


def run_polling():
    """Pure polling mode for local dev."""

    async def start():
        logger.info("Starting polling mode (local)")
        try:
            await dp.start_polling(bot, skip_updates=True)
        finally:
            await on_shutdown(bot)

    asyncio.run(start())


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required")
        return

    if WEBHOOK_URL:
        run_webhook()
    elif os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"):
        run_polling_with_health()
    else:
        run_polling()


if __name__ == "__main__":
    main()
