import os
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (создайте рядом файл .env с текстом: TRAVELPAYOUTS_TOKEN=ваш_токен)
load_dotenv()
TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")

if not TOKEN:
    raise ValueError("Критическая ошибка: Переменная TRAVELPAYOUTS_TOKEN не передана!")

DB_NAME = 'flights_history.db'
ORIGIN = "MOW"
DESTINATION = "SVX"

def init_db():
    """Инициализация базы данных с расширенной структурой."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prices_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_date TEXT,          -- Когда собрали данные (YYYY-MM-DD HH:MM:SS)
        origin TEXT,               -- ИАТА код вылета
        destination TEXT,          -- ИАТА код прилета
        departure_at TEXT,         -- Дата и время вылета (ISO)
        departure_date TEXT,       -- Чистая дата вылета (для удобства группировки YYYY-MM-DD)
        return_at TEXT,            -- Дата возвращения
        airline TEXT,              -- Авиакомпания
        flight_number TEXT,        -- Номер рейса (лучше TEXT, бывают буквы)
        transfers INTEGER,         -- Пересадки
        price INTEGER,             -- Цена
        days_to_departure INTEGER  -- Главная метрика: за сколько дней до вылета смотрим цену
    )
    ''')
    conn.commit()
    conn.close()

def fetch_and_save_airfares(origin, destination, token):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    headers = {
        "X-Access-Token": token,
        "Accept-Encoding": "gzip, deflate"
    }
    
    # Чтобы собирать глубокие данные, не ограничиваемся текущим месяцем.
    # Оставив departure_at пустым или задав период, мы получаем более широкую картину.
    params = {
        "origin": origin,
        "destination": destination,
        "currency": "rub",
        "one_way": "true", # Для продуктового анализа проще анализировать One-Way (туда и обратно отдельно)
        "limit": 100        # Берем больше записей для хорошей выборки
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Ошибка API {response.status_code}: {response.text[:200]}")
            return
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при запросе {origin}->{destination}: {e}")
        return
        
    data = response.json().get('data', [])
    if not data:
        print(f"Данные от API для {origin}->{destination} пусты.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    now = datetime.now()
    current_search_time = now.strftime('%Y-%m-%d %H:%M:%S')
    current_search_date = now.date()
    
    records_to_insert = []
    for item in data:
        dep_at_str = item.get('departure_at', '')
        if not dep_at_str:
            continue
            
        # Парсим дату вылета для расчета дней до вылета
        try:
            # API возвращает '2026-08-15T10:20:00+03:00' или '2026-08-15'
            dep_date_str = dep_at_str.split('T')[0]
            dep_date = datetime.strptime(dep_date_str, '%Y-%m-%d').date()
            days_to_departure = (dep_date - current_search_date).days
        except Exception:
            dep_date_str = None
            days_to_departure = None

        records_to_insert.append((
            current_search_time,
            item.get('origin'),
            item.get('destination'),
            dep_at_str,
            dep_date_str,
            item.get('return_at'),
            item.get('airline'),
            str(item.get('flight_number', '')), # Приводим к строке
            item.get('transfers'),
            item.get('price'),
            days_to_departure
        ))
        
    cursor.executemany('''
    INSERT INTO prices_history 
    (search_date, origin, destination, departure_at, departure_date, return_at, airline, flight_number, transfers, price, days_to_departure)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', records_to_insert)
    
    conn.commit()
    conn.close()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Сохранено {len(records_to_insert)} строк для {origin} -> {destination}")

if __name__ == "__main__":
    init_db()
    fetch_and_save_airfares(ORIGIN, DESTINATION, TOKEN)
    fetch_and_save_airfares(DESTINATION, ORIGIN, TOKEN)
