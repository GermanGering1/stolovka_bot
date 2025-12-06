from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import Database
from config import OrderStates
from keyboards.main_menus import (
    get_main_menu, 
    get_restaurants_keyboard,
    get_menu_keyboard,
    get_cart_keyboard,
    get_order_confirmation_keyboard,
    get_extra_money_keyboard,
    get_cancel_keyboard
)
from filters.role_filter import RegisteredFilter
import json

router = Router()
db = Database()

# Хранилище корзин пользователей (в памяти, можно переделать в Redis)
user_carts = {}

@router.message(RegisteredFilter(), F.text == "🍽️ Сделать заказ")
async def start_order(message: types.Message, state: FSMContext, user_role: str):
    """Начинает процесс заказа"""
    # Проверяем дедлайн
    if db.is_deadline_passed():
        settings = db.get_system_settings()
        deadline_hour = settings[2] if settings else 22
        await message.answer(
            f"⏰ <b>Дедлайн прошел!</b>\n\n"
            f"Прием заказов на завтра завершен в {deadline_hour}:00.\n"
            f"Попробуйте завтра утром.",
            parse_mode='HTML'
        )
        return
    
    # Инициализируем корзину
    user_id = message.from_user.id
    user_carts[user_id] = {
        'restaurant_id': None,
        'items': {},  # item_id: {'name': '', 'price': 0, 'quantity': 1}
        'total': 0
    }
    
    await message.answer(
        "🏪 <b>Выберите ресторан:</b>",
        reply_markup=get_restaurants_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.selecting_restaurant)

@router.callback_query(F.data.startswith("rest_"))
async def select_restaurant(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор ресторана"""
    restaurant_id = int(callback_query.data.split("_")[1])
    
    # Получаем информацию о ресторане
    restaurant = db.get_restaurant_by_id(restaurant_id)
    if not restaurant:
        await callback_query.message.edit_text("❌ Ресторан не найден")
        await callback_query.answer()
        return
    
    restaurant_name = restaurant[1]
    
    # Сохраняем выбранный ресторан в корзину
    user_id = callback_query.from_user.id
    if user_id in user_carts:
        user_carts[user_id]['restaurant_id'] = restaurant_id
    else:
        user_carts[user_id] = {
            'restaurant_id': restaurant_id,
            'items': {},
            'total': 0
        }
    
    await callback_query.message.edit_text(
        f"🏪 <b>{restaurant_name}</b>\n\n"
        f"Выберите блюда из меню:",
        reply_markup=get_menu_keyboard(restaurant_id),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.selecting_dishes)
    await callback_query.answer()

@router.callback_query(F.data.startswith("item_"))
async def add_to_cart(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавляет блюдо в корзину"""
    parts = callback_query.data.split("_")
    item_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    
    # Получаем информацию о блюде
    menu_item = db.get_menu_item_by_id(item_id)
    if not menu_item:
        await callback_query.answer("❌ Блюдо не найдено")
        return
    
    item_id, restaurant_id, name, price, description, restaurant_name = menu_item
    
    # Добавляем в корзину пользователя
    user_id = callback_query.from_user.id
    if user_id not in user_carts:
        await callback_query.answer("❌ Корзина не инициализирована")
        return
    
    if user_carts[user_id]['restaurant_id'] != restaurant_id:
        await callback_query.answer("❌ Вы можете заказывать только из одного ресторана за раз")
        return
    
    # Добавляем/увеличиваем количество
    if item_id in user_carts[user_id]['items']:
        user_carts[user_id]['items'][item_id]['quantity'] += 1
    else:
        user_carts[user_id]['items'][item_id] = {
            'name': name,
            'price': price,
            'quantity': 1
        }
    
    # Обновляем общую сумму
    user_carts[user_id]['total'] += price
    
    await callback_query.answer(f"✅ {name} добавлено в корзину")

@router.callback_query(F.data.startswith("cart_"))
async def show_cart(callback_query: types.CallbackQuery, state: FSMContext):
    """Показывает корзину"""
    user_id = callback_query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]['items']:
        await callback_query.message.edit_text(
            "🛒 <b>Корзина пуста</b>\n\n"
            "Добавьте блюда из меню:",
            reply_markup=get_menu_keyboard(user_carts[user_id]['restaurant_id']),
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    cart = user_carts[user_id]
    restaurant_id = cart['restaurant_id']
    
    # Получаем информацию о ресторане
    restaurant = db.get_restaurant_by_id(restaurant_id)
    restaurant_name = restaurant[1] if restaurant else "Ресторан"
    
    # Формируем текст корзины
    cart_text = f"🛒 <b>Ваш заказ из {restaurant_name}</b>\n\n"
    
    total = 0
    for item_id, item_data in cart['items'].items():
        item_total = item_data['price'] * item_data['quantity']
        cart_text += f"• {item_data['name']} x{item_data['quantity']} = {item_total}₽\n"
        total += item_total
    
    cart_text += f"\n<b>Итого: {total}₽</b>\n"
    
    # Проверяем бюджет
    budget = db.get_daily_budget()
    if total > budget:
        cart_text += f"⚠️ <b>Превышение бюджета на {total - budget}₽</b>\n"
    
    await callback_query.message.edit_text(
        cart_text,
        reply_markup=get_cart_keyboard(restaurant_id),
        parse_mode='HTML'
    )
    await callback_query.answer()

@router.callback_query(F.data.startswith("checkout_"))
async def checkout(callback_query: types.CallbackQuery, state: FSMContext):
    """Переход к оформлению заказа"""
    user_id = callback_query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]['items']:
        await callback_query.answer("❌ Корзина пуста")
        return
    
    cart = user_carts[user_id]
    total = cart['total']
    budget = db.get_daily_budget()
    
    # Формируем текст заказа
    order_text = f"📋 <b>Ваш заказ</b>\n\n"
    
    for item_id, item_data in cart['items'].items():
        item_total = item_data['price'] * item_data['quantity']
        order_text += f"• {item_data['name']} x{item_data['quantity']} = {item_total}₽\n"
    
    order_text += f"\n<b>Итого: {total}₽</b>\n"
    order_text += f"💰 <b>Ваш бюджет:</b> {budget}₽\n"
    
    if total <= budget:
        order_text += f"✅ <b>В пределах бюджета!</b>\n\n"
        order_text += "Подтвердить заказ?"
        
        await callback_query.message.edit_text(
            order_text,
            reply_markup=get_order_confirmation_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(OrderStates.confirming_order)
    else:
        extra_needed = total - budget
        order_text += f"⚠️ <b>Превышение бюджета на {extra_needed}₽</b>\n\n"
        order_text += "Сколько готовы добавить из своих средств?"
        
        await callback_query.message.edit_text(
            order_text,
            reply_markup=get_extra_money_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(OrderStates.adding_extra_money)
    
    await callback_query.answer()

@router.callback_query(F.data.startswith("extra_"))
async def process_extra_money(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает добавление своих денег"""
    data = callback_query.data
    
    if data == "extra_none":
        await callback_query.message.edit_text(
            "❌ Заказ отменен. Сумма превышает бюджет.\n"
            "Попробуйте изменить заказ.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="🔙 Вернуться к меню", 
                        callback_data=f"add_more_{user_carts[callback_query.from_user.id]['restaurant_id']}"
                    )
                ]]
            )
        )
        await callback_query.answer()
        return
    
    user_id = callback_query.from_user.id
    cart = user_carts[user_id]
    total = cart['total']
    budget = db.get_daily_budget()
    
    extra_money = 0
    
    if data == "extra_50":
        extra_money = 50
    elif data == "extra_100":
        extra_money = 100
    elif data == "extra_200":
        extra_money = 200
    elif data == "extra_500":
        extra_money = 500
    elif data == "extra_custom":
        await callback_query.message.edit_text(
            "💰 Введите сумму, которую готовы добавить (в рублях):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(OrderStates.adding_extra_money)
        await callback_query.answer()
        return
    
    # Проверяем, достаточно ли добавленных денег
    if total > budget + extra_money:
        await callback_query.answer(f"❌ Недостаточно! Нужно минимум {total - budget}₽")
        return
    
    # Сохраняем extra_money в состоянии
    await state.update_data(extra_money=extra_money)
    
    # Показываем финальное подтверждение
    order_text = f"📋 <b>Ваш заказ</b>\n\n"
    
    for item_id, item_data in cart['items'].items():
        item_total = item_data['price'] * item_data['quantity']
        order_text += f"• {item_data['name']} x{item_data['quantity']} = {item_total}₽\n"
    
    order_text += f"\n<b>Итого: {total}₽</b>\n"
    order_text += f"💰 <b>Из бюджета:</b> {min(budget, total)}₽\n"
    order_text += f"💵 <b>Доплата своими:</b> {extra_money}₽\n\n"
    order_text += "Подтвердить заказ?"
    
    await callback_query.message.edit_text(
        order_text,
        reply_markup=get_order_confirmation_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.confirming_order)
    await callback_query.answer()

@router.message(OrderStates.adding_extra_money, F.text)
async def process_custom_extra_money(message: types.Message, state: FSMContext):
    """Обрабатывает ввод своей суммы"""
    if message.text == "❌ Отмена":
        await message.answer("Отмена доплаты.", reply_markup=types.ReplyKeyboardRemove())
        user_id = message.from_user.id
        restaurant_id = user_carts[user_id]['restaurant_id']
        
        await message.answer(
            "Вернитесь к меню:",
            reply_markup=get_menu_keyboard(restaurant_id)
        )
        await state.set_state(OrderStates.selecting_dishes)
        return
    
    try:
        extra_money = int(message.text)
        
        if extra_money < 0:
            await message.answer("❌ Сумма не может быть отрицательной. Введите еще раз:")
            return
        
        user_id = message.from_user.id
        cart = user_carts[user_id]
        total = cart['total']
        budget = db.get_daily_budget()
        
        if total > budget + extra_money:
            await message.answer(
                f"❌ Недостаточно! Нужно минимум {total - budget}₽\n"
                f"Введите сумму еще раз:"
            )
            return
        
        # Сохраняем extra_money в состоянии
        await state.update_data(extra_money=extra_money)
        
        # Показываем финальное подтверждение
        order_text = f"📋 <b>Ваш заказ</b>\n\n"
        
        for item_id, item_data in cart['items'].items():
            item_total = item_data['price'] * item_data['quantity']
            order_text += f"• {item_data['name']} x{item_data['quantity']} = {item_total}₽\n"
        
        order_text += f"\n<b>Итого: {total}₽</b>\n"
        order_text += f"💰 <b>Из бюджета:</b> {min(budget, total)}₽\n"
        order_text += f"💵 <b>Доплата своими:</b> {extra_money}₽\n\n"
        order_text += "Подтвердить заказ?"
        
        await message.answer(
            order_text,
            reply_markup=get_order_confirmation_keyboard(),
            parse_mode='HTML'
        )
        await state.set_state(OrderStates.confirming_order)
        
    except ValueError:
        await message.answer("❌ Введите число:")

@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback_query: types.CallbackQuery, state: FSMContext):
    """Подтверждает и сохраняет заказ"""
    user_id = callback_query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]['items']:
        await callback_query.answer("❌ Корзина пуста")
        return
    
    cart = user_carts[user_id]
    restaurant_id = cart['restaurant_id']
    
    # Получаем extra_money из состояния
    state_data = await state.get_data()
    extra_money = state_data.get('extra_money', 0)
    
    # Получаем пользователя
    user = db.get_user_by_telegram_id(user_id)
    if not user:
        await callback_query.answer("❌ Пользователь не найден")
        return
    
    user_db_id = user[0]
    
    # Формируем order_data в нужном формате
    order_data = {}
    for item_id, item_data in cart['items'].items():
        # Получаем полную информацию о блюде
        menu_item = db.get_menu_item_by_id(item_id)
        if menu_item:
            item_name = menu_item[2]  # name
            item_price = menu_item[3]  # price
            # Сохраняем в формате "название: цена"
            order_data[item_name] = item_price * item_data['quantity']
    
    # Сохраняем заказ в БД
    order_id = db.create_order(
        user_id=user_db_id,
        restaurant_id=restaurant_id,
        order_data=order_data,
        total_price=cart['total'],
        extra_money=extra_money
    )
    
    if order_id:
        # Формируем детали заказа для сообщения
        order_details = f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        order_details += f"📅 <b>На дату:</b> Завтра\n"
        order_details += f"🏪 <b>Ресторан:</b> {db.get_restaurant_by_id(restaurant_id)[1]}\n\n"
        
        for item_name, item_total in order_data.items():
            order_details += f"• {item_name}: {item_total}₽\n"
        
        order_details += f"\n<b>Итого: {cart['total']}₽</b>\n"
        
        if extra_money > 0:
            order_details += f"💵 <b>Доплата своими:</b> {extra_money}₽\n"
        
        budget = db.get_daily_budget()
        from_budget = min(budget, cart['total'] - extra_money)
        order_details += f"💰 <b>Из бюджета:</b> {from_budget}₽\n\n"
        
        order_details += "Заказ будет отправлен менеджеру в 22:00."
        
        await callback_query.message.edit_text(
            order_details,
            parse_mode='HTML'
        )
        
        # Очищаем корзину
        if user_id in user_carts:
            del user_carts[user_id]
        
        # Получаем роль пользователя для возврата в меню
        user_role = user[5]  # role из БД
        await callback_query.message.answer(
            "Вернуться в главное меню:",
            reply_markup=get_main_menu(user_role)
        )
        
    else:
        await callback_query.message.edit_text(
            "❌ Ошибка при сохранении заказа. Попробуйте еще раз."
        )
    
    await state.clear()
    await callback_query.answer()

@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
    """Отменяет заказ"""
    user_id = callback_query.from_user.id
    
    # Очищаем корзину
    if user_id in user_carts:
        del user_carts[user_id]
    
    await callback_query.message.edit_text(
        "❌ Заказ отменен."
    )
    
    # Получаем пользователя для возврата в меню
    user = db.get_user_by_telegram_id(user_id)
    user_role = user[5] if user else 'employee'
    
    await callback_query.message.answer(
        "Вернуться в главное меню:",
        reply_markup=get_main_menu(user_role)
    )
    
    await state.clear()
    await callback_query.answer()

@router.message(RegisteredFilter(), F.text == "📜 Мои заказы")
async def show_my_orders(message: types.Message):
    """Показывает заказы пользователя"""
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    user_db_id = user[0]
    
    # Получаем заказы на завтра
    from database import Database
    db_instance = Database()
    orders = db_instance.get_orders_for_restaurant(None)  # Все заказы
    
    user_orders = [o for o in orders if o[1] == user_db_id and o[7] == 0]  # is_sent = 0
    
    if not user_orders:
        await message.answer("📭 У вас нет активных заказов на завтра")
        return
    
    orders_text = "📋 <b>Ваши заказы на завтра:</b>\n\n"
    
    for order in user_orders:
        order_id, user_id, restaurant_id, order_data_json, total_price, extra_money, order_date, created_at, full_name, office, restaurant_name = order
        
        orders_text += f"🏪 <b>{restaurant_name}</b>\n"
        orders_text += f"🆔 Заказ #{order_id}\n"
        orders_text += f"💵 Сумма: {total_price}₽\n"
        
        if extra_money > 0:
            orders_text += f"💵 Доплата: {extra_money}₽\n"
        
        # Парсим JSON с заказом
        try:
            order_data = json.loads(order_data_json)
            orders_text += "🍽 Заказ:\n"
            for item_name, item_price in order_data.items():
                orders_text += f"  • {item_name}: {item_price}₽\n"
        except:
            pass
        
        orders_text += f"📅 Создан: {created_at[:16]}\n\n"
    
    await message.answer(orders_text, parse_mode='HTML')

# Обработчики для навигации по меню
@router.callback_query(F.data.startswith("menu_page_"))
async def change_menu_page(callback_query: types.CallbackQuery):
    """Меняет страницу меню"""
    parts = callback_query.data.split("_")
    restaurant_id = int(parts[2])
    page = int(parts[3])
    
    await callback_query.message.edit_reply_markup(
        reply_markup=get_menu_keyboard(restaurant_id, page)
    )
    await callback_query.answer()

@router.callback_query(F.data == "back_to_restaurants")
async def back_to_restaurants(callback_query: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору ресторана"""
    user_id = callback_query.from_user.id
    # Очищаем корзину при возврате
    if user_id in user_carts:
        del user_carts[user_id]
    
    await callback_query.message.edit_text(
        "🏪 <b>Выберите ресторан:</b>",
        reply_markup=get_restaurants_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.selecting_restaurant)
    await callback_query.answer()

@router.callback_query(F.data.startswith("add_more_"))
async def add_more_items(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавить еще блюда"""
    restaurant_id = int(callback_query.data.split("_")[2])
    
    await callback_query.message.edit_text(
        f"Выберите блюда из меню:",
        reply_markup=get_menu_keyboard(restaurant_id),
        parse_mode='HTML'
    )
    await state.set_state(OrderStates.selecting_dishes)
    await callback_query.answer()