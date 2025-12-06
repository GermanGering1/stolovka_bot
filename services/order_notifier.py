import asyncio
from datetime import datetime, time
from database import Database
from aiogram import Bot

db = Database()

class OrderNotifier:
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def generate_orders_report(self) -> str:
        """Генерирует отчет по заказам в нужном формате"""
        orders = db.get_all_orders_for_tomorrow()
        
        if not orders:
            return "📭 На завтра заказов нет"
        
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
        
        # Формируем отчет
        report = f"📋 <b>ЗАКАЗЫ НА ЗАВТРА ({datetime.now().strftime('%d.%m.%Y')})</b>\n\n"
        
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
        
        return report
    
    async def send_orders_to_manager(self, manager_telegram_id: int):
        """Отправляет заказы менеджеру"""
        try:
            report = await self.generate_orders_report()
            
            # Отправляем отчет
            await self.bot.send_message(
                manager_telegram_id,
                report,
                parse_mode='HTML'
            )
            
            # Помечаем заказы как отправленные
            orders = db.get_all_orders_for_tomorrow()
            order_ids = [o[0] for o in orders]
            
            if order_ids:
                db.mark_orders_as_sent(order_ids)
                print(f"✅ Отправлено {len(order_ids)} заказов менеджеру")
            
        except Exception as e:
            print(f"❌ Ошибка отправки заказов: {e}")
    
    async def check_and_send_orders(self, manager_telegram_id: int):
        """Проверяет время и отправляет заказы если настал дедлайн"""
        while True:
            try:
                now = datetime.now()
                
                # Проверяем каждую минуту
                await asyncio.sleep(60)
                
                # Получаем время дедлайна из настроек
                settings = db.get_system_settings()
                deadline_hour = settings[2] if settings else 22  # order_deadline_hour
                
                # Проверяем, настало ли время отправки
                if now.hour == deadline_hour and now.minute == 0:
                    print(f"⏰ Время отправки заказов! {now}")
                    
                    # Отправляем заказы менеджеру
                    await self.send_orders_to_manager(manager_telegram_id)
                    
                    # Ждем до следующего дня
                    await asyncio.sleep(3600)  # 1 час
                
            except Exception as e:
                print(f"❌ Ошибка в OrderNotifier: {e}")
                await asyncio.sleep(300)  # 5 минут при ошибке