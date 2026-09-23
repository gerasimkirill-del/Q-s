"""
Клавиатуры и вспомогательные функции
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List


def create_inline_keyboard(items: List[str], callback_prefix: str,
                           add_back: bool = False, back_callback: str = "back") -> InlineKeyboardMarkup:
    """Создать инлайн-клавиатуру. Если add_back=True — добавить кнопку «Назад»."""
    buttons = []
    seen = set()
    for item in items:
        clean_item = item.strip()
        if clean_item in seen:  # на одном экране не должно быть одинаковых кнопок
            continue
        seen.add(clean_item)
        buttons.append(
            InlineKeyboardButton(
                text=item,
                callback_data=f"{callback_prefix}:{clean_item}"
            )
        )

    keyboard = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])

    if add_back:
        keyboard.append([InlineKeyboardButton(text="← Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения заявки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="confirm:yes"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="confirm:edit"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_name")],
    ])


def create_question_confirm_keyboard() -> InlineKeyboardMarkup:
    """«Да / Нет» для подтверждения вопроса вне анкеты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да", callback_data="ask:yes"),
        InlineKeyboardButton(text="Нет", callback_data="ask:no"),
    ]])


def create_order_status_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопки статуса под анкетой (видят только админы)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Готово", callback_data=f"ost:done:{order_id}"),
        InlineKeyboardButton(text="Отмена", callback_data=f"ost:cancel:{order_id}"),
        InlineKeyboardButton(text="В работу", callback_data=f"ost:work:{order_id}"),
    ]])


def parse_callback_data(callback_data: str, prefix: str) -> str:
    """Извлечь данные из callback."""
    if callback_data.startswith(prefix + ":"):
        return callback_data[len(prefix) + 1:]
    return ""


def validate_text_input(text: str, min_length: int = 1, max_length: int = 50) -> bool:
    """Проверить текстовый ввод."""
    if not text:
        return False
    text = text.strip()
    return min_length <= len(text) <= max_length
