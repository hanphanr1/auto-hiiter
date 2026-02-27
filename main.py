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


async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        webhook_path = f"/webhook/{BOT_TOKEN}"
        full_url = f"{WEBHOOK_URL}{webhook_path}"
        await bot.set_webhook(full_url, drop_pending_updates=True)
        logger.info("Webhook set to %s", full_url)
    else:
        logger.info("No WEBHOOK_URL set, will use polling")


async def on_shutdown(bot: Bot):
    from functions.charge_functions import close_session
    await close_session()
    from functions.co_functions import _co_session
    if _co_session and not _co_session.closed:
        await _co_session.close()
    if WEBHOOK_URL:
        await bot.delete_webhook()
    logger.info("Bot shutdown complete")


async def health_check(request):
    return web.Response(text="OK")


def run_webhook():
    webhook_path = f"/webhook/{BOT_TOKEN}"

    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    logger.info("Starting webhook server on port %d", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)


async def run_polling():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling mode")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        from functions.charge_functions import close_session
        await close_session()


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required")
        return

    if WEBHOOK_URL or os.environ.get("RAILWAY_ENVIRONMENT"):
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
