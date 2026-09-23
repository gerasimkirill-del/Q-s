"""
Админ-панель: интерактивное меню /admin (ЧС, антиспам, модели, админы, актуальные анкеты),
статусы анкет, а также старые команды /bans, /add_admin, /remove_admin, /list_admins
(работают, но в меню команд не показываются).
"""
import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyParameters
from aiogram.exceptions import TelegramBadRequest

import config
from models.database import Database
from services.order_service import OrderService
from services.bot_commands import set_admin_commands, reset_commands
from utils.keyboard import create_order_status_keyboard
from utils.states import AdminForm

logger = logging.getLogger(__name__)
router = Router()
db = Database()


def is_admin(user_id: int) -> bool:
    from config import ADMIN_IDS
    return user_id in ADMIN_IDS or db.is_admin(user_id)


# ─── /bans ────────────────────────────────────────────────────────────────────

@router.message(Command("bans"))
async def cmd_bans(message: Message):
    if not is_admin(message.from_user.id):
        return

    banned = db.get_banned_users()
    if not banned:
        await message.answer("Забаненных пользователей нет.")
        return

    buttons = []
    for u in banned:
        label = u["user_name"] or str(u["user_id"])
        buttons.append([
            InlineKeyboardButton(
                text=f"🔓 Разбанить {label}",
                callback_data=f"unban:{u['user_id']}"
            )
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Список заблокированных пользователей:", reply_markup=kb)


@router.callback_query(F.data.startswith("unban:"))
async def cb_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return

    uid = int(callback.data.split(":")[1])
    if db.unban_user(uid):
        await callback.answer(f"Пользователь {uid} разблокирован.")
        logger.info(f"Admin {callback.from_user.id} unbanned {uid}")
        # Обновить список
        banned = db.get_banned_users()
        if not banned:
            await callback.message.edit_text("Забаненных пользователей нет.")
            return
        buttons = []
        for u in banned:
            label = u["user_name"] or str(u["user_id"])
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔓 Разбанить {label}",
                    callback_data=f"unban:{u['user_id']}"
                )
            ])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("Список заблокированных пользователей:", reply_markup=kb)
    else:
        await callback.answer("Пользователь не найден.", show_alert=True)


# ─── управление администраторами ──────────────────────────────────────────────

@router.message(Command("add_admin"))
async def add_admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /add_admin <ID>")
        return
    try:
        admin_id = int(args[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    if db.add_admin(admin_id):
        await set_admin_commands(message.bot, admin_id)
        await message.answer(f"Администратор {admin_id} добавлен.")
    else:
        await message.answer(f"Администратор {admin_id} уже существует.")


@router.message(Command("remove_admin"))
async def remove_admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /remove_admin <ID>")
        return
    try:
        admin_id = int(args[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    if db.remove_admin(admin_id):
        await message.answer(f"Администратор {admin_id} удалён.")
    else:
        await message.answer(f"Администратор {admin_id} не найден.")


@router.message(Command("list_admins"))
async def list_admins_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    admins = db.get_all_admins()
    if not admins:
        await message.answer("Администраторов нет.")
        return
    text = "\n".join([f"{i+1}. {aid}" for i, aid in enumerate(admins)])
    await message.answer(f"Администраторы:\n\n{text}")


# ═══════════════════════════ ИНТЕРАКТИВНОЕ АДМИН-МЕНЮ (/admin) ═══════════════════════════

def all_admin_ids() -> list[int]:
    return list(dict.fromkeys(config.ADMIN_IDS + db.get_all_admins()))


def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Короткая сборка клавиатуры: [[(текст, callback), ...], ...]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows
    ])


BACK_TO_MENU = [("← Назад", "adm:menu")]


def admin_menu_kb() -> InlineKeyboardMarkup:
    return kb([
        [("Актуальные анкеты", "adm:orders")],
        [("Редактирование моделей", "adm:pistols")],
        [("Чёрный список", "adm:bans")],
        [("Антиспам", "adm:spam")],
        [("Администраторы", "adm:admins")],
    ])


async def safe_edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup = None):
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(f"Меню администратора (v{config.VERSION})", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.clear()
    await callback.answer()
    await safe_edit(callback, f"Меню администратора (v{config.VERSION})", admin_menu_kb())


# ─── актуальные анкеты и статусы ─────────────────────────────────────────────

def order_admin_text(order: dict) -> str:
    """Текст анкеты для админов (сохранённый при отправке либо собранный из БД)."""
    if order.get("admin_text"):
        return order["admin_text"]
    username = f"@{order['user_username']}" if order.get("user_username") else f"ID: {order['user_id']}"
    return (
        f"📋 НОВАЯ ЗАЯВКА #{order['id']}\n\n"
        f"👤 Клиент: {order.get('user_name') or '—'} ({username})\n"
        f"🔫 Пистолет: {order['pistol_model']}\n"
        f"🔒 Тип кобуры: {order['holster_type']}\n"
        f"🔦 Фонарь: {order['flashlight']}\n"
        f"🎨 Цвет: {order['color']}\n"
        f"🏙 Город: {order['city']}\n"
        f"📛 Имя: {order['customer_name']}\n\n"
        f"🕐 {order['created_at']}"
    )


@router.callback_query(F.data == "adm:orders")
async def cb_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await callback.answer()
    orders = db.get_active_orders()[:20]
    if not orders:
        return await safe_edit(callback, "Актуальных анкет нет.", kb([BACK_TO_MENU]))

    lines = ["<b>Актуальные анкеты</b> (нажмите на цитату под списком — откроется исходная анкета):", ""]
    for o in orders:
        mark = OrderService.STATUS_MARKS.get(o.get("status") or "new")[0]
        lines.append(f"{mark} #{o['id']} — {html.escape(o['pistol_model'])} "
                     f"({html.escape(o['customer_name'])}, {html.escape(o['city'])})")
    await safe_edit(callback, "\n".join(lines), kb([BACK_TO_MENU]))

    chat_id = callback.message.chat.id
    for o in reversed(orders):
        status = o.get("status") or "new"
        original = next((m for m in db.get_order_messages(o["id"]) if m["chat_id"] == chat_id), None)
        reply = (ReplyParameters(message_id=original["message_id"], allow_sending_without_reply=True)
                 if original else None)
        sent = await callback.message.answer(
            OrderService.with_status(order_admin_text(o), status),
            reply_markup=create_order_status_keyboard(o["id"]),
            reply_parameters=reply,
        )
        db.save_order_message(o["id"], chat_id, sent.message_id)


@router.callback_query(F.data.startswith("ost:"))
async def cb_order_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    _, status, order_id = callback.data.split(":")
    order_id = int(order_id)
    order = db.get_order(order_id)
    if not order:
        return await callback.answer("Анкета не найдена.", show_alert=True)

    db.set_order_status(order_id, status)
    text = OrderService.with_status(order_admin_text(order), status)
    markup = create_order_status_keyboard(order_id)
    # обновляем анкету у всех админов (и все её копии из списка)
    targets = db.get_order_messages(order_id)
    if not any(t["message_id"] == callback.message.message_id for t in targets):
        targets.append({"chat_id": callback.message.chat.id, "message_id": callback.message.message_id})
    for t in targets:
        try:
            await callback.bot.edit_message_text(text, chat_id=t["chat_id"], message_id=t["message_id"],
                                                 reply_markup=markup)
        except TelegramBadRequest:
            pass
    labels = {"done": "Готово", "cancel": "Отмена", "work": "В работу"}
    await callback.answer(labels.get(status, status))
    logger.info(f"Admin {callback.from_user.id}: заявка #{order_id} → {status}")


# ─── чёрный список ───────────────────────────────────────────────────────────

def bans_view():
    banned = db.get_banned_users()
    rows = [[(f"🔓 Разбанить {u['user_name'] or u['user_id']}", f"adm:unban:{u['user_id']}")] for u in banned]
    rows.append([("Добавить в ЧС", "adm:ban_add")])
    rows.append(BACK_TO_MENU)
    text = "Список заблокированных пользователей:" if banned else "Забаненных пользователей нет."
    return text, kb(rows)


@router.callback_query(F.data == "adm:bans")
async def cb_bans(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.clear()
    await callback.answer()
    await safe_edit(callback, *bans_view())


@router.callback_query(F.data.startswith("adm:unban:"))
async def cb_menu_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    uid = int(callback.data.split(":")[2])
    db.unban_user(uid)
    logger.info(f"Admin {callback.from_user.id} unbanned {uid}")
    await callback.answer(f"Пользователь {uid} разблокирован.")
    await safe_edit(callback, *bans_view())


@router.callback_query(F.data == "adm:ban_add")
async def cb_ban_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.set_state(AdminForm.ban_user_id)
    await callback.answer()
    await safe_edit(callback, "Отправьте Telegram ID пользователя для блокировки:",
                    kb([[("← Назад", "adm:bans")]]))


@router.message(AdminForm.ban_user_id)
async def msg_ban_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await state.clear()
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        return await message.answer("Некорректный ID.")
    uid = int(raw)
    if uid in all_admin_ids():
        return await message.answer("Нельзя заблокировать администратора.")
    db.ban_user(uid, str(uid))
    await state.clear()
    await message.answer(f"Пользователь {uid} заблокирован.")
    text, markup = bans_view()
    await message.answer(text, reply_markup=markup)


# ─── антиспам ────────────────────────────────────────────────────────────────

SPAM_KEYS = {
    # тип: (ключ лимита, ключ окна, лимит по умолчанию, окно по умолчанию, название)
    "forms": ("spam_max_forms", "spam_window_seconds",
              config.SPAM_MAX_FORMS, config.SPAM_WINDOW_SECONDS, "Анкеты"),
    "questions": ("spam_max_questions", "spam_question_window_seconds",
                  config.SPAM_MAX_QUESTIONS, config.SPAM_QUESTION_WINDOW_SECONDS, "Вопросы вне анкеты"),
}
SPAM_MINUTES = [1, 5, 10, 30, 60]
SPAM_LIMITS = [1, 2, 3, 5, 10]


def spam_values(kind: str) -> tuple[int, int]:
    k_max, k_win, d_max, d_win, _ = SPAM_KEYS[kind]
    return db.get_setting(k_max, d_max), db.get_setting(k_win, d_win)


@router.callback_query(F.data == "adm:spam")
async def cb_spam(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await callback.answer()
    fm, fw = spam_values("forms")
    qm, qw = spam_values("questions")
    text = ("<b>Антиспам</b>\n\n"
            f"Анкеты: не больше {fm} шт. за {fw // 60} мин.\n"
            f"Вопросы вне анкеты: не больше {qm} шт. за {qw // 60} мин.\n\n"
            "Что настроить?")
    await safe_edit(callback, text, kb([
        [("Анкеты", "adm:spam:forms"), ("Вопросы", "adm:spam:questions")],
        BACK_TO_MENU,
    ]))


def spam_kind_view(kind: str):
    cur_max, cur_win = spam_values(kind)
    name = SPAM_KEYS[kind][4]
    text = (f"<b>Антиспам — {name}</b>\n\n"
            f"Сейчас: не больше {cur_max} шт. за {cur_win // 60} мин.\n\n"
            "Время ограничения (верхний ряд) и лимит (нижний ряд):")
    mark = lambda cond, t: f"• {t}" if cond else t
    rows = [
        [(mark(m * 60 == cur_win, f"{m} мин"), f"adm:spw:{kind}:{m}") for m in SPAM_MINUTES],
        [(mark(n == cur_max, f"{n} шт"), f"adm:spm:{kind}:{n}") for n in SPAM_LIMITS],
        [("← Назад", "adm:spam")],
    ]
    return text, kb(rows)


@router.callback_query(F.data.in_({"adm:spam:forms", "adm:spam:questions"}))
async def cb_spam_kind(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await callback.answer()
    await safe_edit(callback, *spam_kind_view(callback.data.split(":")[2]))


@router.callback_query(F.data.startswith("adm:spw:") | F.data.startswith("adm:spm:"))
async def cb_spam_set(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    _, what, kind, value = callback.data.split(":")
    k_max, k_win = SPAM_KEYS[kind][:2]
    if what == "spw":
        db.set_setting(k_win, int(value) * 60)
    else:
        db.set_setting(k_max, int(value))
    await callback.answer("Сохранено")
    await safe_edit(callback, *spam_kind_view(kind))


# ─── редактирование моделей ──────────────────────────────────────────────────

PISTOL_TEMPLATE_HELP = (
    "Скопируйте шаблон ниже (нажмите на него), измените под себя и отправьте одним сообщением.\n\n"
    "• <b>Марка</b> — название кнопки в анкете\n"
    "• <b>Модели</b> — через запятую; одна модель — шаг выбора модели пропускается\n"
    "• <b>Фонарь</b> — да / нет (нет — вопрос про фонарь не задаётся)\n"
    "• кнопка «Прочее» добавляется автоматически\n\n"
)


def pistol_template(p: dict = None) -> str:
    if not p:
        p = {"brand": "Название марки", "models": ["Модель 1", "Модель 2"], "has_flashlight": True}
    return (f"Марка: {p['brand']}\n"
            f"Модели: {', '.join(p['models'])}\n"
            f"Фонарь: {'да' if p['has_flashlight'] else 'нет'}")


def parse_pistol_template(text: str) -> tuple[dict | None, str | None]:
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
    brand = fields.get("марка", "")
    models_raw = fields.get("модели", fields.get("модель", ""))
    flash_raw = fields.get("фонарь", "да").lower()

    if not brand:
        return None, "Не указана «Марка»."
    if brand.lower() == "прочее":
        return None, "«Прочее» — служебное название, выберите другое."
    if len(f"brand:{brand}".encode()) > 64:
        return None, "Слишком длинное название марки (до ~28 символов)."
    models = list(dict.fromkeys(m.strip() for m in models_raw.split(",")
                                if m.strip() and m.strip().lower() != "прочее"))
    if not models:
        return None, "Укажите хотя бы одну модель в строке «Модели»."
    too_long = [m for m in models if len(f"model:{m}".encode()) > 64]
    if too_long:
        return None, f"Слишком длинные названия моделей: {', '.join(too_long)}"
    if flash_raw not in ("да", "нет"):
        return None, "В строке «Фонарь» напишите да или нет."
    return {"brand": brand, "models": models, "has_flashlight": flash_raw == "да"}, None


def pistols_view():
    pistols = db.get_pistols()
    rows = [[(p["brand"], f"adm:pe:{i}")] for i, p in enumerate(pistols)]
    rows.append([("Добавить новую модель", "adm:padd")])
    rows.append(BACK_TO_MENU)
    return "Выберите модель для редактирования или добавьте новую:", kb(rows)


@router.callback_query(F.data == "adm:pistols")
async def cb_pistols(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.clear()
    await callback.answer()
    await safe_edit(callback, *pistols_view())


async def ask_template(callback: CallbackQuery, state: FSMContext, pistol: dict = None):
    await state.set_state(AdminForm.pistol_template)
    await state.update_data(edit_brand=pistol["brand"] if pistol else None)
    title = f"Редактирование: <b>{html.escape(pistol['brand'])}</b>\n\n" if pistol else "Новая модель\n\n"
    rows = []
    if pistol:
        rows.append([("Удалить марку", "adm:pdel")])
    rows.append([("← Назад", "adm:pistols")])
    await safe_edit(callback,
                    title + PISTOL_TEMPLATE_HELP + f"<pre>{html.escape(pistol_template(pistol))}</pre>",
                    kb(rows))


@router.callback_query(F.data == "adm:padd")
async def cb_pistol_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await callback.answer()
    await ask_template(callback, state)


@router.callback_query(F.data.startswith("adm:pe:"))
async def cb_pistol_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    pistols = db.get_pistols()
    idx = int(callback.data.split(":")[2])
    if idx >= len(pistols):
        return await callback.answer("Модель не найдена, обновите список.", show_alert=True)
    await callback.answer()
    await ask_template(callback, state, pistols[idx])


@router.callback_query(F.data == "adm:pdel")
async def cb_pistol_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    brand = (await state.get_data()).get("edit_brand")
    if brand:
        db.delete_pistol(brand)
        logger.info(f"Admin {callback.from_user.id} удалил марку {brand}")
    await state.clear()
    await callback.answer("Удалено")
    await safe_edit(callback, *pistols_view())


@router.message(AdminForm.pistol_template)
async def msg_pistol_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await state.clear()
    pistol, error = parse_pistol_template(message.text)
    if error:
        return await message.answer(f"{error}\nИсправьте шаблон и отправьте ещё раз.")
    old_brand = (await state.get_data()).get("edit_brand")
    existing = db.get_pistol(pistol["brand"])
    if existing and pistol["brand"] != old_brand:
        return await message.answer("Марка с таким названием уже есть. Выберите её в списке для редактирования.")

    db.save_pistol(pistol["brand"], pistol["models"], pistol["has_flashlight"], old_brand=old_brand)
    await state.clear()
    logger.info(f"Admin {message.from_user.id} сохранил марку {pistol['brand']}: {pistol['models']}")
    await message.answer(
        f"Сохранено. Ветка уже доступна в анкете:\n<pre>{html.escape(pistol_template(pistol))}</pre>",
        parse_mode="HTML",
    )
    text, markup = pistols_view()
    await message.answer(text, reply_markup=markup)


# ─── администраторы ──────────────────────────────────────────────────────────

def admins_view():
    rows = []
    lines = ["<b>Администраторы</b>", ""]
    for aid in all_admin_ids():
        if aid in config.ADMIN_IDS:
            lines.append(f"• <code>{aid}</code> — встроенный")
        else:
            lines.append(f"• <code>{aid}</code>")
            rows.append([(f"Удалить {aid}", f"adm:adel:{aid}")])
    rows.append([("Добавить администратора", "adm:aadd")])
    rows.append(BACK_TO_MENU)
    return "\n".join(lines), kb(rows)


@router.callback_query(F.data == "adm:admins")
async def cb_admins(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.clear()
    await callback.answer()
    await safe_edit(callback, *admins_view())


@router.callback_query(F.data == "adm:aadd")
async def cb_admin_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    await state.set_state(AdminForm.add_admin_id)
    await callback.answer()
    await safe_edit(callback, "Отправьте Telegram ID нового администратора\n"
                              "(узнать ID можно у @userinfobot):", kb([[("← Назад", "adm:admins")]]))


@router.message(AdminForm.add_admin_id)
async def msg_admin_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await state.clear()
    raw = (message.text or "").strip()
    if not raw.isdigit():
        return await message.answer("Некорректный ID.")
    admin_id = int(raw)
    await state.clear()
    if db.add_admin(admin_id) or admin_id in config.ADMIN_IDS:
        await set_admin_commands(message.bot, admin_id)
        await message.answer(f"Администратор {admin_id} добавлен.")
    else:
        await message.answer(f"Администратор {admin_id} уже существует.")
    text, markup = admins_view()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("adm:adel:"))
async def cb_admin_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет прав.", show_alert=True)
    admin_id = int(callback.data.split(":")[2])
    if admin_id in config.ADMIN_IDS:
        return await callback.answer("Встроенного администратора удалить нельзя.", show_alert=True)
    db.remove_admin(admin_id)
    await reset_commands(callback.bot, admin_id)
    await callback.answer(f"Администратор {admin_id} удалён.")
    await safe_edit(callback, *admins_view())
