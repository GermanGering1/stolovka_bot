import json
import random
from typing import List, Dict
from database import Database

db = Database()

class MenuScraper:
    """Мок-скрапер для демонстрации"""
    
    @staticmethod
    def scrape_restaurant(restaurant_name: str) -> List[Dict]:
        """Возвращает мок-меню для ресторана"""
        menus = {
            "Сицилия": [
                {"name": "Пицца Маргарита 30см", "price": 450, "description": "Сыр, томаты, базилик"},
                {"name": "Пицца Пепперони 30см", "price": 520, "description": "Пепперони, сыр, соус"},
                {"name": "Паста Карбонара", "price": 380, "description": "Спагетти, бекон, сливки, яйцо"},
                {"name": "Салат Цезарь", "price": 320, "description": "Курица, салат, сухарики, соус"},
                {"name": "Кока-Кола 0.5л", "price": 120, "description": "Газированный напиток"},
                {"name": "Фанта 0.5л", "price": 120, "description": "Апельсиновый напиток"},
            ],
            "Макдональдс": [
                {"name": "Биг Мак", "price": 210, "description": "Бургер с двумя котлетами"},
                {"name": "Чикенбургер", "price": 130, "description": "Куриный бургер"},
                {"name": "Картофель фри средний", "price": 110, "description": "Обжаренный картофель"},
                {"name": "Наггетсы 6шт", "price": 180, "description": "Куриные наггетсы"},
                {"name": "Кока-Кола 0.4л", "price": 150, "description": "Газировка"},
                {"name": "Молочный коктейль", "price": 200, "description": "Ванильный коктейль"},
            ],
            "Суши Вок": [
                {"name": "Филадельфия ролл", "price": 380, "description": "Лосось, сыр, огурец"},
                {"name": "Калифорния ролл", "price": 350, "description": "Краб, авокадо, огурец"},
                {"name": "Рис с курицей", "price": 280, "description": "Жареный рис с курицей"},
                {"name": "Суп том ям", "price": 320, "description": "Острый тайский суп"},
                {"name": "Зеленый чай", "price": 80, "description": "Традиционный чай"},
                {"name": "Спринг роллы", "price": 220, "description": "Овощные роллы"},
            ],
            "Бургер Кинг": [
                {"name": "Воппер", "price": 250, "description": "Классический бургер"},
                {"name": "Чизбургер", "price": 180, "description": "Бургер с сыром"},
                {"name": "Картофель фри большой", "price": 140, "description": "Большая порция"},
                {"name": "Луковые кольца", "price": 160, "description": "Хрустящие кольца"},
                {"name": "Шейк ванильный", "price": 220, "description": "Молочный коктейль"},
                {"name": "Кока-Кола 0.5л", "price": 130, "description": "Газировка"},
            ]
        }
        
        return menus.get(restaurant_name, [])
    
    @staticmethod
    def import_scraped_menu(restaurant_id: int, restaurant_name: str) -> tuple:
        """Импортирует скрапленное меню в БД"""
        scraped_items = MenuScraper.scrape_restaurant(restaurant_name)
        
        if not scraped_items:
            return 0, 0, "Меню для этого ресторана не найдено"
        
        added = 0
        updated = 0
        
        for item in scraped_items:
            # Проверяем, есть ли уже такое блюдо
            db.cursor.execute('''
                SELECT id FROM menu_items 
                WHERE restaurant_id = ? AND LOWER(name) = LOWER(?)
            ''', (restaurant_id, item['name']))
            
            existing = db.cursor.fetchone()
            
            if existing:
                # Обновляем цену
                db.cursor.execute('''
                    UPDATE menu_items 
                    SET price = ?, description = ?, is_available = 1
                    WHERE id = ?
                ''', (item['price'], item.get('description'), existing[0]))
                updated += 1
            else:
                # Добавляем новое
                db.cursor.execute('''
                    INSERT INTO menu_items 
                    (restaurant_id, name, price, description, is_available)
                    VALUES (?, ?, ?, ?, 1)
                ''', (restaurant_id, item['name'], item['price'], item.get('description')))
                added += 1
        
        db.conn.commit()
        
        return added, updated, f"Добавлено: {added}, Обновлено: {updated}"