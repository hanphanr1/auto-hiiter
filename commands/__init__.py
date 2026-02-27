from aiogram import Router

router = Router()

from commands.start import router as start_router
from commands.co import router as co_router
from commands.proxy_cmd import router as proxy_router
from commands.admin import router as admin_router

router.include_router(start_router)
router.include_router(co_router)
router.include_router(proxy_router)
router.include_router(admin_router)
