from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable, Union
from datetime import datetime, date, time
from database import Database
from config import ROLES, Settings
import json

db = Database()

class AuthMiddleware(BaseMiddleware):
    """
    Middleware для аутентификации и авторизации пользователей.
    Добавляет данные о пользователе в контекст каждого хэндлера.
    """
    
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        """
        Основной метод middleware.
        """
        
        # Получаем Telegram ID пользователя
        telegram_id = None
        if isinstance(event, Message):
            telegram_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            telegram_id = event.from_user.id
        else:
            # Если это другой тип события, пропускаем middleware
            return await handler(event, data)
        
        # ========== ПОЛУЧЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ ==========
        
        # Получаем пользователя из БД
        user = db.get_user_by_telegram_id(telegram_id)
        
        if user:
            # Пользователь найден в БД
            user_id, telegram_id_db, password, full_name, office, role, created_at = user
            
            # Добавляем информацию о пользователе в данные
            data['user_id'] = user_id  # Внутренний ID в БД
            data['telegram_id'] = telegram_id_db
            data['full_name'] = full_name
            data['office'] = office
            data['user_role'] = role
            data['created_at'] = created_at
            data['is_registered'] = True
            
            # Добавляем читабельное название роли
            data['role_name'] = ROLES.get(role, role)
            
        else:
            # Пользователь не найден в БД (не зарегистрирован)
            data['user_id'] = None
            data['telegram_id'] = telegram_id
            data['full_name'] = event.from_user.full_name if event.from_user else "Неизвестный"
            data['office'] = None
            data['user_role'] = 'pending'  # Ожидает регистрации
            data['created_at'] = None
            data['is_registered'] = False
            data['role_name'] = ROLES.get('pending', 'Ожидает регистрации')
        
        # ========== ПРОВЕРКА СИСТЕМНЫХ НАСТРОЕК ==========
        
        # Получаем системные настройки
        settings = db.get_system_settings()
        if settings:
            daily_budget = settings[1]  # daily_budget
            order_deadline_hour = settings[2]  # order_deadline_hour
            notification_hour = settings[3]  # notification_hour
            registration_password = settings[4]  # registration_password
        else:
            # Используем значения по умолчанию
            daily_budget = Settings.DAILY_BUDGET
            order_deadline_hour = Settings.ORDER_DEADLINE_HOUR
            notification_hour = Settings.NOTIFICATION_HOUR
            registration_password = Settings.REGISTRATION_PASSWORD
        
        # Добавляем настройки в данные
        data['daily_budget'] = daily_budget
        data['order_deadline_hour'] = order_deadline_hour
        data['notification_hour'] = notification_hour
        data['registration_password'] = registration_password
        
        # ========== ПРОВЕРКА ДОСТУПНОСТИ ЗАКАЗОВ ==========
        
        # Проверяем, доступны ли заказы сегодня
        ordering_enabled, reason = db.is_ordering_enabled_today()
        data['ordering_enabled'] = ordering_enabled
        data['ordering_disabled_reason'] = reason
        
        # Проверяем, прошел ли дедлайн за сегодня
        deadline_passed = db.is_deadline_passed()
        data['deadline_passed'] = deadline_passed
        
        # Проверяем, можно ли делать заказ на завтра
        can_order_tomorrow = ordering_enabled and not deadline_passed
        data['can_order_tomorrow'] = can_order_tomorrow
        
        # ========== ИНФОРМАЦИЯ О СИСТЕМЕ ==========
        
        # Текущая дата и время
        now = datetime.now()
        data['current_date'] = now.strftime('%d.%m.%Y')
        data['current_time'] = now.strftime('%H:%M')
        data['current_datetime'] = now
        
        # Дата на завтра (для заказов)
        tomorrow_date = date.today()
        data['tomorrow_date'] = tomorrow_date.strftime('%d.%m.%Y')
        data['tomorrow_date_iso'] = tomorrow_date.isoformat()
        
        # Информация о дедлайне
        if can_order_tomorrow:
            # Рассчитываем время до дедлайна
            deadline_time = time(order_deadline_hour, 0)
            current_time = now.time()
            
            if current_time < deadline_time:
                hours_left = deadline_time.hour - current_time.hour
                minutes_left = deadline_time.minute - current_time.minute
                
                if minutes_left < 0:
                    hours_left -= 1
                    minutes_left += 60
                
                if hours_left > 0:
                    time_until_deadline = f"{hours_left} час {minutes_left} мин"
                else:
                    time_until_deadline = f"{minutes_left} мин"
            else:
                time_until_deadline = "менее минуты"
            
            data['time_until_deadline'] = time_until_deadline
            data['deadline_message'] = f"⏰ Дедлайн заказов на завтра: {order_deadline_hour}:00 ({time_until_deadline} осталось)"
        else:
            data['time_until_deadline'] = None
            if deadline_passed:
                data['deadline_message'] = f"⏰ Дедлайн прошел в {order_deadline_hour}:00. Заказы на завтра больше не принимаются."
            else:
                data['deadline_message'] = f"📅 Заказы сегодня недоступны. {reason}"
        
        # ========== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ==========
        
        # Полное имя с эмодзи в зависимости от роли
        if data['user_role'] == 'manager':
            data['full_name_with_emoji'] = f"👑 {data['full_name']}"
        elif data['user_role'] == 'employee':
            data['full_name_with_emoji'] = f"👤 {data['full_name']}"
        else:
            data['full_name_with_emoji'] = f"⏳ {data['full_name']}"
        
        # Информация о бюджете
        if data['is_registered']:
            data['budget_message'] = f"💰 Ваш дневной бюджет: {daily_budget}₽"
        else:
            data['budget_message'] = f"💰 Дневной бюджет для сотрудников: {daily_budget}₽"
        
        # ========== ВЫЗОВ СЛЕДУЮЩЕГО ХЭНДЛЕРА ==========
        
        try:
            return await handler(event, data)
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"⚠️ Ошибка в middleware: {e}")
            raise