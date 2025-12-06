from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from database import Database
from config import ManagerStates
from keyboards.main_menus import (
    get_main_menu, 
    get_manager_restaurants_keyboard,
    get_cancel_keyboard
)
from filters.role_filter import ManagerFilter
from services.order_notifier import OrderNotifier
from services.delivery_notifier import DeliveryNotifier
from services.menu_scraper import MenuScraper
import json

router = Router()
db = Database()

@router.message(ManagerFilter(), F.text == "📊 Получить заказы")
async def get_orders_report(message: types.Message):
    """Получает отчет по заказам в нужном формате"""
    orders = db.get_all_orders_for_tomorrow()
    
    if not orders:
        await message.answer("📭 На завтра заказов нет")
        return
    
    # Группируем по ресторанам
    orders_by_restaurant = {}
    for order in orders:
        order_id, user_id, restaurant_id, order_data_json, total_price, extra_money, order_date, created_at, full_name, office, restaurant_name = order
        
        if restaurant_name not in orders_by_restaurant:
            orders_by_restaurant[restaurant_name] = []
        
        # Парсим JSON с заказом
        try:
            order_data = json.loads(order_data_json)
            orders_by_restaurant[restaurant_name].append({
                'full_name': full_name,
                'office': office,
                'order_data': order_data,
                'total_price': total_price,
                'extra_money': extra_money,
                'order_id': order_id
            })
        except:
            continue
    
    # Формируем отчет в нужном формате
    report = f"📋 <b>ЗАКАЗЫ НА ЗАВТРА</b>\n\n"
    
    for restaurant_name, restaurant_orders in orders_by_restaurant.items():
        report += f"<b>{restaurant_name}</b>\n"
        
        for order in restaurant_orders:
            report += f"- <b>{order['full_name']} ({order['office']}):</b>\n"
            
            # Выводим каждое блюдо
            item_num = 1
            for dish_name, dish_price in order['order_data'].items():
                report += f"  {item_num}. {dish_name}, {dish_price}Р\n"
                item_num += 1
            
            if order['extra_money'] > 0:
                report += f"  <i>Доплата со своих средств - {order['extra_money']}Р</i>\n"
            
            report += "\n"
        
        report += "\n"
    
    # Итоговая информация
    total_orders = len(orders)
    total_amount = sum(o[4] for o in orders)
    report += f"<b>ИТОГО:</b> {total_orders} заказов на {total_amount}Р\n"
    
    await message.answer(report, parse_mode='HTML')
    
    # Предлагаем пометить как отправленные
    if orders:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[[
                types.InlineKeyboardButton(
                    text="✅ Пометить как отправленные", 
                    callback_data="mark_orders_sent"
                )
            ]]
        )
        await message.answer(
            f"Заказы еще не отправлены менеджеру.\n"
            f"Отметить {len(orders)} заказов как отправленные?",
            reply_markup=keyboard
        )

@router.callback_query(F.data == "mark_orders_sent")
async def mark_orders_sent(callback_query: types.CallbackQuery):
    """Помечает заказы как отправленные"""
    orders = db.get_all_orders_for_tomorrow()
    order_ids = [o[0] for o in orders]
    
    if order_ids:
        success = db.mark_orders_as_sent(order_ids)
        
        if success:
            await callback_query.message.edit_text(
                f"✅ {len(order_ids)} заказов помечены как отправленные"
            )
        else:
            await callback_query.message.edit_text(
                "❌ Ошибка при обновлении статуса заказов"
            )
    else:
        await callback_query.message.edit_text("📭 Нет заказов для отправки")
    
    await callback_query.answer()

@router.message(ManagerFilter(), F.text == "🏪 Управление ресторанами")
async def manage_restaurants(message: types.Message):
    """Управление ресторанами"""
    await message.answer(
        "🏪 <b>Управление ресторанами</b>\n\n"
        "Выберите ресторан для управления:",
        reply_markup=get_manager_restaurants_keyboard(),
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("mgr_rest_"))
async def manage_specific_restaurant(callback_query: types.CallbackQuery):
    """Управление конкретным рестораном"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    if not restaurant:
        await callback_query.answer("❌ Ресторан не найден")
        return
    
    restaurant_id, name, description, is_active = restaurant
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="📋 Управление меню", 
                callback_data=f"mgr_menu_{restaurant_id}"
            ),
            types.InlineKeyboardButton(
                text="🚚 Уведомить о доставке", 
                callback_data=f"notify_delivery_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="✅ Активировать" if not is_active else "❌ Деактивировать", 
                callback_data=f"toggle_rest_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data="back_to_restaurants"
            )
        ]
    ])
    
    status = "✅ Активен" if is_active else "❌ Неактивен"
    
    await callback_query.message.edit_text(
        f"🏪 <b>{name}</b>\n"
        f"📝 {description or 'Без описания'}\n"
        f"📊 Статус: {status}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback_query.answer()

@router.callback_query(F.data.startswith("mgr_menu_"))
async def manage_restaurant_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Управление меню ресторана"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    await state.update_data(restaurant_id=restaurant_id)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="➕ Добавить блюдо вручную", 
                callback_data=f"add_manual_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="📝 Импорт из текста", 
                callback_data=f"import_text_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🤖 Авто-импорт (скрапинг)", 
                callback_data=f"scrape_menu_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="📋 Просмотреть меню", 
                callback_data=f"view_menu_{restaurant_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data=f"mgr_rest_{restaurant_id}"
            )
        ]
    ])
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    await callback_query.message.edit_text(
        f"📋 <b>Управление меню: {restaurant_name}</b>\n\n"
        f"Выберите способ добавления меню:",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback_query.answer()

@router.callback_query(F.data.startswith("add_manual_"))
async def add_manual_menu_item(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавление блюда вручную"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    await state.update_data(restaurant_id=restaurant_id)
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    await callback_query.message.edit_text(
        f"➕ <b>Добавление блюда в {restaurant_name}</b>\n\n"
        f"Введите название блюда и цену через запятую:\n"
        f"<i>Пример: Пицца Маргарита, 450</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.adding_menu_item)
    await callback_query.answer()

@router.message(ManagerStates.adding_menu_item, F.text)
async def process_menu_item(message: types.Message, state: FSMContext):
    """Обрабатывает добавление блюда"""
    if message.text == "❌ Отмена":
        await message.answer("Добавление отменено.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    try:
        text = message.text.strip()
        if ',' in text:
            parts = text.split(',')
            name = parts[0].strip()
            price = int(parts[1].strip().replace('₽', '').replace('р', '').replace('руб', '').strip())
        else:
            # Пробуем распарсить другой формат
            parts = text.split()
            if len(parts) >= 2:
                try:
                    price = int(parts[-1].replace('₽', '').replace('р', '').replace('руб', '').strip())
                    name = ' '.join(parts[:-1]).strip()
                except:
                    raise ValueError
            else:
                raise ValueError
        
        data = await state.get_data()
        restaurant_id = data['restaurant_id']
        
        # Добавляем блюдо
        success = db.add_menu_item(restaurant_id, name, price)
        
        if success:
            await message.answer(
                f"✅ Блюдо добавлено:\n"
                f"🍽 {name}\n"
                f"💵 {price}₽",
                reply_markup=types.ReplyKeyboardRemove()
            )
        else:
            await message.answer(
                "❌ Ошибка при добавлении блюда",
                reply_markup=types.ReplyKeyboardRemove()
            )
        
        # Предлагаем добавить еще
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="➕ Добавить еще", 
                    callback_data=f"add_manual_{restaurant_id}"
                ),
                types.InlineKeyboardButton(
                    text="🔙 В меню", 
                    callback_data=f"mgr_menu_{restaurant_id}"
                )
            ]
        ])
        
        await message.answer(
            "Что делаем дальше?",
            reply_markup=keyboard
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите:\n"
            "<i>Название блюда, цена</i>\n\n"
            "Пример: Пицца Маргарита, 450"
        )

@router.callback_query(F.data.startswith("import_text_"))
async def import_menu_from_text(callback_query: types.CallbackQuery, state: FSMContext):
    """Импорт меню из текста"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    await state.update_data(restaurant_id=restaurant_id)
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    await callback_query.message.edit_text(
        f"📝 <b>Импорт меню для {restaurant_name}</b>\n\n"
        f"Отправьте меню в формате:\n\n"
        f"<code>- позиция1, цена\n- позиция2, цена\n- позиция3, цена</code>\n\n"
        f"Или:\n"
        f"<code>позиция1 - цена\nпозиция2 - цена</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.editing_menu)
    await callback_query.answer()

@router.message(ManagerStates.editing_menu, F.text)
async def process_menu_import(message: types.Message, state: FSMContext):
    """Обрабатывает импорт меню"""
    if message.text == "❌ Отмена":
        await message.answer("Импорт отменен.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    data = await state.get_data()
    restaurant_id = data['restaurant_id']
    
    # Импортируем меню
    added, updated = db.import_menu_from_text(restaurant_id, message.text)
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    await message.answer(
        f"✅ <b>Меню импортировано для {restaurant_name}</b>\n\n"
        f"📊 Результат:\n"
        f"• Добавлено: {added} блюд\n"
        f"• Обновлено: {updated} блюд\n\n"
        f"Используйте 'Просмотреть меню' для проверки.",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode='HTML'
    )
    
    await state.clear()

@router.callback_query(F.data.startswith("scrape_menu_"))
async def scrape_menu(callback_query: types.CallbackQuery):
    """Скрапинг меню (мок)"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    if not restaurant:
        await callback_query.answer("❌ Ресторан не найден")
        return
    
    restaurant_name = restaurant[1]
    
    # Используем мок-скрапер
    added, updated, message = MenuScraper.import_scraped_menu(restaurant_id, restaurant_name)
    
    await callback_query.message.edit_text(
        f"🤖 <b>Скрапинг меню для {restaurant_name}</b>\n\n"
        f"{message}\n\n"
        f"<i>Это демонстрационная версия скрапинга.</i>",
        parse_mode='HTML'
    )
    await callback_query.answer()

@router.callback_query(F.data.startswith("view_menu_"))
async def view_restaurant_menu(callback_query: types.CallbackQuery):
    """Просмотр меню ресторана"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    menu_items = db.get_menu_for_restaurant(restaurant_id, available_only=False)
    
    if not menu_items:
        await callback_query.message.edit_text(
            "📭 Меню ресторана пустое.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="🔙 Назад", 
                        callback_data=f"mgr_menu_{restaurant_id}"
                    )
                ]]
            )
        )
        await callback_query.answer()
        return
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    menu_text = f"📋 <b>Меню: {restaurant_name}</b>\n\n"
    
    for item in menu_items:
        item_id, name, price, description, is_available = item
        status = "✅" if is_available else "❌"
        menu_text += f"{status} <b>{name}</b> - {price}₽\n"
        if description:
            menu_text += f"   <i>{description}</i>\n"
        menu_text += "\n"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data=f"mgr_menu_{restaurant_id}"
            )
        ]
    ])
    
    # Разбиваем длинные сообщения
    if len(menu_text) > 4000:
        for i in range(0, len(menu_text), 4000):
            await callback_query.message.answer(
                menu_text[i:i+4000],
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        await callback_query.message.answer(
            "Меню ресторана:",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.edit_text(
            menu_text,
            reply_markup=keyboard,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    
    await callback_query.answer()

@router.message(ManagerFilter(), F.text == "⚙️ Настройки системы")
async def system_settings(message: types.Message):
    """Настройки системы"""
    settings = db.get_system_settings()
    
    if not settings:
        await message.answer("❌ Настройки не найдены")
        return
    
    daily_budget = settings[1]
    deadline_hour = settings[2]
    notification_hour = settings[3]
    password = settings[4]
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="💰 Изменить бюджет", 
                callback_data="change_budget"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🔑 Изменить пароль регистрации", 
                callback_data="change_password"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="⏰ Изменить время дедлайна", 
                callback_data="change_deadline"
            )
        ]
    ])
    
    settings_text = (
        f"⚙️ <b>Настройки системы</b>\n\n"
        f"💰 <b>Дневной бюджет:</b> {daily_budget}₽\n"
        f"⏰ <b>Дедлайн заказа:</b> {deadline_hour}:00\n"
        f"📨 <b>Время отправки отчетов:</b> {notification_hour}:00\n"
        f"🔑 <b>Пароль регистрации:</b> <code>{password}</code>\n\n"
        f"Выберите настройку для изменения:"
    )
    
    await message.answer(settings_text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "change_budget")
async def change_budget_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает изменение бюджета"""
    await callback_query.message.edit_text(
        "💰 <b>Изменение дневного бюджета</b>\n\n"
        f"Текущий бюджет: {db.get_daily_budget()}₽\n\n"
        f"Введите новый бюджет (в рублях):",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.setting_password)  # Используем то же состояние
    await state.update_data(setting_type='budget')
    await callback_query.answer()

@router.callback_query(F.data == "change_password")
async def change_password_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает изменение пароля"""
    settings = db.get_system_settings()
    current_password = settings[4] if settings else "office123"
    
    await callback_query.message.edit_text(
        "🔑 <b>Изменение пароля регистрации</b>\n\n"
        f"Текущий пароль: <code>{current_password}</code>\n\n"
        f"Введите новый пароль:",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.setting_password)
    await state.update_data(setting_type='password')
    await callback_query.answer()

@router.message(ManagerStates.setting_password, F.text)
async def process_setting_change(message: types.Message, state: FSMContext):
    """Обрабатывает изменение настроек"""
    if message.text == "❌ Отмена":
        await message.answer("Изменение отменено.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    data = await state.get_data()
    setting_type = data.get('setting_type')
    
    if setting_type == 'budget':
        try:
            new_budget = int(message.text)
            
            if new_budget <= 0:
                await message.answer("❌ Бюджет должен быть положительным числом")
                return
            
            success = db.update_daily_budget(new_budget)
            
            if success:
                await message.answer(
                    f"✅ Дневной бюджет изменен на {new_budget}₽",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            else:
                await message.answer(
                    "❌ Ошибка при изменении бюджета",
                    reply_markup=types.ReplyKeyboardRemove()
                )
        
        except ValueError:
            await message.answer("❌ Введите число:")
            return
    
    elif setting_type == 'password':
        new_password = message.text.strip()
        
        if len(new_password) < 4:
            await message.answer("❌ Пароль должен быть не менее 4 символов")
            return
        
        success = db.update_registration_password(new_password)
        
        if success:
            await message.answer(
                f"✅ Пароль изменен на: <code>{new_password}</code>",
                reply_markup=types.ReplyKeyboardRemove(),
                parse_mode='HTML'
            )
        else:
            await message.answer(
                "❌ Ошибка при изменении пароля",
                reply_markup=types.ReplyKeyboardRemove()
            )
    
    await state.clear()

@router.message(ManagerFilter(), F.text == "🚚 Уведомить о доставке")
async def notify_delivery_start(message: types.Message):
    """Начинает процесс уведомления о доставке"""
    await message.answer(
        "🚚 <b>Уведомление о доставке</b>\n\n"
        "Выберите ресторан, для которого нужно отправить уведомление:",
        reply_markup=get_manager_restaurants_keyboard(),
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("notify_delivery_"))
async def notify_delivery_for_restaurant(callback_query: types.CallbackQuery, state: FSMContext):
    """Уведомление о доставке для конкретного ресторана"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    await state.update_data(restaurant_id=restaurant_id)
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    await callback_query.message.edit_text(
        f"🚚 <b>Уведомление о доставке: {restaurant_name}</b>\n\n"
        f"Введите сообщение для отправки всем, кто заказал из этого ресторана сегодня:\n\n"
        f"<i>Пример: Доставка {restaurant_name} приехала! Забирайте заказы у ресепшена.</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.sending_delivery_notification)
    await callback_query.answer()

@router.message(ManagerStates.sending_delivery_notification, F.text)
async def send_delivery_notification(message: types.Message, state: FSMContext, user_id: int):
    """Отправляет уведомление о доставке"""
    if message.text == "❌ Отмена":
        await message.answer("Уведомление отменено.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    notification_text = message.text.strip()
    
    data = await state.get_data()
    restaurant_id = data['restaurant_id']
    
    # Отправляем уведомление
    from aiogram import Bot
    bot = Bot.get_current()
    
    success, result_message = await DeliveryNotifier.notify_restaurant_delivery(
        bot, restaurant_id, notification_text, user_id
    )
    
    if success:
        await message.answer(
            f"✅ {result_message}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            f"❌ {result_message}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

@router.callback_query(F.data == "add_restaurant")
async def add_new_restaurant(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавление нового ресторана"""
    await callback_query.message.edit_text(
        "➕ <b>Добавление нового ресторана</b>\n\n"
        "Введите название ресторана:",
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(ManagerStates.adding_restaurant)
    await callback_query.answer()

@router.message(ManagerStates.adding_restaurant, F.text)
async def process_new_restaurant(message: types.Message, state: FSMContext):
    """Обрабатывает добавление нового ресторана"""
    if message.text == "❌ Отмена":
        await message.answer("Добавление отменено.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    restaurant_name = message.text.strip()
    
    if len(restaurant_name) < 2:
        await message.answer("❌ Название слишком короткое")
        return
    
    # Добавляем ресторан
    restaurant_id = db.add_restaurant(restaurant_name)
    
    if restaurant_id:
        await message.answer(
            f"✅ Ресторан '{restaurant_name}' добавлен!\n\n"
            f"Теперь добавьте меню для этого ресторана.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="📋 Добавить меню", 
                        callback_data=f"mgr_menu_{restaurant_id}"
                    )
                ]
            ]),
            parse_mode='HTML'
        )
    else:
        await message.answer(
            "❌ Ошибка при добавлении ресторана. Возможно, такое название уже существует.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

@router.callback_query(F.data.startswith("toggle_rest_"))
async def toggle_restaurant_status(callback_query: types.CallbackQuery):
    """Активирует/деактивирует ресторан"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    restaurant = db.get_restaurant_by_id(restaurant_id)
    if not restaurant:
        await callback_query.answer("❌ Ресторан не найден")
        return
    
    current_status = restaurant[3]  # is_active
    new_status = not current_status
    
    # В реальной БД нужно добавить метод update_restaurant_status
    # Здесь мок реализация
    db.cursor.execute('''
        UPDATE restaurants 
        SET is_active = ?
        WHERE id = ?
    ''', (new_status, restaurant_id))
    db.conn.commit()
    
    status_text = "активирован" if new_status else "деактивирован"
    
    await callback_query.message.edit_text(
        f"✅ Ресторан '{restaurant[1]}' {status_text}.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(
                text="🔙 Назад", 
                callback_data=f"mgr_rest_{restaurant_id}"
            )
        ]])
    )
    await callback_query.answer()

@router.callback_query(F.data == "back_to_restaurants")
async def back_to_restaurants_list(callback_query: types.CallbackQuery):
    """Возврат к списку ресторанов"""
    await callback_query.message.edit_text(
        "🏪 <b>Управление ресторанами</b>\n\n"
        "Выберите ресторан для управления:",
        reply_markup=get_manager_restaurants_keyboard(),
        parse_mode='HTML'
    )
    await callback_query.answer()