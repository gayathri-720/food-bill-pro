from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import send_file
import io

app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE = "restaurant.db"

# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ---------------- DATABASE INIT ----------------

def init_db():
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    """)

    # MENU
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,
            category TEXT,
            price INTEGER
        )
    """)

    # ORDERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # ORDER ITEMS
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_name TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    # GROUPS
    c.execute("""
        CREATE TABLE IF NOT EXISTS groups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT UNIQUE
        )
    """)

    # GROUP MEMBERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS group_members(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            UNIQUE(group_id, user_id),
            FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # OFFERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS offers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            title TEXT,
            description TEXT,
            price INTEGER,
            expiry_datetime TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
        )
    """)

    # SAMPLE MENU
    c.execute("SELECT COUNT(*) FROM menu")
    if c.fetchone()[0] == 0:
        items = [
            ("Chicken Biryani", "Biryani", 250),
            ("Mutton Biryani", "Biryani", 320),
            ("Margherita Pizza", "Pizza", 299),
            ("Veg Burger", "Burger", 120),
            ("Cold Coffee", "Coffee", 90)
        ]
        c.executemany(
            "INSERT INTO menu (item_name, category, price) VALUES (?,?,?)",
            items
        )

    # DEFAULT ADMIN
    c.execute("SELECT * FROM users WHERE email='admin@gmail.com'")
    if not c.fetchone():
        admin_password = generate_password_hash("admin123")
        c.execute(
            "INSERT INTO users (name,email,password,is_admin) VALUES (?,?,?,1)",
            ("admin", "admin@gmail.com", admin_password)
        )

    conn.commit()
    conn.close()

init_db()

# ---------------- AUTH ----------------

@app.route("/")
def home():
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name,email,password) VALUES (?,?,?)",
                (name, email, password)
            )
            conn.commit()
        except:
            conn.close()
            return "Email already exists!"
        conn.close()
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["is_admin"] = user["is_admin"]
            session["cart"] = {}
            if user["is_admin"] == 1:
                return redirect("/admin/dashboard")
            else:
                return redirect("/menu")
        return "Invalid Credentials"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- MENU ----------------

@app.route("/menu")
def menu():
    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get("search")
    conn = get_db()

    if search:
        items = conn.execute(
            "SELECT * FROM menu WHERE item_name LIKE ? OR category LIKE ?",
            ('%' + search + '%', '%' + search + '%')
        ).fetchall()
    else:
        items = conn.execute("SELECT * FROM menu").fetchall()

    conn.close()
    return render_template("menu.html", items=items)

# ---------------- GROUP OFFERS ----------------

@app.route("/group/<int:group_id>")
def group_page(group_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()

    if not group:
        conn.close()
        return "Group not found"

    offers = conn.execute("""
        SELECT *
        FROM offers
        WHERE group_id=?
        AND datetime(expiry_datetime) > datetime('now')
    """, (group_id,)).fetchall()

    conn.close()
    return render_template("group_offers.html", group_name=group["group_name"], offers=offers)
@app.route("/admin/group/<int:group_id>", methods=["GET","POST"])
def admin_group(group_id):
    if not session.get("is_admin"):
        return redirect("/login")

    conn = get_db()
    group = conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
    if not group:
        conn.close()
        return "Group not found"

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        price = request.form["price"]
        expiry_datetime = request.form["expiry"]
        

       
        conn.execute("""
            INSERT INTO offers (group_id,title,description,price,expiry_datetime)
            VALUES (?,?,?,?,?)
        """, (group_id, title, description, price, expiry_datetime))
        conn.commit()

    offers = conn.execute("SELECT * FROM offers WHERE group_id=?", (group_id,)).fetchall()
    conn.close()

    return render_template("admin_group.html", group=group, offers=offers)

@app.route("/add_offer_to_cart", methods=["POST"])
def add_offer_to_cart():
    if "user_id" not in session:
        return redirect("/login")

    offer_id = request.form["offer_id"]
    quantity = int(request.form["quantity"])

    conn = get_db()
    offer = conn.execute("""
        SELECT *
        FROM offers
        WHERE id=?
        AND datetime(expiry_datetime) > datetime('now')
    """, (offer_id,)).fetchone()

    if not offer:
        conn.close()
        return "Offer expired or invalid"

    member = conn.execute("""
        SELECT *
        FROM group_members
        WHERE group_id=? AND user_id=?
    """, (offer["group_id"], session["user_id"])).fetchone()
    conn.close()

    if not member:
        return "Unauthorized"

    cart = session.get("cart", {})
    key = f"offer_{offer_id}"

    if key in cart:
        cart[key]["quantity"] += quantity
    else:
        cart[key] = {
            "name": offer["title"],
            "price": offer["price"],
            "quantity": quantity
        }

    session["cart"] = cart
    return redirect("/cart")

# ---------------- CART OPERATIONS ----------------

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if "user_id" not in session:
        return redirect("/login")
        
    item_id = request.form.get("item_id")
    quantity = int(request.form.get("quantity", 1))

    conn = get_db()
    item = conn.execute("SELECT id, item_name, price FROM menu WHERE id=?", (item_id,)).fetchone()
    conn.close()

    if not item:
        return redirect("/menu")

    cart = session.get("cart", {})
    if item_id in cart:
        cart[item_id]["quantity"] += quantity
    else:
        cart[item_id] = {
            "name": item["item_name"],
            "price": item["price"],
            "quantity": quantity
        }

    session["cart"] = cart
    return redirect("/cart")

@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect("/login")

    cart = session.get("cart", {})
    total = sum(int(item["price"]) * int(item["quantity"]) for item in cart.values())
    return render_template("cart.html", cart=cart, total=total)

@app.route("/remove_from_cart/<key>")
def remove_from_cart(key):
    cart = session.get("cart", {})
    if key in cart:
        cart.pop(key)
        session["cart"] = cart
    return redirect("/cart")

@app.route("/clear_cart")
def clear_cart():
    session.pop("cart", None)
    return redirect("/cart")

# ---------------- CHECKOUT & GROUPS ----------------

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        return redirect("/login")

    cart = session.get("cart")
    if not cart:
        return redirect("/cart")

    if request.method == "POST":
        payment_method = request.form.get("payment_method")
        conn = get_db()
        cur = conn.execute("INSERT INTO orders (user_id) VALUES (?)", (session["user_id"],))
        order_id = cur.lastrowid

        for item in cart.values():
            conn.execute("INSERT INTO order_items (order_id, item_name) VALUES (?,?)", (order_id, item["name"]))

        # Group Formation Logic
        for item in cart.values():
            if item["name"].startswith("Offer"): continue

            users = conn.execute("""
                SELECT DISTINCT o.user_id FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                WHERE oi.item_name=?
            """, (item["name"],)).fetchall()

            if len(users) >= 2:
                group_name = f"{item['name']} Lovers"
                group = conn.execute("SELECT * FROM groups WHERE group_name=?", (group_name,)).fetchone()
                
                if not group:
                    cur = conn.execute("INSERT INTO groups (group_name) VALUES (?)", (group_name,))
                    group_id = cur.lastrowid
                else:
                    group_id = group["id"]

                for u in users:
                    conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?,?)", (group_id, u["user_id"]))

        conn.commit()
        conn.close()
        session.pop("cart", None)
        return render_template("order_success.html", method=payment_method)

    return render_template("checkout.html")

@app.route("/my_groups")
def my_groups():
    if not session.get("user_id"):
        return redirect("/login")

    conn = get_db()
    groups_data = conn.execute("""
        SELECT g.* FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
    """, (session["user_id"],)).fetchall()

    groups = []
    for group in groups_data:
        members = conn.execute("SELECT u.name FROM users u JOIN group_members gm ON u.id = gm.user_id WHERE gm.group_id = ?", (group["id"],)).fetchall()
        offers = conn.execute("SELECT * FROM offers WHERE group_id = ?", (group["id"],)).fetchall()
        groups.append({"id": group["id"], "group_name": group["group_name"], "members": members, "offers": offers})

    conn.close()
    return render_template("my_groups.html", groups=groups)

# ---------------- ADMIN PANEL ----------------

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect("/login")

    conn = get_db()
    groups = conn.execute("""
        SELECT g.id, g.group_name, COUNT(gm.user_id) as total_members
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        GROUP BY g.id
    """).fetchall()
    conn.close()
    return render_template("admin_dashboard.html", groups=groups)

@app.route("/admin_post_offer", methods=["GET", "POST"])
def admin_post_offer():
    if not session.get("is_admin"):
        return "Unauthorized"

    conn = get_db()
    if request.method == "POST":
        group_id, title = request.form["group_id"], request.form["title"]
        description, price = request.form["description"], request.form["price"]
        expiry_datetime = f"{request.form['expiry_date']} {request.form['expiry_time']}"

        conn.execute("INSERT INTO offers (group_id,title,description,price,expiry_datetime) VALUES (?,?,?,?,?)",
                     (group_id, title, description, price, expiry_datetime))
        conn.commit()

    groups = conn.execute("SELECT * FROM groups").fetchall()
    conn.close()
    return render_template("admin_offer.html", groups=groups)

@app.route("/claim_offer/<int:offer_id>", methods=["POST"])
def claim_offer(offer_id):
    if not session.get("user_id"):
        return redirect("/login")

    conn = sqlite3.connect("restaurant.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get offer
    cursor.execute("SELECT * FROM offers WHERE id=?", (offer_id,))
    offer = cursor.fetchone()

    if not offer:
        conn.close()
        return "Offer not found"

    # ✅ Check expiry
    cursor.execute("""
        SELECT * FROM offers
        WHERE id=?
        AND datetime(expiry_datetime) > datetime('now')
    """, (offer_id,))
    
    if not cursor.fetchone():
        conn.close()
        return "Offer expired"

    # ✅ Check claim limit
    if offer["claimed_count"] >= offer["max_claims"]:
        conn.close()
        return "Offer Sold Out!"

    # ✅ Increase claim count IMMEDIATELY
    cursor.execute("""
        UPDATE offers
        SET claimed_count = claimed_count + 1
        WHERE id=? AND claimed_count < max_claims
    """, (offer_id,))

    conn.commit()

    # Check if update actually happened
    if cursor.rowcount == 0:
        conn.close()
        return "Offer Sold Out!"

    conn.close()

    return "Offer Claimed Successfully!"
@app.route("/orders")
def order_history():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    # Get all orders of current user
    orders_data = conn.execute("""
        SELECT * FROM orders
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    orders = []

    for order in orders_data:
        order_id = order["id"]

        items = conn.execute("""
            SELECT oi.item_name, m.price
            FROM order_items oi
            LEFT JOIN menu m ON oi.item_name = m.item_name
            WHERE oi.order_id=?
        """, (order_id,)).fetchall()

        total = 0
        for item in items:
            if item["price"]:
                total += item["price"]

        orders.append({
            "id": order_id,
            "created_at": order["created_at"],
            "items": items,
            "total": total
        })

    conn.close()

    return render_template("order_history.html", orders=orders)
@app.route("/supplier_dashboard")
def supplier_dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("supplier_dashboard.html")
@app.route("/add_supplier_item", methods=["POST"])
def add_supplier_item():
    if "user_id" not in session:
        return redirect("/login")

    item_name = request.form["item_name"]
    category = request.form["category"]
    price = request.form["price"]
    quantity = request.form["quantity"]
    location = request.form["location"]
    contact = request.form["contact"]

    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO supplier_items
        (user_id, item_name, category, price_per_kg, quantity, location, contact)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session["user_id"], item_name, category, price, quantity, location, contact))

    conn.commit()
    conn.close()

    return redirect("/view_my_listings")
@app.route("/admin_suppliers")
def admin_suppliers():

    category = request.args.get("category")
    sort = request.args.get("sort")

    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()

    query = """
        SELECT users.name,
               supplier_items.item_name,
               supplier_items.category,
               supplier_items.price_per_kg,
               supplier_items.quantity,
               supplier_items.location,
               supplier_items.contact,
               supplier_items.created_at
        FROM supplier_items
        JOIN users ON supplier_items.user_id = users.id
    """

    conditions = []
    params = []

    # Filter by category
    if category and category != "All":
        conditions.append("supplier_items.category = ?")
        params.append(category)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Sort by price
    if sort == "low":
        query += " ORDER BY supplier_items.price_per_kg ASC"
    else:
        query += " ORDER BY supplier_items.created_at DESC"

    cursor.execute(query, params)
    items = cursor.fetchall()

    # Get distinct categories for dropdown
    cursor.execute("SELECT DISTINCT category FROM supplier_items")
    categories = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        "admin_suppliers.html",
        items=items,
        categories=categories,
        selected_category=category,
        selected_sort=sort
    )
@app.route("/view_my_listings")
def view_my_listings():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM supplier_items
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],))

    items = cursor.fetchall()
    conn.close()

    return render_template("view_my_listings.html", items=items)


@app.route("/admin/add_special", methods=["GET", "POST"])
def add_special():
    if session.get("is_admin") != 1:
        return redirect("/login")

    if request.method == "POST":
        item_name = request.form["item_name"]
        category = request.form["category"]
        price = request.form["price"]

        today = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect("restaurant.db")
        cursor = conn.cursor()

        # Delete old specials (yesterday and before)
        cursor.execute("DELETE FROM specials WHERE DATE(created_at) != ?", (today,))

        # Insert new special
        cursor.execute(
            "INSERT INTO specials (item_name, category, price) VALUES (?, ?, ?)",
            (item_name, category, price)
        )

        conn.commit()
        conn.close()

        return redirect("/admin/dashboard")

    return render_template("add_special.html")
@app.route("/today_special")
def today_special():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM specials ORDER BY created_at DESC")
    specials = cursor.fetchall()
    conn.close()

    return render_template("today_special.html", specials=specials)
@app.route("/add_special_to_cart", methods=["POST"])
def add_special_to_cart():
    if "user_id" not in session:
        return redirect("/login")

    item_id = request.form.get("item_id")
    quantity = int(request.form.get("quantity", 1))

    conn = get_db()
    item = conn.execute(
        "SELECT id, item_name, price FROM specials WHERE id=?",
        (item_id,)
    ).fetchone()
    conn.close()

    if not item:
        return redirect("/today_special")

    cart = session.get("cart", {})

    # Important: Use a unique key so it doesn’t clash with menu items
    special_key = f"special_{item_id}"

    if special_key in cart:
        cart[special_key]["quantity"] += quantity
    else:
        cart[special_key] = {
            "name": item["item_name"],
            "price": item["price"],
            "quantity": quantity
        }

    session["cart"] = cart
    return redirect("/cart")
@app.route("/diet_menu", methods=["GET", "POST"])
def diet_menu():
    if "user_id" not in session:
        return redirect("/login")
    
    if request.method == "POST":
        name = request.form["name"]
        shift = request.form["shift"]
        mobile = request.form["mobile"]
        days = request.form["days"]
        months = request.form["months"]
        liquids = request.form["liquids"]
        nonveg = request.form["nonveg"]
        food_items = request.form["food_items"]
        
        conn = get_db()
        conn.execute("""
            INSERT INTO diet_menu_requests
            (user_id, name, shift, mobile, days, months, liquids, nonveg, food_items)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["user_id"], name, shift, mobile, days, months, liquids, nonveg, food_items))
        conn.commit()
        conn.close()
        return "Diet menu request submitted successfully!"
    
    return render_template("diet_menu.html")
@app.route("/admin/diet_requests/<int:request_id>/<action>")
def update_diet_status(request_id, action):
    # Only admin can update
    if session.get("is_admin") != 1:
        return redirect("/login")
    
    if action not in ["Accept", "Reject"]:
        return "Invalid action"
    
    conn = get_db()
    conn.execute("update diet_menu_requests SET status=? WHERE id=?", (action, request_id))
    conn.commit()
    conn.close()
    
    return redirect("/admin/diet_requests")
@app.route("/admin/diet_requests")
def admin_diet_requests():
    # Only admin can access
    if session.get("is_admin") != 1:
        return redirect("/login")
    
    conn = get_db()
    requests = conn.execute("SELECT * FROM diet_menu_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return render_template("admin_diet_requests.html", requests=requests)
@app.route("/my_diet_requests")
def my_diet_requests():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()
    requests = conn.execute(
        "SELECT * FROM diet_menu_requests WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    return render_template("my_diet_requests.html", requests=requests)
@app.route("/download_diet_menu/<int:request_id>")
def download_diet_menu(request_id):
    if "user_id" not in session:
        return redirect("/login")
    
    user_id = session["user_id"]
    conn = get_db()
    request_data = conn.execute(
        "SELECT * FROM diet_menu_requests WHERE id=? AND user_id=?",
        (request_id, user_id)
    ).fetchone()
    conn.close()

    if not request_data:
        return "Request not found"
    
    if request_data["status"] != "Accept":
        return "Admin has not accepted this request yet"

    # Create text content
    content = f"""
Diet Menu Request
-----------------
Name: {request_data['name']}
Shift: {request_data['shift']}
Mobile: {request_data['mobile']}
Days: {request_data['days']}
Months: {request_data['months']}
Liquids: {request_data['liquids']}
Non-Veg: {request_data['nonveg']}
Food Items: {request_data['food_items']}
Status: {request_data['status']}
Submitted At: {request_data['created_at']}
"""

    # Send as downloadable file
    return send_file(
        io.BytesIO(content.encode('utf-8')),
        as_attachment=True,
        download_name=f"DietMenu_{request_data['id']}.txt",
        mimetype="text/plain"
    )
if __name__ == "__main__":
    app.run(debug=True)