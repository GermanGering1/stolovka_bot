import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config import storage
from database import Database
from middlewares.auth_middleware import AuthMiddleware
from services.order_notifier import OrderNotifier
from routers import auth, employee, manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота
API_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

async def main():
    # Инициализация БД
    db = Database()
    
    # Создаем менеджера по умолчанию
    MANAGER_TELEGRAM_ID = int(os.getenv('MANAGER_TELEGRAM_ID', 123456789))
    
    manager_user = db.get_user_by_telegram_id(MANAGER_TELEGRAM_ID)
    if not manager_user:
        # Регистрируем менеджера
        settings = db.get_system_settings()
        password = settings[4] if settings else 'office123'
        
        # Используем cursor напрямую, так как у нас нет метода для регистрации менеджера
        try:
            db.cursor.execute('''
                INSERT OR REPLACE INTO users (telegram_id, password, full_name, office, role)
                VALUES (?, ?, 'Менеджер', 'Главный офис', 'manager')
            ''', (MANAGER_TELEGRAM_ID, password))
            db.conn.commit()
            logger.info(f"✅ Менеджер с ID {MANAGER_TELEGRAM_ID} создан")
        except Exception as e:
            logger.error(f"❌ Ошибка создания менеджера: {e}")
    
    # Инициализация бота
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера
    dp = Dispatcher(storage=storage)
    
    # Подключаем middleware
    auth_middleware = AuthMiddleware()
    dp.update.middleware(auth_middleware)
    
    # Подключаем роутеры
    dp.include_router(auth.router)
    dp.include_router(employee.router)
    dp.include_router(manager.router)
    
    # Запускаем сервис отправки заказов (в фоне)
    order_notifier = OrderNotifier(bot)
    asyncio.create_task(order_notifier.check_and_send_orders(MANAGER_TELEGRAM_ID))
    
    # Запуск бота
    logger.info("🤖 Бот запущен...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()
        db.close()

if __name__ == '__main__':
    asyncio.run(main())