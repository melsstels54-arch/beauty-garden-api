from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import os
from typing import List, Optional

app = FastAPI(title="Beauty Garden API")

# Разрешаем доступ с любых устройств
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модели данных
class Product(BaseModel):
    id: Optional[int] = None
    name: str
    category: str
    brand: str
    volume: int
    skin_type: str
    selling_price: float
    stock: int


class OrderItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: float


class Order(BaseModel):
    items: List[OrderItem]
    customer_name: str
    customer_phone: str
    delivery_address: str
    delivery_date: str


# Подключение к БД
def get_db():
    conn = sqlite3.connect('beauty_shop.db')
    conn.row_factory = sqlite3.Row
    return conn


# Инициализация базы данных
def init_database():
    conn = get_db()
    cursor = conn.cursor()

    # Создаем таблицы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            volume INTEGER,
            skin_type TEXT,
            purchase_price REAL,
            selling_price REAL,
            stock INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            delivery_date TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'новый',
            order_date TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES mobile_orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            email TEXT,
            address TEXT,
            work_hours TEXT,
            instagram TEXT,
            telegram TEXT
        )
    ''')

    # Проверяем, есть ли товары
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        # Добавляем тестовые товары из вашей БД
        products_data = [
            ("Увлажняющий крем", "крем", "La Roche-Posay", 50, "все типы", 800, 1500, 100),
            ("Очищающая пенка", "очищение", "CeraVe", 150, "все типы", 500, 950, 80),
            ("Гиалуроновая сыворотка", "сыворотка", "The Ordinary", 30, "все типы", 400, 750, 60),
            ("Мицеллярная вода", "очищение", "Bioderma", 250, "чувствительная", 600, 1200, 90),
            ("Тоник успокаивающий", "тоник", "Avene", 200, "чувствительная", 350, 700, 70),
            ("Восстанавливающий крем", "крем", "Vichy", 50, "сухая", 700, 1350, 50),
            ("Маттирующий тоник", "тоник", "Nuxe", 200, "жирная", 400, 800, 40),
            ("Пилинг для лица", "пилинг", "Clarins", 75, "все типы", 900, 1800, 30),
            ("Крем для глаз", "крем", "Kiehl's", 15, "чувствительная", 1100, 2200, 25),
            ("Сыворотка с витамином C", "сыворотка", "Loreal Paris", 30, "все типы", 600, 1200, 45),
        ]

        for product in products_data:
            cursor.execute('''
                INSERT INTO products (name, category, brand, volume, skin_type, purchase_price, selling_price, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', product)

    # Добавляем контакты
    cursor.execute("SELECT COUNT(*) FROM company_contacts")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO company_contacts (phone, email, address, work_hours, instagram, telegram)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "+7 (999) 123-45-67",
            "beauty.garden@shop.ru",
            "г. Москва, ул. Цветочная, д. 15",
            "Пн-Пт: 10:00-20:00, Сб-Вс: 11:00-18:00",
            "@beauty_garden",
            "@beauty_garden_bot"
        ))

    conn.commit()
    conn.close()


# API Endpoints
@app.get("/")
def root():
    return {"message": "Beauty Garden API", "version": "1.0", "status": "online"}


@app.get("/api/products", response_model=List[Product])
def get_products(search: Optional[str] = None, category: Optional[str] = None):
    conn = get_db()
    query = "SELECT id, name, category, brand, volume, skin_type, selling_price, stock FROM products WHERE stock > 0"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    if category and category != "все":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY name"
    products = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(product) for product in products]


@app.get("/api/categories")
def get_categories():
    conn = get_db()
    categories = conn.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL").fetchall()
    conn.close()
    return [{"name": cat[0]} for cat in categories]


@app.post("/api/orders")
def create_order(order: Order):
    conn = get_db()
    cursor = conn.cursor()

    order_number = f"BG{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_amount = sum(item.quantity * item.unit_price for item in order.items)
    order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        # Проверяем наличие
        for item in order.items:
            stock = cursor.execute("SELECT stock FROM products WHERE id = ?", (item.product_id,)).fetchone()
            if not stock or stock[0] < item.quantity:
                raise HTTPException(status_code=400, detail=f"Товар {item.product_id} отсутствует")

        # Создаем заказ
        cursor.execute('''
            INSERT INTO mobile_orders 
            (order_number, customer_name, customer_phone, delivery_address, delivery_date, total_amount, status, order_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, order.customer_name, order.customer_phone, order.delivery_address,
              order.delivery_date, total_amount, 'новый', order_date))

        order_id = cursor.lastrowid

        # Добавляем товары
        for item in order.items:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
            ''', (order_id, item.product_id, item.quantity, item.unit_price, item.quantity * item.unit_price))

            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item.quantity, item.product_id))

        conn.commit()
        return {"success": True, "order_number": order_number, "total_amount": total_amount}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/orders/{phone}")
def get_orders(phone: str):
    conn = get_db()
    orders = conn.execute('''
        SELECT id, order_number, customer_name, total_amount, status, order_date, delivery_address, delivery_date
        FROM mobile_orders 
        WHERE customer_phone = ?
        ORDER BY order_date DESC
    ''', (phone,)).fetchall()
    conn.close()
    return [dict(order) for order in orders]


@app.get("/api/contacts")
def get_contacts():
    conn = get_db()
    contacts = conn.execute("SELECT * FROM company_contacts ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(contacts) if contacts else {}


# Запуск
if __name__ == "__main__":
    init_database()
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)