"""
Обработчики заказов с кнопками «Назад», антиспамом и баном
"""
import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (MESSAGES, FLASHLIGHT_OPTIONS, COLORS,
                    MAX_TEXT_LENGTH, SPAM_MAX_FORMS, SPAM_WINDOW_SECONDS,
                    SPAM_MAX_QUESTIONS, SPAM_QUESTION_WINDOW_SECONDS)
from models.database import Database
from utils.states import OrderForm
from utils.keyboard import (create_inline_keyboard, create_confirm_keyboard,
                             create_question_confirm_keyboard,
                             parse_callback_data, validate_text_input)

logger = logging.getLogger(__name__)
router = Router()
db = Database()


def is_admin(user_id: int) -> bool:
    from config import ADMIN_IDS
    return user_id in ADMIN_IDS or db.is_admin(user_id)


def pistol_brands() -> dict:
    """Актуальный каталог из БД: {марка: [модели]} (редактируется в админ-меню)."""
    return {p["brand"]: p["models"] for p in db.get_pistols()}


def brand_has_flashlight(brand: str) -> bool:
    p = db.get_pistol(brand)
    return p["has_flashlight"] if p else True  # «Прочее»/ручной ввод — с выбором фонаря


# ─── вспомогательные функции навигации ────────────────────────────────────────

async def show_brand_step(target, state: FSMContext, edit: bool = True):
    await state.set_state(OrderForm.choose_brand)
    brands = list(pistol_brands().keys()) + ["Прочее"]
    keyboard = create_inline_keyboard(brands, "brand")
    text = MESSAGES["choose_brand"]
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_model_step(target, state: FSMContext, brand: str, edit: bool = True):
    await state.set_state(OrderForm.choose_model)
    models = list(pistol_brands().get(brand, [])) + ["Прочее"]
    keyboard = create_inline_keyboard(models, "model", add_back=True, back_callback="back_to_brand")
    text = MESSAGES["choose_model"]
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_holster_step(target, state: FSMContext, edit: bool = True):
    await state.set_state(OrderForm.choose_holster_type)
    holster_types = ["Скрытая", "Поясная"]
    keyboard = create_inline_keyboard(holster_types, "holster_type",
                                      add_back=True, back_callback="back_to_brand")
    text = MESSAGES["choose_holster_type"]
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_flashlight_step(target, state: FSMContext, edit: bool = True):
    await state.set_state(OrderForm.choose_flashlight)
    keyboard = create_inline_keyboard(FLASHLIGHT_OPTIONS, "flashlight",
                                      add_back=True, back_callback="back_to_holster")
    text = MESSAGES["choose_flashlight"]
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_color_step(target, state: FSMContext, edit: bool = True):
    await state.set_state(OrderForm.choose_color)
    data = await state.get_data()
    brand = data.get("order_data", {}).get("pistol_brand", "")
    back_cb = "back_to_flashlight" if brand_has_flashlight(brand) else "back_to_holster"
    keyboard = create_inline_keyboard(COLORS, "color",
                                      add_back=True, back_callback=back_cb)
    text = MESSAGES["choose_color"]
    if edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_confirm_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    od = data.get("order_data", {})
    brand   = od.get("pistol_brand", "—")
    model   = od.get("pistol_model", "—")
    htype   = od.get("holster_type", "—")
    flash   = od.get("flashlight", "—")
    fmodel  = od.get("flashlight_model", "")
    color   = od.get("color", "—")
    city    = od.get("city", "—")
    name    = od.get("customer_name", "—")

    flash_str = flash
    if "С фонарём" in flash and fmodel:
        flash_str = f"{flash} ({fmodel})"

    text = (
        "Проверьте вашу заявку:\n\n"
        f"Пистолет: {brand} {model}\n"
        f"Тип кобуры: {htype}\n"
        f"Фонарь: {flash_str}\n"
        f"Цвет: {color}\n"
        f"Город: {city}\n"
        f"Имя: {name}\n\n"
        "Всё верно?"
    )
    await state.set_state(OrderForm.confirm)
    await callback.message.edit_text(text, reply_markup=create_confirm_keyboard())


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if db.is_banned(message.from_user.id):
        await message.answer(MESSAGES["banned"])
        return

    await state.clear()
    keyboard = create_inline_keyboard(["Начать"], "start_order")
    await message.answer(MESSAGES["start"], reply_markup=keyboard)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MESSAGES["cancelled"])


# ─── старт опроса ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "start_order:Начать")
async def step_choose_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(order_data={})
    await show_brand_step(callback, state)


# ─── марка ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("brand:"))
async def step_handle_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    brand = parse_callback_data(callback.data, "brand")

    data = await state.get_data()
    od = data.get("order_data", {})
    od["pistol_brand"] = brand
    await state.update_data(order_data=od)

    if brand == "Прочее":
        await state.set_state(OrderForm.enter_custom_brand)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_brand")]
        ])
        await callback.message.edit_text(MESSAGES["enter_custom_brand"], reply_markup=keyboard)
        return

    models = pistol_brands().get(brand, [])
    if len(models) == 1:
        od["pistol_model"] = models[0]
        await state.update_data(order_data=od)
        await show_holster_step(callback, state)
    else:
        await show_model_step(callback, state, brand)


@router.message(OrderForm.enter_custom_brand)
async def step_custom_brand(message: Message, state: FSMContext):
    if not validate_text_input(message.text, 1, MAX_TEXT_LENGTH):
        await message.answer(MESSAGES["invalid_input"])
        return
    data = await state.get_data()
    od = data.get("order_data", {})
    od["pistol_brand"] = message.text.strip()
    od["pistol_model"] = "Прочее"
    await state.update_data(order_data=od)
    await show_holster_step(message, state, edit=False)


# ─── модель ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("model:"))
async def step_after_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    model = parse_callback_data(callback.data, "model")

    data = await state.get_data()
    od = data.get("order_data", {})

    if model == "Прочее":
        await state.set_state(OrderForm.enter_custom_model)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_brand")]
        ])
        await callback.message.edit_text(MESSAGES["enter_custom_model"], reply_markup=keyboard)
        return

    od["pistol_model"] = model
    await state.update_data(order_data=od)
    await show_holster_step(callback, state)


@router.message(OrderForm.enter_custom_model)
async def step_custom_model(message: Message, state: FSMContext):
    if not validate_text_input(message.text, 1, MAX_TEXT_LENGTH):
        await message.answer(MESSAGES["invalid_input"])
        return
    data = await state.get_data()
    od = data.get("order_data", {})
    od["pistol_model"] = message.text.strip()
    await state.update_data(order_data=od)
    await show_holster_step(message, state, edit=False)


# ─── тип кобуры ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("holster_type:"))
async def step_after_holster(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    htype = parse_callback_data(callback.data, "holster_type")
    data = await state.get_data()
    od = data.get("order_data", {})
    od["holster_type"] = htype
    await state.update_data(order_data=od)
    if brand_has_flashlight(od.get("pistol_brand", "")):
        await show_flashlight_step(callback, state)
    else:
        # Для марок без фонаря (например, «Гроза») шаг фонаря пропускается
        od["flashlight"] = "Без фонаря"
        od["flashlight_model"] = ""
        await state.update_data(order_data=od)
        await show_color_step(callback, state)


# ─── фонарь ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("flashlight:"))
async def step_after_flashlight(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    flashlight = parse_callback_data(callback.data, "flashlight")
    data = await state.get_data()
    od = data.get("order_data", {})
    od["flashlight"] = flashlight
    await state.update_data(order_data=od)

    if "С фонарём" in flashlight:
        await state.set_state(OrderForm.enter_flashlight_model)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="back_to_flashlight")]
        ])
        await callback.message.edit_text(MESSAGES["enter_flashlight_model"], reply_markup=keyboard)
    else:
        od["flashlight_model"] = ""
        await state.update_data(order_data=od)
        await show_color_step(callback, state)


@router.message(OrderForm.enter_flashlight_model)
async def step_enter_flashlight(message: Message, state: FSMContext):
    if not validate_text_input(message.text, 1, MAX_TEXT_LENGTH):
        await message.answer(MESSAGES["invalid_input"])
        return
    data = await state.get_data()
    od = data.get("order_data", {})
    od["flashlight_model"] = message.text.strip()
    await state.update_data(order_data=od)
    await show_color_step(message, state, edit=False)


# ─── цвет ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("color:"))
async def step_choose_color(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    color = parse_callback_data(callback.data, "color")
    data = await state.get_data()
    od = data.get("order_data", {})
    od["color"] = color
    await state.update_data(order_data=od)

    await state.set_state(OrderForm.enter_city)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_color")]
    ])
    await callback.message.edit_text(MESSAGES["enter_city"], reply_markup=keyboard)


@router.message(OrderForm.enter_city)
async def step_enter_city(message: Message, state: FSMContext):
    if not validate_text_input(message.text, 1, MAX_TEXT_LENGTH):
        await message.answer(MESSAGES["invalid_input"])
        return
    data = await state.get_data()
    od = data.get("order_data", {})
    od["city"] = message.text.strip()
    await state.update_data(order_data=od)

    await state.set_state(OrderForm.enter_name)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_city")]
    ])
    await message.answer(MESSAGES["enter_name"], reply_markup=keyboard)


@router.message(OrderForm.enter_name)
async def step_enter_name(message: Message, state: FSMContext):
    if not validate_text_input(message.text, 1, MAX_TEXT_LENGTH):
        await message.answer(MESSAGES["invalid_input"])
        return
    data = await state.get_data()
    od = data.get("order_data", {})
    od["customer_name"] = message.text.strip()
    await state.update_data(order_data=od)

    # Показать подтверждение через фейковый callback-подобный объект
    await state.set_state(OrderForm.confirm)

    flash_str = od.get("flashlight", "—")
    fmodel = od.get("flashlight_model", "")
    if "С фонарём" in flash_str and fmodel:
        flash_str = f"{flash_str} ({fmodel})"

    text = (
        "Проверьте вашу заявку:\n\n"
        f"Пистолет: {od.get('pistol_brand','—')} {od.get('pistol_model','—')}\n"
        f"Тип кобуры: {od.get('holster_type','—')}\n"
        f"Фонарь: {flash_str}\n"
        f"Цвет: {od.get('color','—')}\n"
        f"Город: {od.get('city','—')}\n"
        f"Имя: {od.get('customer_name','—')}\n\n"
        "Всё верно?"
    )
    await message.answer(text, reply_markup=create_confirm_keyboard())


# ─── подтверждение ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "confirm:yes")
async def step_confirm_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = callback.from_user

    # Антиспам
    max_forms = db.get_setting("spam_max_forms", SPAM_MAX_FORMS)
    window = db.get_setting("spam_window_seconds", SPAM_WINDOW_SECONDS)
    count = db.get_form_count(user.id, window)
    if count >= max_forms:
        await callback.message.edit_text(MESSAGES["spam_warning"])
        # Уведомить админов
        from config import ADMIN_IDS
        all_admins = list(set(db.get_all_admins() + ADMIN_IDS))
        spam_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Пусть живёт", callback_data=f"spam_forgive:{user.id}"),
            InlineKeyboardButton(text="БАН",         callback_data=f"spam_ban:{user.id}"),
        ]])
        display = f"@{user.username}" if user.username else (user.first_name or str(user.id))
        for admin_id in all_admins:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"У нас завёлся засранец-спамер, ну или оружейный барон: {user.id} ({display})",
                    reply_markup=spam_kb
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")
        await state.clear()
        return

    data = await state.get_data()
    od = data.get("order_data", {})

    from services.order_service import OrderService

    class _OD:
        pass

    order_obj = _OD()
    order_obj.pistol_brand     = od.get("pistol_brand", "")
    order_obj.pistol_model     = od.get("pistol_model", "")
    order_obj.holster_type     = od.get("holster_type", "")
    order_obj.flashlight       = od.get("flashlight", "")
    order_obj.flashlight_model = od.get("flashlight_model", "")
    order_obj.color            = od.get("color", "")
    order_obj.city             = od.get("city", "")
    order_obj.customer_name    = od.get("customer_name", "")

    db.log_form(user.id)
    await OrderService.save_and_notify(user, order_obj, bot=callback.bot)

    # Вопрос о дополнениях — без кнопок: любой текст дальше уходит в поток вопросов
    await state.clear()
    await callback.message.edit_text(
        MESSAGES["submitted"] + "\n\n" + MESSAGES["question_prompt"]
    )


@router.callback_query(F.data == "confirm:edit")
async def step_confirm_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_brand_step(callback, state)


# ─── кнопки «Назад» ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_brand")
async def back_to_brand(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    # Сбросить всё начиная с марки
    data = await state.get_data()
    od = data.get("order_data", {})
    for key in ["pistol_brand","pistol_model","holster_type","flashlight","flashlight_model","color","city","customer_name"]:
        od.pop(key, None)
    await state.update_data(order_data=od)
    await show_brand_step(callback, state)


@router.callback_query(F.data == "back_to_holster")
async def back_to_holster(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    od = data.get("order_data", {})
    for key in ["holster_type","flashlight","flashlight_model","color","city","customer_name"]:
        od.pop(key, None)
    await state.update_data(order_data=od)
    await show_holster_step(callback, state)


@router.callback_query(F.data == "back_to_flashlight")
async def back_to_flashlight(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    od = data.get("order_data", {})
    for key in ["flashlight","flashlight_model","color","city","customer_name"]:
        od.pop(key, None)
    await state.update_data(order_data=od)
    await show_flashlight_step(callback, state)


@router.callback_query(F.data == "back_to_color")
async def back_to_color(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    od = data.get("order_data", {})
    for key in ["color","city","customer_name"]:
        od.pop(key, None)
    await state.update_data(order_data=od)
    await show_color_step(callback, state)


@router.callback_query(F.data == "back_to_city")
async def back_to_city(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    od = data.get("order_data", {})
    for key in ["city","customer_name"]:
        od.pop(key, None)
    await state.update_data(order_data=od)

    await state.set_state(OrderForm.enter_city)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_color")]
    ])
    await callback.message.edit_text(MESSAGES["enter_city"], reply_markup=keyboard)


@router.callback_query(F.data == "back_to_name")
async def back_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    od = data.get("order_data", {})
    od.pop("customer_name", None)
    await state.update_data(order_data=od)

    await state.set_state(OrderForm.enter_name)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_city")]
    ])
    await callback.message.edit_text(MESSAGES["enter_name"], reply_markup=keyboard)


@router.callback_query(F.data == "back_to_confirm")
async def back_to_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_confirm_step(callback, state)


# ─── решения админа по спамеру ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("spam_forgive:"))
async def spam_forgive(callback: CallbackQuery):
    await callback.answer("Пользователь помилован.")
    uid = int(callback.data.split(":")[1])
    await callback.message.edit_text(f"Пользователь {uid} помилован.")


@router.callback_query(F.data.startswith("spam_ban:"))
async def spam_ban(callback: CallbackQuery):
    await callback.answer("Пользователь заблокирован.")
    uid = int(callback.data.split(":")[1])
    db.ban_user(uid, str(uid))
    await callback.message.edit_text(f"Пользователь {uid} заблокирован.")


# ─── вопросы вне анкеты ─────────────────────────────────────────────────────

@router.message(Command("ask"))
async def cmd_ask(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MESSAGES["ask_prompt"])


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def question_outside_form(message: Message, state: FSMContext):
    """Любой текст вне заполнения анкеты: цитируем и просим подтвердить."""
    if db.is_banned(message.from_user.id):
        await message.answer(MESSAGES["banned"])
        return
    text = message.text.strip()
    if not validate_text_input(text, 1, 1000):
        await message.answer(MESSAGES["invalid_input"])
        return

    sent = await message.answer(
        f"<blockquote>{html.escape(text)}</blockquote>\n\n{MESSAGES['question_confirm']}",
        parse_mode="HTML",
        reply_markup=create_question_confirm_keyboard(),
    )
    data = await state.get_data()
    pending = data.get("pending_questions", {})
    pending[str(sent.message_id)] = text
    await state.update_data(pending_questions=pending)


@router.callback_query(F.data == "ask:no")
async def question_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    pending = data.get("pending_questions", {})
    pending.pop(str(callback.message.message_id), None)
    await state.update_data(pending_questions=pending)
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "ask:yes")
async def question_send(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = callback.from_user
    data = await state.get_data()
    pending = data.get("pending_questions", {})
    text = pending.pop(str(callback.message.message_id), None)
    await state.update_data(pending_questions=pending)
    if not text:
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    # Антиспам вопросов (лимит и окно настраиваются в админ-меню)
    max_q = db.get_setting("spam_max_questions", SPAM_MAX_QUESTIONS)
    window = db.get_setting("spam_question_window_seconds", SPAM_QUESTION_WINDOW_SECONDS)
    if db.get_question_count(user.id, window) >= max_q:
        await callback.message.edit_text(MESSAGES["spam_warning"])
        return

    from services.message_service import MessageService
    db.log_question(user.id)
    await MessageService.send_question_to_admins(user, text, bot=callback.bot)
    await callback.message.edit_text(MESSAGES["question_sent"])
