from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime
from typing import List, Optional

app = FastAPI(title="Beauty Garden API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Product(BaseModel):
    name: str
    category: str = ""
    brand: str = ""
    volume: int = 0
    skin_type: str = "все типы"
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


def get_db():
    conn = sqlite3.connect('beauty_shop.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

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
            total_price REAL NOT NULL
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

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        test_products = [
            ("Увлажняющий крем", "крем", "La Roche-Posay", 50, "все типы", 800, 1500, 100),
            ("Очищающая пенка", "очищение", "CeraVe", 150, "все типы", 500, 950, 80),
            ("Гиалуроновая сыворотка", "сыворотка", "The Ordinary", 30, "все типы", 400, 750, 60),
        ]
        for p in test_products:
            cursor.execute('''
                INSERT INTO products (name, category, brand, volume, skin_type, purchase_price, selling_price, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', p)

    cursor.execute("SELECT COUNT(*) FROM company_contacts")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO company_contacts (phone, email, address, work_hours, instagram, telegram)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("+7 (999) 123-45-67", "beauty.garden@shop.ru", "г. Москва, ул. Цветочная, д. 15",
              "Пн-Пт: 10:00-20:00", "@beauty_garden", "@beauty_garden_bot"))

    conn.commit()
    conn.close()
    print("✅ DB initialized")


@app.get("/")
def root():
    return {"message": "Beauty Garden API", "status": "online"}


@app.get("/api/products")
def get_products():
    conn = get_db()
    products = conn.execute(
        "SELECT id, name, category, brand, volume, skin_type, selling_price, stock FROM products WHERE stock > 0").fetchall()
    conn.close()
    return [dict(p) for p in products]


@app.get("/api/categories")
def get_categories():
    conn = get_db()
    categories = conn.execute(
        "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''").fetchall()
    conn.close()
    return [{"name": cat[0]} for cat in categories]


@app.post("/api/orders")
def create_order(order: Order):
    conn = get_db()
    cursor = conn.cursor()
    order_number = f"BG{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_amount = sum(item.quantity * item.unit_price for item in order.items)
    order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for item in order.items:
        stock = cursor.execute("SELECT stock FROM products WHERE id = ?", (item.product_id,)).fetchone()
        if not stock or stock[0] < item.quantity:
            raise HTTPException(status_code=400, detail="Товара нет")

    cursor.execute('''
        INSERT INTO mobile_orders (order_number, customer_name, customer_phone, delivery_address, delivery_date, total_amount, order_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (order_number, order.customer_name, order.customer_phone, order.delivery_address, order.delivery_date,
          total_amount, order_date))

    order_id = cursor.lastrowid

    for item in order.items:
        cursor.execute('''
            INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, item.product_id, item.quantity, item.unit_price, item.quantity * item.unit_price))
        cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item.quantity, item.product_id))

    conn.commit()
    conn.close()
    return {"success": True, "order_number": order_number, "total_amount": total_amount}


@app.get("/api/orders/{phone}")
def get_orders(phone: str):
    conn = get_db()
    orders = conn.execute('''
        SELECT id, order_number, customer_name, total_amount, status, order_date, delivery_address, delivery_date
        FROM mobile_orders WHERE customer_phone = ? ORDER BY order_date DESC
    ''', (phone,)).fetchall()
    conn.close()
    return [dict(o) for o in orders]


@app.get("/api/contacts")
def get_contacts():
    conn = get_db()
    contacts = conn.execute("SELECT * FROM company_contacts ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if contacts:
        return dict(contacts)
    return {"phone": "+7 (999) 123-45-67", "email": "beauty.garden@shop.ru",
            "address": "г. Москва, ул. Цветочная, д. 15", "work_hours": "Пн-Пт: 10:00-20:00",
            "instagram": "@beauty_garden", "telegram": "@beauty_garden_bot"}


if __name__ == "__main__":
    init_db()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)