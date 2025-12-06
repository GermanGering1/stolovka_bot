import sqlite3
from datetime import datetime, date, timedelta
import json
from typing import List, Dict, Optional

class Database:
    def __init__(self, db_name='lunch_orders.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Пользователи
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                office TEXT NOT NULL,
                role TEXT DEFAULT 'employee',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Рестораны
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Меню ресторанов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                is_available BOOLEAN DEFAULT 1,
                FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
            )
        ''')
        
        # Заказы (хранятся до отправки менеджеру)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                restaurant_id INTEGER NOT NULL,
                order_data TEXT NOT NULL,  -- JSON с заказом
                total_price INTEGER NOT NULL,
                extra_money INTEGER DEFAULT 0,
                order_date DATE NOT NULL,  -- Дата, на которую заказ
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_sent BOOLEAN DEFAULT 0,  -- Отправлен ли менеджеру
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
            )
        ''')
        
        # Отправленные заказы (архив)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_order_id INTEGER,
                user_id INTEGER NOT NULL,
                restaurant_id INTEGER NOT NULL,
                order_data TEXT NOT NULL,
                total_price INTEGER NOT NULL,
                extra_money INTEGER DEFAULT 0,
                order_date DATE NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
            )
        ''')
        
        # Системные настройки (с бюджетом)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY,
                daily_budget INTEGER DEFAULT 400,
                order_deadline_hour INTEGER DEFAULT 22,
                notification_hour INTEGER DEFAULT 22,
                registration_password TEXT DEFAULT 'office123',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Уведомления о доставке
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS delivery_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                sent_by INTEGER NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (restaurant_id) REFERENCES restaurants (id),
                FOREIGN KEY (sent_by) REFERENCES users (id)
            )
        ''')
        
        # Инициализация настроек
        self.cursor.execute('''
            INSERT OR IGNORE INTO system_settings 
            (id, daily_budget, order_deadline_hour, notification_hour, registration_password)
            VALUES (1, 400, 22, 22, 'office123')
        ''')
        
        self.conn.commit()
        pass
    
    # ========== АВТОРИЗАЦИЯ И ПОЛЬЗОВАТЕЛИ ==========
    
    def check_registration_password(self, password: str) -> bool:
        """Проверяет пароль для регистрации"""
        self.cursor.execute(
            'SELECT registration_password FROM system_settings WHERE id = 1'
        )
        result = self.cursor.fetchone()
        return result and result[0] == password
    
    def register_user(self, telegram_id: int, full_name: str, office: str) -> bool:
        """Регистрирует нового пользователя"""
        try:
            # Проверяем, не зарегистрирован ли уже
            self.cursor.execute(
                'SELECT id FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            if self.cursor.fetchone():
                return False
            
            # Получаем текущий пароль
            self.cursor.execute(
                'SELECT registration_password FROM system_settings WHERE id = 1'
            )
            password = self.cursor.fetchone()[0]
            
            self.cursor.execute('''
                INSERT INTO users (telegram_id, password, full_name, office, role)
                VALUES (?, ?, ?, ?, 'employee')
            ''', (telegram_id, password, full_name, office))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Registration error: {e}")
            return False
    
    def get_user_by_telegram_id(self, telegram_id: int):
        """Получает пользователя по Telegram ID"""
        self.cursor.execute('''
            SELECT id, telegram_id, full_name, office, role
            FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        return self.cursor.fetchone()
    
    def get_user_by_id(self, user_id: int):
        """Получает пользователя по ID"""
        self.cursor.execute('''
            SELECT id, telegram_id, full_name, office, role
            FROM users WHERE id = ?
        ''', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_users(self):
        """Получает всех пользователей"""
        self.cursor.execute('''
            SELECT id, telegram_id, full_name, office, role
            FROM users ORDER BY full_name
        ''')
        return self.cursor.fetchall()
    
    # ========== НАСТРОЙКИ СИСТЕМЫ ==========
    
    def get_system_settings(self):
        """Получает системные настройки"""
        self.cursor.execute('SELECT * FROM system_settings WHERE id = 1')
        return self.cursor.fetchone()
    
    def update_daily_budget(self, new_budget: int) -> bool:
        """Обновляет дневной бюджет"""
        try:
            self.cursor.execute('''
                UPDATE system_settings 
                SET daily_budget = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (new_budget,))
            self.conn.commit()
            return True
        except:
            return False
    
    def update_registration_password(self, new_password: str) -> bool:
        """Обновляет пароль для регистрации"""
        try:
            self.cursor.execute('''
                UPDATE system_settings 
                SET registration_password = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (new_password,))
            self.conn.commit()
            return True
        except:
            return False
    
    def get_daily_budget(self) -> int:
        """Получает текущий дневной бюджет"""
        settings = self.get_system_settings()
        return settings[1] if settings else 400
    
    # ========== РЕСТОРАНЫ И МЕНЮ ==========
    
    def get_restaurants(self, active_only: bool = True):
        """Получает список ресторанов"""
        query = 'SELECT id, name, description, is_active FROM restaurants'
        if active_only:
            query += ' WHERE is_active = 1'
        query += ' ORDER BY name'
        
        self.cursor.execute(query)
        return self.cursor.fetchall()
    
    def get_restaurant_by_id(self, restaurant_id: int):
        """Получает ресторан по ID"""
        self.cursor.execute('''
            SELECT id, name, description, is_active
            FROM restaurants WHERE id = ?
        ''', (restaurant_id,))
        return self.cursor.fetchone()
    
    def add_restaurant(self, name: str, description: str = None) -> int:
        """Добавляет новый ресторан"""
        try:
            self.cursor.execute('''
                INSERT INTO restaurants (name, description)
                VALUES (?, ?)
            ''', (name, description))
            
            restaurant_id = self.cursor.lastrowid
            self.conn.commit()
            return restaurant_id
        except:
            return 0
    
    def add_menu_item(self, restaurant_id: int, name: str, price: int, 
                     description: str = None) -> bool:
        """Добавляет позицию в меню"""
        try:
            self.cursor.execute('''
                INSERT INTO menu_items (restaurant_id, name, price, description)
                VALUES (?, ?, ?, ?)
            ''', (restaurant_id, name, price, description))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Add menu item error: {e}")
            return False
    
    def get_menu_for_restaurant(self, restaurant_id: int, available_only: bool = True):
        """Получает меню ресторана"""
        query = '''
            SELECT id, name, price, description, is_available
            FROM menu_items
            WHERE restaurant_id = ?
        '''
        
        if available_only:
            query += ' AND is_available = 1'
        
        query += ' ORDER BY name'
        
        self.cursor.execute(query, (restaurant_id,))
        return self.cursor.fetchall()
    
    def get_menu_item_by_id(self, item_id: int):
        """Получает позицию меню по ID"""
        self.cursor.execute('''
            SELECT mi.id, mi.restaurant_id, mi.name, mi.price, mi.description,
                   r.name as restaurant_name
            FROM menu_items mi
            JOIN restaurants r ON mi.restaurant_id = r.id
            WHERE mi.id = ?
        ''', (item_id,))
        return self.cursor.fetchone()
    
    def import_menu_from_text(self, restaurant_id: int, menu_text: str) -> Tuple[int, int]:
        """Импортирует меню из текста в формате:
        - позиция1, цена
        - позиция2, цена
        """
        added = 0
        updated = 0
        
        try:
            lines = menu_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or not line.startswith('-'):
                    continue
                
                # Убираем дефис и пробелы
                line = line[1:].strip()
                
                # Парсим название и цену
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        try:
                            price = int(parts[1].strip().replace('р', '').replace('руб', '').strip())
                        except:
                            continue
                        
                        # Проверяем, есть ли уже такое блюдо
                        self.cursor.execute('''
                            SELECT id FROM menu_items 
                            WHERE restaurant_id = ? AND LOWER(name) = LOWER(?)
                        ''', (restaurant_id, name))
                        
                        existing = self.cursor.fetchone()
                        
                        if existing:
                            # Обновляем существующее
                            self.cursor.execute('''
                                UPDATE menu_items 
                                SET price = ?, is_available = 1
                                WHERE id = ?
                            ''', (price, existing[0]))
                            updated += 1
                        else:
                            # Добавляем новое
                            self.cursor.execute('''
                                INSERT INTO menu_items 
                                (restaurant_id, name, price, is_available)
                                VALUES (?, ?, ?, 1)
                            ''', (restaurant_id, name, price))
                            added += 1
            
            self.conn.commit()
            return added, updated
        except Exception as e:
            print(f"Import menu error: {e}")
            return 0, 0
    
    # ========== ЗАКАЗЫ ==========
    
    def create_order(self, user_id: int, restaurant_id: int, 
                    order_data: Dict, total_price: int, 
                    extra_money: int = 0) -> int:
        """Создает новый заказ"""
        try:
            # Дата на завтра (заказ делается на следующий день)
            order_date = (date.today() + timedelta(days=1)).isoformat()
            
            self.cursor.execute('''
                INSERT INTO pending_orders 
                (user_id, restaurant_id, order_data, total_price, 
                 extra_money, order_date, is_sent)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (user_id, restaurant_id, json.dumps(order_data, ensure_ascii=False), 
                  total_price, extra_money, order_date))
            
            order_id = self.cursor.lastrowid
            self.conn.commit()
            return order_id
        except Exception as e:
            print(f"Create order error: {e}")
            return 0
    
    def get_todays_pending_orders(self):
        """Получает заказы на сегодня (которые еще не отправлены)"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        self.cursor.execute('''
            SELECT po.id, po.user_id, po.restaurant_id, po.order_data,
                   po.total_price, po.extra_money, po.order_date, po.created_at,
                   u.full_name, u.office, r.name as restaurant_name
            FROM pending_orders po
            JOIN users u ON po.user_id = u.id
            JOIN restaurants r ON po.restaurant_id = r.id
            WHERE po.order_date = ? AND po.is_sent = 0
            ORDER BY r.name, u.full_name
        ''', (tomorrow,))
        return self.cursor.fetchall()
    
    def get_orders_for_restaurant(self, restaurant_id: int, sent_only: bool = False):
        """Получает заказы по ресторану"""
        query = '''
            SELECT po.id, po.user_id, po.restaurant_id, po.order_data,
                   po.total_price, po.extra_money, po.order_date, po.created_at,
                   u.full_name, u.office, r.name as restaurant_name
            FROM pending_orders po
            JOIN users u ON po.user_id = u.id
            JOIN restaurants r ON po.restaurant_id = r.id
            WHERE po.restaurant_id = ?
        '''
        
        if sent_only:
            query += ' AND po.is_sent = 1'
        else:
            query += ' AND po.is_sent = 0'
        
        query += ' ORDER BY po.order_date DESC, u.full_name'
        
        self.cursor.execute(query, (restaurant_id,))
        return self.cursor.fetchall()
    
    def mark_orders_as_sent(self, order_ids: List[int]) -> bool:
        """Помечает заказы как отправленные менеджеру"""
        try:
            # Переносим в архив
            self.cursor.execute(f'''
                INSERT INTO sent_orders 
                (original_order_id, user_id, restaurant_id, order_data,
                 total_price, extra_money, order_date)
                SELECT id, user_id, restaurant_id, order_data,
                       total_price, extra_money, order_date
                FROM pending_orders 
                WHERE id IN ({','.join('?' for _ in order_ids)})
            ''', order_ids)
            
            # Помечаем как отправленные
            self.cursor.execute(f'''
                UPDATE pending_orders 
                SET is_sent = 1
                WHERE id IN ({','.join('?' for _ in order_ids)})
            ''', order_ids)
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Mark orders as sent error: {e}")
            return False
    
    def get_all_orders_for_tomorrow(self):
        """Получает ВСЕ заказы на завтра (для отправки менеджеру)"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        self.cursor.execute('''
            SELECT po.id, po.user_id, po.restaurant_id, po.order_data,
                   po.total_price, po.extra_money, po.order_date, po.created_at,
                   u.full_name, u.office, r.name as restaurant_name
            FROM pending_orders po
            JOIN users u ON po.user_id = u.id
            JOIN restaurants r ON po.restaurant_id = r.id
            WHERE po.order_date = ? AND po.is_sent = 0
            ORDER BY r.name, u.full_name
        ''', (tomorrow,))
        return self.cursor.fetchall()
    
    # ========== УВЕДОМЛЕНИЯ О ДОСТАВКЕ ==========
    
    def get_users_for_restaurant_today(self, restaurant_id: int) -> List[int]:
        """Получает Telegram ID пользователей, которые заказали сегодня из ресторана"""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        self.cursor.execute('''
            SELECT DISTINCT u.telegram_id
            FROM pending_orders po
            JOIN users u ON po.user_id = u.id
            WHERE po.restaurant_id = ? 
              AND po.order_date = ?
              AND po.is_sent = 0
        ''', (restaurant_id, tomorrow))
        
        return [row[0] for row in self.cursor.fetchall()]
    
    def add_delivery_notification(self, restaurant_id: int, message: str, sent_by: int) -> bool:
        """Добавляет запись об отправленном уведомлении"""
        try:
            self.cursor.execute('''
                INSERT INTO delivery_notifications 
                (restaurant_id, message, sent_by)
                VALUES (?, ?, ?)
            ''', (restaurant_id, message, sent_by))
            
            self.conn.commit()
            return True
        except:
            return False
    
    def is_ordering_enabled_today(self) -> Tuple[bool, str]:
        """Проверяет, доступен ли заказ сегодня"""
        # Проверяем общую настройку
        settings = self.get_system_settings()
        if not settings or not settings[4]:  # order_enabled
            return False, "Заказы временно отключены"
        
        # Проверяем день недели
        today_weekday = datetime.now().weekday()  # 0=Понедельник
        enabled_days = json.loads(settings[3]) if settings[3] else []  # order_enabled_days
        
        if today_weekday not in enabled_days:
            day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            return False, f"Сегодня {day_names[today_weekday]}, заказы не принимаются"
        
        # Проверяем специальные настройки дня
        today = date.today()
        day_setting = self.get_day_setting(today)
        
        if day_setting:
            if not day_setting[3]:  # order_enabled
                return False, day_setting[4] if day_setting[4] else "Сегодня заказы отключены"
        
        return True, ""
    
    def is_deadline_passed(self) -> bool:
        """Проверяет, прошел ли дедлайн"""
        settings = self.get_system_settings()
        if not settings:
            return False
        
        # Проверяем специальные настройки дня
        today = date.today()
        day_setting = self.get_day_setting(today)
        
        deadline_time_str = None
        if day_setting and day_setting[2]:  # order_deadline_time из day_settings
            deadline_time_str = day_setting[2]
        
        if not deadline_time_str:
            deadline_time_str = settings[1]  # order_deadline_time из system_settings
        
        if not deadline_time_str:
            return False
        
        # Парсим время
        try:
            deadline_hour, deadline_minute = map(int, deadline_time_str.split(':'))
            current_time = datetime.now().time()
            deadline_time = datetime.now().replace(hour=deadline_hour, minute=deadline_minute, second=0).time()
            
            return current_time > deadline_time
        except:
            return False
    
    def get_day_setting(self, target_date: date):
        """Получает настройки для конкретного дня"""
        self.cursor.execute('''
            SELECT id, order_deadline_time, order_enabled, notes
            FROM day_settings
            WHERE target_date = ?
        ''', (target_date,))
        return self.cursor.fetchone()
    
    def close(self):
        self.conn.close()