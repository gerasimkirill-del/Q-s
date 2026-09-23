"""
Конфигурация бота Q Holsters
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Актуальная версия — история изменений в CHANGELOG.md
VERSION = "2.0.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Папка data — постоянное хранилище (на BotHost сохраняется между обновлениями)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Перенос БД из старого места (корень проекта) в data/ — чтобы не потерять заявки
_old_db = os.path.join(BASE_DIR, "holsters_bot.db")
_new_db = os.path.join(DATA_DIR, "holsters_bot.db")
if os.path.exists(_old_db) and not os.path.exists(_new_db):
    os.replace(_old_db, _new_db)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8926714896:AAElSwGcWDQG8btxuPyIDHLiteI9nxgzLRM")

DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(DATA_DIR, "holsters_bot.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE") or os.path.join(DATA_DIR, "bot.log")

MAX_TEXT_LENGTH = 50

# Встроенные администраторы — активны всегда, удалить из меню нельзя.
# Дополнительных админов добавляют через /admin → «Администраторы».
PRESET_ADMINS = {
    "Kirill": 838603680,
    "Dima": 1326598195,
}
ADMIN_IDS: list[int] = list(PRESET_ADMINS.values())

# Антиспам по умолчанию (дальше меняется в /admin → «Антиспам», хранится в БД)
SPAM_MAX_FORMS = 3
SPAM_WINDOW_SECONDS = 300      # анкеты: 3 шт. за 5 минут
SPAM_MAX_QUESTIONS = 3
SPAM_QUESTION_WINDOW_SECONDS = 300  # вопросы вне анкеты: 3 шт. за 5 минут

# Стартовый каталог. Используется только для первичного заполнения БД,
# дальше модели редактируются в /admin → «Редактирование моделей».
PISTOL_BRANDS = {
    "Grand Power": ["T11", "T12", "TQ1", "TQ2"],
    "Glock":       ["G19", "G17"],
    "Sig Sauer P226": ["Standard"],
    "Пистолет Ярыгина": ["ПЯ", "Викинг", "MP-353", "MP-356"],
    "Гроза":       ["01", "02", "04"],
    "ПМ":          ["Классический", "ПМ-Pro"],
    "Тень-37":     ["Standard"],
    "ПЛК":         ["Standard"],
}

# Марки, для которых шаг выбора фонаря пропускается
NO_FLASHLIGHT_BRANDS = ["Гроза"]

FLASHLIGHT_OPTIONS = ["С фонарём", "Без фонаря"]
COLORS = ["Black", "Olive", "Coyote"]

MESSAGES = {
    "start": (
        'Добро пожаловать в «Q» Holsters!\n'
        'Чтобы оформить заказ, нажмите кнопку ниже.'
    ),
    "choose_brand":          "Выберите марку пистолета:",
    "choose_model":          "Выберите модель:",
    "enter_custom_brand":    "Введите марку пистолета:",
    "enter_custom_model":    "Введите модель пистолета:",
    "choose_holster_type":   "Выберите тип кобуры:",
    "choose_flashlight":     "Кобура с фонарём или без?",
    "enter_flashlight_model":"Введите модель фонаря:",
    "choose_color":          "Выберите цвет кобуры:",
    "enter_city":            "Введите ваш город (например, «Москва»):",
    "enter_name":            "Введите ваше имя:",
    "invalid_input":         "Некорректный ввод. Пожалуйста, попробуйте ещё раз.",
    "submitted":             "Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.",
    "cancelled":             "Отменено. Нажмите /start, чтобы начать заново.",
    "spam_warning":          (
        "Ну вот зачем ты это делаешь? "
        "Если тебе скучно, напиши мне в личку, пообщаемся!"
    ),
    "banned":                "Вы заблокированы и не можете оставлять заявки.",
    "question_prompt":       (
        "Если у вас есть дополнительные вопросы, "
        "пожалуйста, кратко изложите их, и мы свяжемся с вами для обсуждения."
    ),
    "ask_prompt":            "Изложите свой вопрос, мы обязательно свяжемся с вами.",
    "question_confirm":      "Вы уверены что хотите задать этот вопрос?",
    "question_sent":         "Ваш вопрос отправлен. Спасибо!",
}
