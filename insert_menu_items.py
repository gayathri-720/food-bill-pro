import sqlite3

# ===============================================
# CONNECT USING FULL PATH (IMPORTANT)
# ===============================================

db_path = r"C:\Users\windows\Desktop\food\restaurant.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("Connected to database successfully")

# ===============================================
# STEP 1 — CREATE TABLE IF NOT EXISTS
# ===============================================

c.execute("""
CREATE TABLE IF NOT EXISTS menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT UNIQUE,
    category TEXT,
    price INTEGER,
    image TEXT
)
""")

print("Menu table ready")

# ===============================================
# STEP 2 — ADD IMAGE COLUMN IF MISSING
# ===============================================

try:
    c.execute("ALTER TABLE menu ADD COLUMN image TEXT")
    print("Image column added")
except:
    print("Image column already exists")

# ===============================================
# STEP 3 — ITEMS WITH IMAGES
# ===============================================

new_items = [
    ("Veg Biryani", "Biryani", 200, "veg_biryani.jpg"),
    ("Paneer Biryani", "Biryani", 230, "paneer_biryani.jpg"),
    ("Pepperoni Pizza", "Pizza", 349, "pepperoni_pizza.jpg"),
    ("Farmhouse Pizza", "Pizza", 329, "farmhouse_pizza.jpg"),
    ("Chicken Burger", "Burger", 150, "chicken_burger.jpg"),
    ("Cheese Burger", "Burger", 140, "cheese_burger.jpg"),
    ("Hot Coffee", "Coffee", 70, "hot_coffee.jpg"),
    ("Cappuccino", "Coffee", 110, "cappuccino.jpg"),
    ("French Fries", "Snacks", 100, "fries.jpg"),
    ("Garlic Bread", "Snacks", 130, "garlic_bread.jpg"),
    ("Samosa", "Snacks", 40, "samosa.jpg"),
    ("Spring Rolls", "Snacks", 150, "spring_rolls.jpg"),
    ("Chocolate Shake", "Beverages", 120, "choco_shake.jpg"),
    ("Mango Juice", "Beverages", 80, "mango_juice.jpg"),
    ("Lime Soda", "Beverages", 60, "lime_soda.jpg")
]

# ===============================================
# STEP 4 — INSERT SAFELY
# ===============================================

inserted_count = 0

for item in new_items:
    c.execute("SELECT * FROM menu WHERE item_name=?", (item[0],))
    if not c.fetchone():
        c.execute("""
            INSERT INTO menu (item_name, category, price, image)
            VALUES (?, ?, ?, ?)
        """, item)
        inserted_count += 1

# ===============================================
# SAVE & CLOSE
# ===============================================

conn.commit()
conn.close()

print(f"{inserted_count} new items inserted successfully.")
print("Database updated safely with images.")