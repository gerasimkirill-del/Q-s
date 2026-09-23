"""
Сервис отправки вопросов от пользователей администраторам
"""
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import User

from config import BOT_TOKEN, ADMIN_IDS
from models.database import Database

logger = logging.getLogger(__name__)
db = Database()


class MessageService:

    @staticmethod
    async def send_question_to_admins(user: User, question: str, bot: Bot = None):
        own_session = bot is None
        bot = bot or Bot(token=BOT_TOKEN)
        try:
            message_text = MessageService._format_question(user, question)
            all_admins = list(set(db.get_all_admins() + ADMIN_IDS))
            for admin_id in all_admins:
                try:
                    await bot.send_message(admin_id, message_text)
                except Exception as e:
                    logger.error(f"Ошибка отправки вопроса администратору {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка отправки вопроса: {e}")
        finally:
            if own_session:
                await bot.session.close()

    @staticmethod
    def _format_question(user: User, question: str) -> str:
        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        return (
            f"❓ ВОПРОС ОТ КЛИЕНТА\n\n"
            f"👤 {user.first_name or '—'} ({username})\n\n"
            f"{question}\n\n"
            f"🕐 {now}"
        )
