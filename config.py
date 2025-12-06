from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

storage = MemoryStorage()

# ========== НАСТРОЙКИ СИСТЕМЫ ==========
class Settings:
    # Значения по умолчанию (будут переопределены из БД при старте)
    DAILY_BUDGET = 400  # Бюджет на обед
    ORDER_DEADLINE_HOUR = 22  # 22:00 - дедлайн заказов на завтра
    NOTIFICATION_HOUR = 22  # 22:00 - отправка заказов менеджеру
    REGISTRATION_PASSWORD = "office123"  # Пароль для регистрации
    
    # Проверка рабочего дня (0=Понедельник, 6=Воскресенье)
    WORKING_DAYS = [0, 1, 2, 3, 4]  # Пн-Пт

# ========== СОСТОЯНИЯ FSM ==========
class AuthStates(StatesGroup):
    """Состояния для процесса регистрации"""
    waiting_for_password = State()  # Ожидание ввода пароля
    waiting_for_name = State()      # Ожидание ввода ФИО
    waiting_for_office = State()    # Ожидание выбора офиса

class OrderStates(StatesGroup):
    """Состояния для процесса заказа"""
    selecting_restaurant = State()  # Выбор ресторана
    selecting_dishes = State()      # Выбор блюд из меню
    confirming_order = State()      # Подтверждение заказа
    adding_extra_money = State()    # Добавление своих денег

class ManagerStates(StatesGroup):
    """Состояния для действий менеджера"""
    adding_restaurant = State()            # Добавление нового ресторана
    adding_menu_item = State()             # Добавление блюда в меню
    setting_password = State()             # Изменение пароля регистрации
    setting_budget = State()               # Изменение бюджета
    sending_delivery_notification = State()  # Уведомление о доставке
    editing_menu = State()                 # Редактирование меню (импорт текста)
    setting_deadline = State()             # Установка времени дедлайна

# ========== СПИСКИ И СЛОВАРИ ==========

# Офисы для выбора при регистрации
OFFICES = {
    'office1': '🏢 Петровская 6',
    'office2': '🏢 Ленина 25',
    'office3': '🏢 Центральная 1',
    'office4': '🏢 Гагарина 15',
    'office5': '🏢 Советская 42'
}

# Роли пользователей
ROLES = {
    'manager': '👑 Менеджер',
    'employee': '👤 Сотрудник',
    'pending': '⏳ Ожидает регистрации'
}

# Типы доставки (для расширения функционала)
DELIVERY_TYPES = {
    'office': '🏢 Доставка в офис',
    'pickup': '🚶‍♂️ Самовывоз из ресторана',
    'courier': '🚚 Курьерская доставка'
}

# Временные слоты для доставки
TIME_SLOTS = {
    '12:00': '🕛 12:00-12:30',
    '12:30': '🕧 12:30-13:00',
    '13:00': '🕐 13:00-13:30',
    '13:30': '🕜 13:30-14:00'
}