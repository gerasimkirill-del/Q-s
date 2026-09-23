"""
FSM-состояния для оформления заказа
"""
from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    choose_brand = State()
    enter_custom_brand = State()
    choose_model = State()
    enter_custom_model = State()
    choose_holster_type = State()
    choose_flashlight = State()
    enter_flashlight_model = State()
    choose_color = State()
    enter_city = State()
    enter_name = State()
    confirm = State()


class AdminForm(StatesGroup):
    ban_user_id = State()       # ввод ID для добавления в ЧС
    add_admin_id = State()      # ввод ID нового администратора
    pistol_template = State()   # ожидание заполненного шаблона модели
