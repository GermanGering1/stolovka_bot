from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import OFFICES

db = Database()

def get_main_menu(role: str) -> ReplyKeyboardMarkup:
    """Главное меню по роли"""
    keyboard = []
    
    if role == 'manager':
        keyboard.append([KeyboardButton(text="👥 Управление пользователями")])
        keyboard.append([KeyboardButton(text="🏪 Управление ресторанами")])
        keyboard.append([KeyboardButton(text="📋 Управление меню")])
        keyboard.append([KeyboardButton(text="⚙️ Настройки системы")])
        keyboard.append([KeyboardButton(text="📊 Получить заказы")])
        keyboard.append([KeyboardButton(text="🚚 Уведомить о доставке")])
    
    keyboard.append([KeyboardButton(text="🍽️ Сделать заказ")])
    keyboard.append([KeyboardButton(text="📜 Мои заказы")])
    keyboard.append([KeyboardButton(text="ℹ️ Информация")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_office_selection_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора офиса при регистрации"""
    keyboard = []
    row = []
    
    for i, (key, value) in enumerate(OFFICES.items()):
        button = KeyboardButton(text=value)
        row.append(button)
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_restaurants_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для выбора ресторана"""
    restaurants = db.get_restaurants(active_only=True)
    
    keyboard = []
    row = []
    
    for i, restaurant in enumerate(restaurants):
        restaurant_id, name, description, is_active = restaurant
        button = InlineKeyboardButton(text=f"🏪 {name}", callback_data=f"rest_{restaurant_id}")
        row.append(button)
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton(text="📭 Нет доступных ресторанов", callback_data="no_restaurants")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_menu_keyboard(restaurant_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура с меню ресторана"""
    menu_items = db.get_menu_for_restaurant(restaurant_id, available_only=True)
    
    # Пагинация (по 8 items на страницу)
    items_per_page = 8
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_items = menu_items[start_idx:end_idx]
    
    keyboard = []
    
    for item in page_items:
        item_id, name, price, description, is_available = item
        button_text = f"{name} - {price}₽"
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"item_{item_id}_{page}")])
    
    # Кнопки навигации
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data=f"menu_page_{restaurant_id}_{page-1}"
        ))
    
    nav_buttons.append(InlineKeyboardButton(
        text=f"📄 {page + 1}/{(len(menu_items) + items_per_page - 1) // items_per_page}", 
        callback_data="current"
    ))
    
    if end_idx < len(menu_items):
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️", 
            callback_data=f"menu_page_{restaurant_id}_{page+1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton(text="🛒 Показать корзину", callback_data=f"cart_{restaurant_id}"),
        InlineKeyboardButton(text="✅ Завершить", callback_data=f"finish_{restaurant_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад к ресторанам", callback_data="back_to_restaurants")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cart_keyboard(restaurant_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления корзиной"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еще", callback_data=f"add_more_{restaurant_id}")],
        [InlineKeyboardButton(text="✏️ Изменить заказ", callback_data=f"edit_cart_{restaurant_id}")],
        [InlineKeyboardButton(text="🗑️ Очистить корзину", callback_data=f"clear_cart_{restaurant_id}")],
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data=f"checkout_{restaurant_id}")]
    ])

def get_order_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения заказа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")]
    ])

def get_extra_money_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для добавления своих денег"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 +50₽", callback_data="extra_50"),
            InlineKeyboardButton(text="💵 +100₽", callback_data="extra_100"),
            InlineKeyboardButton(text="💵 +200₽", callback_data="extra_200")
        ],
        [
            InlineKeyboardButton(text="💵 +500₽", callback_data="extra_500"),
            InlineKeyboardButton(text="✏️ Другая сумма", callback_data="extra_custom")
        ],
        [InlineKeyboardButton(text="🚫 Не добавлять", callback_data="extra_none")]
    ])

def get_manager_restaurants_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора ресторана менеджером"""
    restaurants = db.get_restaurants()
    
    keyboard = []
    for restaurant in restaurants:
        restaurant_id, name, description, is_active = restaurant
        status = "✅" if is_active else "❌"
        button = InlineKeyboardButton(
            text=f"{status} {name}", 
            callback_data=f"mgr_rest_{restaurant_id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="➕ Добавить ресторан", callback_data="add_restaurant")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )