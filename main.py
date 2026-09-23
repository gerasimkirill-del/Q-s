"""
Главный файл бота Q Holsters. Версия — config.VERSION, история — CHANGELOG.md
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from models.database import Database
from handlers.admin_handlers import router as admin_router
from handlers.order_handlers import router as order_router
from services.bot_commands import setup_commands

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    if not config.BOT_TOKEN:
        logger.error("Не задан BOT_TOKEN (файл .env или переменные окружения).")
        return

    # Встроенные админы (Kirill, Dima) активны всегда — без выбора в консоли
    db = Database()
    admin_ids = list(dict.fromkeys(config.ADMIN_IDS + db.get_all_admins()))
    logger.info(f"Q Holsters Bot v{config.VERSION}. Администраторы: {admin_ids}")

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    bot = Bot(token=config.BOT_TOKEN)

    await setup_commands(bot, admin_ids)

    # Админский роутер первым: его состояния (ввод ID, шаблон модели) важнее «вопроса вне анкеты»
    dp.include_router(admin_router)
    dp.include_router(order_router)

    logger.info("Бот запущен. Для остановки нажмите Ctrl+C.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Сессия закрыта.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
