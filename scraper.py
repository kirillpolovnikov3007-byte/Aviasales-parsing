import os
import sqlite3
import requests
from datetime import datetime

# Берем токен из секретов окружения GitHub
TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN")

DB_NAME = 'flights_history.db'
ORIGIN = "MOW"
DESTINATION = "SVX"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prices_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_date TEXT,          
        origin TEXT,               
        destination TEXT,          
        departure_at TEXT,         
        departure_date TEXT,       
        return_at TEXT,            
        airline TEXT,              
        flight_number TEXT,        
        transfers INTEGER,         
        price INTEGER,             
        days_to_departure INTEGER  
    )
    ''')
    conn.commit()
    conn.close()

def fetch_and_save_airfares(origin, destination, token):
    if not token:
        print("Ошибка: Токен Travelpayouts не найден в переменных окружения!")
        return

    url = "https://travelpayouts.com"
    headers = {
        "X-Access-Token": token,
        "Accept-Encoding": "gzip, deflate"
    }
    
    params = {
        "origin": origin,
        "destination": destination,
        "currency": "rub",
        "one_way": "true", 
        "limit": 100        
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            print(f"Ошибка API {response.status_code}: {response.text[:200]}")
            return
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети: {e}")
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
            
        try:
            # Извлекаем 'YYYY-MM-DD' из строки вроде '2026-08-15T10:20:00+03:00'
            dep_date_str = dep_at_str.split('T')[0]
            dep_date = datetime.strptime(dep_date_str, '%Y-%m-%d').date()
            days_to_departure = (dep_date - current_search_date).days
        except Exception as e:
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
            str(item.get('flight_number', '')), 
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
    print(f"Успешно сохранено {len(records_to_insert)} строк для {origin} -> {destination}")

if __name__ == "__main__":
    init_db()
    fetch_and_save_airfares(ORIGIN, DESTINATION, TOKEN)
    fetch_and_save_airfares(DESTINATION, ORIGIN, TOKEN)
