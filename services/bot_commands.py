"""
Меню команд бота: пользователи видят только /start и /ask, админы — ещё /admin
"""
import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

logger = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Начать оформление заказа"),
    BotCommand(command="ask",   description="Задать вопрос"),
]
ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="admin", description="Меню администратора"),
]


async def set_admin_commands(bot: Bot, admin_id: int):
    try:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception as e:  # админ ещё не писал боту — команды появятся после /start
        logger.warning(f"Не удалось задать меню команд для {admin_id}: {e}")


async def reset_commands(bot: Bot, user_id: int):
    try:
        await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=user_id))
    except Exception:
        pass


async def setup_commands(bot: Bot, admin_ids: list[int]):
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in admin_ids:
        await set_admin_commands(bot, admin_id)
