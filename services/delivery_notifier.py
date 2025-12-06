from database import Database
from aiogram import Bot

db = Database()

class DeliveryNotifier:
    @staticmethod
    async def notify_restaurant_delivery(bot: Bot, restaurant_id: int, message: str, manager_id: int):
        """Отправляет уведомление о доставке всем, кто заказал из этого ресторана"""
        try:
            # Получаем пользователей
            user_telegram_ids = db.get_users_for_restaurant_today(restaurant_id)
            
            if not user_telegram_ids:
                return False, "Нет заказов из этого ресторана на сегодня"
            
            # Получаем информацию о ресторане
            restaurant = db.get_restaurant_by_id(restaurant_id)
            if not restaurant:
                return False, "Ресторан не найден"
            
            restaurant_name = restaurant[1]
            
            # Отправляем всем пользователям
            success_count = 0
            for telegram_id in user_telegram_ids:
                try:
                    await bot.send_message(
                        telegram_id,
                        f"🚚 <b>Уведомление о доставке</b>\n\n"
                        f"Ресторан: <b>{restaurant_name}</b>\n"
                        f"{message}",
                        parse_mode='HTML'
                    )
                    success_count += 1
                except Exception as e:
                    print(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
            
            # Сохраняем в историю
            db.add_delivery_notification(restaurant_id, message, manager_id)
            
            return True, f"Уведомление отправлено {success_count}/{len(user_telegram_ids)} пользователям"
            
        except Exception as e:
            return False, f"Ошибка: {str(e)}"