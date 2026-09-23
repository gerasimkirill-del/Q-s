"""
Сервис отправки заявок администраторам
"""
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import User

from utils.keyboard import create_order_status_keyboard

from config import BOT_TOKEN, ADMIN_IDS
from models.database import Database

logger = logging.getLogger(__name__)
db = Database()


class OrderService:

    @staticmethod
    async def save_and_notify(user: User, order_data, bot: Bot = None):
        own_session = bot is None
        bot = bot or Bot(token=BOT_TOKEN)
        try:
            order_id = db.save_order(
                user_id=user.id,
                user_name=user.first_name or "",
                user_username=user.username or None,
                pistol_model=f"{order_data.pistol_brand} {order_data.pistol_model}",
                holster_type=order_data.holster_type,
                flashlight=order_data.flashlight,
                color=order_data.color,
                city=order_data.city,
                customer_name=order_data.customer_name,
            )
            logger.info(f"Заявка #{order_id} сохранена для пользователя {user.id}")

            task_message = OrderService._format_task(user, order_data, order_id)
            db.set_order_admin_text(order_id, task_message)
            all_admins = list(set(db.get_all_admins() + ADMIN_IDS))

            for admin_id in all_admins:
                try:
                    sent = await bot.send_message(
                        admin_id,
                        OrderService.with_status(task_message, "new"),
                        reply_markup=create_order_status_keyboard(order_id),
                    )
                    db.save_order_message(order_id, admin_id, sent.message_id)
                    logger.info(f"Заявка #{order_id} отправлена администратору {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки администратору {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка сохранения заявки: {e}")
        finally:
            if own_session:
                await bot.session.close()

    # Статус-метки анкеты для админов: сверху и снизу сообщения
    STATUS_MARKS = {
        "new":    "❓❓❓",
        "work":   "🕐🕐🕐",
        "done":   "✅✅✅",
        "cancel": "❌❌❌",
    }

    @staticmethod
    def with_status(text: str, status: str) -> str:
        mark = OrderService.STATUS_MARKS.get(status, OrderService.STATUS_MARKS["new"])
        return f"{mark}\n{text}\n{mark}"

    @staticmethod
    def _format_task(user: User, order_data, order_id: int) -> str:
        flash = order_data.flashlight.strip()
        if "С фонарём" in flash and order_data.flashlight_model:
            flash = f"{flash} ({order_data.flashlight_model})"

        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        return (
            f"📋 НОВАЯ ЗАЯВКА #{order_id}\n\n"
            f"👤 Клиент: {user.first_name or '—'} ({username})\n"
            f"🔫 Пистолет: {order_data.pistol_brand} {order_data.pistol_model}\n"
            f"🔒 Тип кобуры: {order_data.holster_type}\n"
            f"🔦 Фонарь: {flash}\n"
            f"🎨 Цвет: {order_data.color}\n"
            f"🏙 Город: {order_data.city}\n"
            f"📛 Имя: {order_data.customer_name}\n\n"
            f"🕐 {now}"
        )
