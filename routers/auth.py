from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import Database
from config import AuthStates, OFFICES
from keyboards.main_menus import get_main_menu, get_office_selection_keyboard, get_cancel_keyboard
from filters.role_filter import PendingFilter, RegisteredFilter

router = Router()
db = Database()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, user_role: str):
    """Начало работы - проверяем регистрацию"""
    if user_role == 'pending':
        await message.answer(
            "👋 Добро пожаловать в систему заказа обедов!\n\n"
            "Введите пароль для регистрации:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AuthStates.waiting_for_password)
    else:
        # Уже зарегистрирован
        budget = db.get_daily_budget()
        await message.answer(
            f"С возвращением!\n\n"
            f"💰 <b>Дневной бюджет:</b> {budget}₽\n"
            f"👤 <b>Ваша роль:</b> {'Менеджер' if user_role == 'manager' else 'Сотрудник'}\n\n"
            f"Используйте меню ниже:",
            reply_markup=get_main_menu(user_role),
            parse_mode='HTML'
        )
        await state.clear()

@router.message(AuthStates.waiting_for_password, F.text)
async def process_password(message: types.Message, state: FSMContext, registration_password: str):
    """Обрабатывает ввод пароля"""
    if message.text == "❌ Отмена":
        await message.answer("Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    password = message.text.strip()
    
    if password == registration_password:
        await message.answer(
            "✅ Пароль верный!\n\n"
            "Теперь введите ваше ФИО (полностью):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AuthStates.waiting_for_name)
    else:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз:")

@router.message(AuthStates.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    """Обрабатывает ввод ФИО"""
    if message.text == "❌ Отмена":
        await message.answer("Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    full_name = message.text.strip()
    
    if len(full_name) < 3:
        await message.answer("❌ ФИО слишком короткое. Введите еще раз:")
        return
    
    await state.update_data(full_name=full_name)
    
    await message.answer(
        f"✅ ФИО сохранено: {full_name}\n\n"
        f"Теперь выберите ваш офис:",
        reply_markup=get_office_selection_keyboard()
    )
    await state.set_state(AuthStates.waiting_for_office)

@router.message(AuthStates.waiting_for_office, F.text)
async def process_office(message: types.Message, state: FSMContext):
    """Обрабатывает выбор офиса"""
    if message.text == "❌ Отмена":
        await message.answer("Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    office = message.text.strip()
    
    # Проверяем, что офис из списка
    if office not in OFFICES.values():
        await message.answer(
            "❌ Пожалуйста, выберите офис из списка кнопками:",
            reply_markup=get_office_selection_keyboard()
        )
        return
    
    data = await state.get_data()
    full_name = data['full_name']
    
    # Регистрируем пользователя
    success = db.register_user(message.from_user.id, full_name, office)
    
    if success:
        budget = db.get_daily_budget()
        await message.answer(
            f"🎉 <b>Регистрация успешна!</b>\n\n"
            f"👤 <b>ФИО:</b> {full_name}\n"
            f"🏢 <b>Офис:</b> {office}\n"
            f"💰 <b>Дневной бюджет:</b> {budget}₽\n\n"
            f"Теперь вы можете делать заказы на обед!",
            reply_markup=get_main_menu('employee'),
            parse_mode='HTML'
        )
    else:
        await message.answer(
            "❌ Ошибка регистрации. Возможно, вы уже зарегистрированы.\n"
            "Попробуйте команду /start еще раз."
        )
    
    await state.clear()

@router.message(Command("profile"))
@router.message(RegisteredFilter(), F.text == "ℹ️ Информация")
async def show_profile(message: types.Message, user_role: str, full_name: str, 
                      office: str, daily_budget: int, deadline_message: str,
                      full_name_with_emoji: str):
    """Показывает профиль пользователя"""
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"{full_name_with_emoji}\n"
        f"🏢 <b>Офис:</b> {office}\n"
        f"🎭 <b>Роль:</b> {'Менеджер' if user_role == 'manager' else 'Сотрудник'}\n"
        f"💰 <b>Дневной бюджет:</b> {daily_budget}₽\n\n"
        f"{deadline_message}"
    )
    
    await message.answer(profile_text, parse_mode='HTML')