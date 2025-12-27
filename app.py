import os
import uuid
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import psycopg

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ================= CONFIG =================

UPLOAD_FOLDER = "static/uploads/profile"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
MAX_FILE_SIZE = 2 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= DATABASE =================

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return psycopg.connect(db_url, sslmode="require")

def init_db():
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Users table (Existing)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                mobile VARCHAR(15) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                profile_photo VARCHAR(255),
                email VARCHAR(100),
                address TEXT,
                city VARCHAR(50),
                state VARCHAR(50),
                pincode VARCHAR(10),
                user_id VARCHAR(20) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Services table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                service_number INTEGER UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                image_url TEXT,
                price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(5, 2) DEFAULT 0,
                description TEXT,
                category VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Service Items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS service_items (
                id SERIAL PRIMARY KEY,
                service_id INTEGER REFERENCES services(id) ON DELETE CASCADE,
                item_number INTEGER NOT NULL,
                name VARCHAR(200) NOT NULL,
                image_url TEXT,
                price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(5, 2) DEFAULT 0,
                description TEXT,
                is_available BOOLEAN DEFAULT TRUE,
                UNIQUE(service_id, item_number)
            )
        """)
        
        # Menu Categories table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu_categories (
                id SERIAL PRIMARY KEY,
                category_number INTEGER UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                image_url TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Menu Items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                category_id INTEGER REFERENCES menu_categories(id) ON DELETE CASCADE,
                item_number INTEGER NOT NULL,
                name VARCHAR(200) NOT NULL,
                image_url TEXT,
                price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(5, 2) DEFAULT 0,
                description TEXT,
                is_available BOOLEAN DEFAULT TRUE,
                UNIQUE(category_id, item_number)
            )
        """)
        
        # Cart table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_id VARCHAR(100),
                item_type VARCHAR(20) NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                price_at_add DECIMAL(10, 2) NOT NULL,
                discount_at_add DECIMAL(5, 2) DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Orders table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number VARCHAR(20) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                total_amount DECIMAL(10, 2) NOT NULL,
                discount_amount DECIMAL(10, 2) DEFAULT 0,
                final_amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(50),
                payment_status VARCHAR(20) DEFAULT 'pending',
                delivery_address TEXT,
                delivery_city VARCHAR(50),
                delivery_state VARCHAR(50),
                delivery_pincode VARCHAR(10),
                delivery_instructions TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Order Items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                item_type VARCHAR(20) NOT NULL,
                item_id INTEGER NOT NULL,
                item_name VARCHAR(200) NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(5, 2) DEFAULT 0,
                total_price DECIMAL(10, 2) NOT NULL
            )
        """)
        
        # Insert sample data if tables are empty
        cur.execute("SELECT COUNT(*) FROM services")
        if cur.fetchone()[0] == 0:
            # Insert sample services
            sample_services = [
                (101, 'Web Development', 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=300&fit=crop', 999.99, 20, 'Complete web development solutions', 'IT'),
                (102, 'Mobile App Development', 'https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=400&h=300&fit=crop', 1499.99, 15, 'Native and cross-platform apps', 'IT'),
                (103, 'Digital Marketing', 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&h=300&fit=crop', 799.99, 25, 'Boost your online presence', 'Marketing'),
                (104, 'Graphic Design', 'https://images.unsplash.com/photo-1634942537034-2531766767d1?w=400&h=300&fit=crop', 599.99, 10, 'Creative designs for branding', 'Design'),
                (105, 'SEO Optimization', 'https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=400&h=300&fit=crop', 499.99, 30, 'Improve search engine rankings', 'Marketing'),
                (106, 'Content Writing', 'https://images.unsplash.com/photo-1455390582262-044cdead277a?w=400&h=300&fit=crop', 299.99, 5, 'Professional content creation', 'Writing')
            ]
            
            for service in sample_services:
                cur.execute("""
                    INSERT INTO services (service_number, name, image_url, price, discount, description, category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, service)
            
            # Insert sample menu categories
            sample_categories = [
                (201, 'Appetizers', 'Start your meal right', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=400&h=300&fit=crop'),
                (202, 'Main Course', 'Hearty and delicious', 'https://images.unsplash.com/photo-1563379926898-05f4575a45d8?w=400&h=300&fit=crop'),
                (203, 'Desserts', 'Sweet endings', 'https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?w=400&h=300&fit=crop'),
                (204, 'Beverages', 'Refreshing drinks', 'https://images.unsplash.com/photo-1560512823-829485b8bf24?w=400&h=300&fit=crop'),
                (205, 'Specials', 'Chef recommendations', 'https://images.unsplash.com/photo-1559847844-5315695dadae?w=400&h=300&fit=crop')
            ]
            
            for category in sample_categories:
                cur.execute("""
                    INSERT INTO menu_categories (category_number, name, description, image_url)
                    VALUES (%s, %s, %s, %s)
                """, category)
        
        conn.commit()
    conn.close()

# ================= HELPERS =================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_by_mobile(mobile):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE mobile=%s", (mobile,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            conn.close()
            return dict(zip(cols, row))
    conn.close()
    return None

def get_user_by_id(uid):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            conn.close()
            return dict(zip(cols, row))
    conn.close()
    return None

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def generate_user_id(name):
    # Generate unique user ID: First 3 letters of name + random 4 digits
    prefix = name[:3].upper()
    random_digits = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{random_digits}"

def get_all_services():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM services 
            WHERE is_active = TRUE 
            ORDER BY service_number
        """)
        rows = cur.fetchall()
        if rows:
            cols = [d[0] for d in cur.description]
            services = [dict(zip(cols, row)) for row in rows]
            conn.close()
            
            # Calculate final price
            for service in services:
                service['final_price'] = service['price'] * (1 - (service['discount'] or 0)/100)
            return services
    conn.close()
    return []

def get_all_menu_categories():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM menu_categories 
            WHERE is_active = TRUE 
            ORDER BY category_number
        """)
        rows = cur.fetchall()
        if rows:
            cols = [d[0] for d in cur.description]
            conn.close()
            return [dict(zip(cols, row)) for row in rows]
    conn.close()
    return []

def get_menu_items_by_category(category_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT mi.*, mc.name as category_name 
            FROM menu_items mi
            JOIN menu_categories mc ON mi.category_id = mc.id
            WHERE mi.category_id = %s AND mi.is_available = TRUE
            ORDER BY mi.item_number
        """, (category_id,))
        rows = cur.fetchall()
        if rows:
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, row)) for row in rows]
            conn.close()
            
            # Calculate final price
            for item in items:
                item['final_price'] = item['price'] * (1 - (item['discount'] or 0)/100)
            return items
    conn.close()
    return []

def get_cart_count(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT SUM(quantity) FROM cart WHERE user_id = %s", (user_id,))
        result = cur.fetchone()[0]
        conn.close()
        return result or 0

# ================= ROUTES =================

@app.route("/")
def home():
    if "user_id" in session:
        # ✅ AUTO REDIRECT TO SERVICES PAGE AFTER LOGIN/REGISTRATION
        return redirect(url_for("services"))
    return redirect(url_for("login"))

# ---------- REGISTER (WITH AUTO USER ID) ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("services"))  # ✅ Redirect to services

    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if not name or not mobile or not password:
            flash("All fields required", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match", "error")
            return render_template("register.html")

        if get_user_by_mobile(mobile):
            flash("Mobile already registered", "error")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        user_id_code = generate_user_id(name)

        conn = get_db_connection()
        with conn.cursor() as cur:
            # Create user with auto-generated user_id
            cur.execute(
                "INSERT INTO users (name, mobile, password, user_id) VALUES (%s,%s,%s,%s) RETURNING id",
                (name, mobile, hashed, user_id_code)
            )
            user_db_id = cur.fetchone()[0]

            # 🔥 AUTO LOGO = USER ID
            default_logo = f"profile/user_{user_db_id}.png"
            cur.execute(
                "UPDATE users SET profile_photo=%s WHERE id=%s",
                (default_logo, user_db_id)
            )

            conn.commit()
        conn.close()

        session["user_id"] = user_db_id
        session["user_data"] = get_user_by_id(user_db_id)
        flash(f"Registration successful! Your User ID: {user_id_code}", "success")
        
        # ✅ AUTO REDIRECT TO SERVICES PAGE AFTER REGISTRATION
        return redirect(url_for("services"))

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("services"))  # ✅ Redirect to services

    if request.method == "POST":
        mobile = request.form.get("mobile")
        password = request.form.get("password")

        user = get_user_by_mobile(mobile)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_data"] = user
            session["session_id"] = str(uuid.uuid4())
            flash("Login successful!", "success")
            
            # ✅ AUTO REDIRECT TO SERVICES PAGE AFTER LOGIN
            return redirect(url_for("services"))

        flash("Invalid credentials", "error")

    return render_template("login.html")

# ---------- SERVICES PAGE (MAIN PAGE AFTER LOGIN) ----------
@app.route("/services")
def services():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    services_data = get_all_services()
    
    # Get cart count for navigation
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("services.html", 
                         user=user,
                         services=services_data,
                         current_page='services',
                         cart_count=cart_count)

# ---------- MENU PAGE ----------
@app.route("/menu")
def menu():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    categories = get_all_menu_categories()
    
    # Get items for each category
    items_by_category = {}
    for category in categories:
        items = get_menu_items_by_category(category['id'])
        if items:
            items_by_category[category['id']] = items
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("menu.html",
                         user=user,
                         categories=categories,
                         items_by_category=items_by_category,
                         current_page='menu',
                         cart_count=cart_count,
                         no_data=len(categories) == 0)

# ---------- SERVICE DETAIL PAGE ----------
@app.route("/service/<int:service_id>")
def service_detail(service_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Get service details
        cur.execute("SELECT * FROM services WHERE id = %s", (service_id,))
        row = cur.fetchone()
        if not row:
            flash("Service not found!", "error")
            return redirect(url_for("services"))
        
        cols = [d[0] for d in cur.description]
        service = dict(zip(cols, row))
        service['final_price'] = service['price'] * (1 - (service['discount'] or 0)/100)
        
        # Get service items
        cur.execute("""
            SELECT * FROM service_items 
            WHERE service_id = %s AND is_available = TRUE
            ORDER BY item_number
        """, (service_id,))
        rows = cur.fetchall()
        items = []
        if rows:
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, row)) for row in rows]
            for item in items:
                item['final_price'] = item['price'] * (1 - (item['discount'] or 0)/100)
    
    conn.close()
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("service_detail.html",
                         user=user,
                         service=service,
                         items=items,
                         current_page='services',
                         cart_count=cart_count)

# ---------- ADD TO CART ----------
@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login first!"})
    
    item_type = request.form.get("item_type")
    item_id = request.form.get("item_id")
    quantity = int(request.form.get("quantity", 1))
    
    if not item_type or not item_id:
        return jsonify({"success": False, "message": "Invalid item!"})
    
    user_id = session["user_id"]
    session_id = get_session_id()
    
    # Get item price and discount
    conn = get_db_connection()
    with conn.cursor() as cur:
        if item_type == 'service':
            cur.execute("SELECT name, price, discount FROM services WHERE id = %s", (item_id,))
        elif item_type == 'menu_item':
            cur.execute("SELECT name, price, discount FROM menu_items WHERE id = %s", (item_id,))
        else:
            conn.close()
            return jsonify({"success": False, "message": "Invalid item type!"})
        
        item_data = cur.fetchone()
        if not item_data:
            conn.close()
            return jsonify({"success": False, "message": "Item not found!"})
        
        item_name, price, discount = item_data
        
        # Check if item already in cart
        cur.execute("""
            SELECT id, quantity FROM cart 
            WHERE user_id = %s AND item_type = %s AND item_id = %s
        """, (user_id, item_type, item_id))
        
        existing = cur.fetchone()
        
        if existing:
            # Update quantity
            cur.execute("""
                UPDATE cart SET quantity = quantity + %s 
                WHERE id = %s
            """, (quantity, existing[0]))
        else:
            # Add new item
            cur.execute("""
                INSERT INTO cart (user_id, session_id, item_type, item_id, quantity, price_at_add, discount_at_add)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, session_id, item_type, item_id, quantity, price, discount))
        
        conn.commit()
    conn.close()
    
    return jsonify({
        "success": True, 
        "message": f"{item_name} added to cart!",
        "cart_count": get_cart_count(user_id)
    })

# ---------- CART PAGE ----------
@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Get cart items with details
        cur.execute("""
            SELECT 
                c.id as cart_id,
                c.item_type,
                c.item_id,
                c.quantity,
                c.price_at_add,
                c.discount_at_add,
                CASE 
                    WHEN c.item_type = 'service' THEN s.name
                    WHEN c.item_type = 'menu_item' THEN mi.name
                END as name,
                CASE 
                    WHEN c.item_type = 'service' THEN s.image_url
                    WHEN c.item_type = 'menu_item' THEN mi.image_url
                END as image_url,
                CASE 
                    WHEN c.item_type = 'service' THEN s.description
                    WHEN c.item_type = 'menu_item' THEN mi.description
                END as description
            FROM cart c
            LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
            LEFT JOIN menu_items mi ON c.item_type = 'menu_item' AND c.item_id = mi.id
            WHERE c.user_id = %s
            ORDER BY c.added_at DESC
        """, (session["user_id"],))
        
        rows = cur.fetchall()
        cart_items = []
        if rows:
            cols = [d[0] for d in cur.description]
            cart_items = [dict(zip(cols, row)) for row in rows]
            
            # Calculate prices
            for item in cart_items:
                item['final_price'] = item['price_at_add'] * (1 - (item['discount_at_add'] or 0)/100)
                item['total_price'] = item['final_price'] * item['quantity']
        
        # Calculate cart total
        cur.execute("""
            SELECT 
                SUM(price_at_add * quantity) as subtotal,
                SUM((price_at_add * discount_at_add / 100) * quantity) as discount,
                SUM(price_at_add * quantity * (1 - discount_at_add / 100)) as total
            FROM cart 
            WHERE user_id = %s
        """, (session["user_id"],))
        
        total_row = cur.fetchone()
        cart_total = {
            'subtotal': total_row[0] or 0,
            'discount': total_row[1] or 0,
            'total': total_row[2] or 0
        }
    
    conn.close()
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("cart.html",
                         user=user,
                         cart_items=cart_items,
                         cart_total=cart_total,
                         current_page='cart',
                         cart_count=cart_count)

# ---------- REMOVE FROM CART ----------
@app.route("/remove-from-cart/<int:cart_id>")
def remove_from_cart(cart_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cart WHERE id = %s AND user_id = %s", 
                   (cart_id, session["user_id"]))
        conn.commit()
    conn.close()
    
    flash("Item removed from cart!", "success")
    return redirect(url_for("cart"))

# ---------- ORDER PAGE ----------
@app.route("/order")
def order():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    
    # Check if cart has items
    cart_count = get_cart_count(session["user_id"])
    if cart_count == 0:
        flash("Your cart is empty!", "error")
        return redirect(url_for("cart"))
    
    # Calculate cart total
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                SUM(price_at_add * quantity * (1 - discount_at_add / 100)) as total
            FROM cart 
            WHERE user_id = %s
        """, (session["user_id"],))
        
        total = cur.fetchone()[0] or 0
    conn.close()
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("order.html",
                         user=user,
                         cart_total=total,
                         current_page='order',
                         cart_count=cart_count)

# ---------- PLACE ORDER ----------
@app.route("/place-order", methods=["POST"])
def place_order():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please login!"})
    
    user_id = session["user_id"]
    
    # Get delivery info
    delivery_address = request.form.get("delivery_address", "")
    delivery_city = request.form.get("delivery_city", "")
    delivery_state = request.form.get("delivery_state", "")
    delivery_pincode = request.form.get("delivery_pincode", "")
    delivery_instructions = request.form.get("delivery_instructions", "")
    payment_method = request.form.get("payment_method", "cod")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get cart items and calculate total
            cur.execute("""
                SELECT 
                    SUM(price_at_add * quantity) as subtotal,
                    SUM((price_at_add * discount_at_add / 100) * quantity) as discount,
                    SUM(price_at_add * quantity * (1 - discount_at_add / 100)) as total
                FROM cart 
                WHERE user_id = %s
            """, (user_id,))
            
            total_row = cur.fetchone()
            subtotal = total_row[0] or 0
            discount = total_row[1] or 0
            total = total_row[2] or 0
            
            # Generate order number
            order_number = f"ORD{random.randint(100000, 999999)}"
            
            # Create order
            cur.execute("""
                INSERT INTO orders (
                    order_number, user_id, total_amount, discount_amount, 
                    final_amount, payment_method, delivery_address, delivery_city,
                    delivery_state, delivery_pincode, delivery_instructions
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                order_number, user_id, subtotal, discount, total,
                payment_method, delivery_address, delivery_city,
                delivery_state, delivery_pincode, delivery_instructions
            ))
            
            order_id = cur.fetchone()[0]
            
            # Get cart items and add to order items
            cur.execute("""
                SELECT 
                    c.item_type,
                    c.item_id,
                    c.quantity,
                    c.price_at_add,
                    c.discount_at_add,
                    CASE 
                        WHEN c.item_type = 'service' THEN s.name
                        WHEN c.item_type = 'menu_item' THEN mi.name
                    END as item_name
                FROM cart c
                LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                LEFT JOIN menu_items mi ON c.item_type = 'menu_item' AND c.item_id = mi.id
                WHERE c.user_id = %s
            """, (user_id,))
            
            cart_items = cur.fetchall()
            cols = [d[0] for d in cur.description]
            
            for item in cart_items:
                item_dict = dict(zip(cols, item))
                unit_price = item_dict['price_at_add']
                discount_percent = item_dict['discount_at_add'] or 0
                final_price = unit_price * (1 - discount_percent/100)
                total_price = final_price * item_dict['quantity']
                
                cur.execute("""
                    INSERT INTO order_items (
                        order_id, item_type, item_id, item_name, 
                        quantity, unit_price, discount, total_price
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    order_id, item_dict['item_type'], item_dict['item_id'],
                    item_dict['item_name'], item_dict['quantity'],
                    unit_price, discount_percent, total_price
                ))
            
            # Clear cart
            cur.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "Order placed successfully!",
                "order_number": order_number,
                "order_id": order_id
            })
            
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"})
    finally:
        conn.close()

# ---------- ORDER HISTORY ----------
@app.route("/order-history")
def order_history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_id(session["user_id"])
    
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                o.id, o.order_number, o.total_amount, o.discount_amount,
                o.final_amount, o.status, o.payment_method, o.payment_status,
                o.order_date,
                COUNT(oi.id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.user_id = %s
            GROUP BY o.id
            ORDER BY o.order_date DESC
        """, (session["user_id"],))
        
        rows = cur.fetchall()
        orders = []
        if rows:
            cols = [d[0] for d in cur.description]
            orders = [dict(zip(cols, row)) for row in rows]
    
    conn.close()
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("order_history.html",
                         user=user,
                         orders=orders,
                         current_page='order_history',
                         cart_count=cart_count)

# ---------- PROFILE ----------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    # Process profile photo URL
    photo = user.get("profile_photo")
    if photo:
        user["profile_photo"] = url_for("static", filename=photo)
    else:
        user["profile_photo"] = url_for("static", filename="img/default-avatar.png")

    # Get recent orders for profile
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT order_number, final_amount, status, order_date
            FROM orders 
            WHERE user_id = %s 
            ORDER BY order_date DESC 
            LIMIT 3
        """, (session["user_id"],))
        
        rows = cur.fetchall()
        recent_orders = []
        if rows:
            cols = [d[0] for d in cur.description]
            recent_orders = [dict(zip(cols, row)) for row in rows]
    
    conn.close()
    
    cart_count = get_cart_count(session["user_id"])
    
    return render_template("profile.html", 
                         user=user, 
                         recent_orders=recent_orders,
                         current_page='profile',
                         cart_count=cart_count)

# ---------- EDIT PROFILE (CHANGE LOGO) ----------
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        email = request.form.get("email")
        address = request.form.get("address")
        city = request.form.get("city")
        state = request.form.get("state")
        pincode = request.form.get("pincode")
        
        profile_photo = user["profile_photo"]

        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file and allowed_file(file.filename):
                fname = secure_filename(file.filename)
                new_name = f"profile/user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
                path = os.path.join("static/uploads", new_name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                file.save(path)
                profile_photo = new_name

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET name=%s, mobile=%s, email=%s, address=%s, 
                    city=%s, state=%s, pincode=%s, profile_photo=%s
                WHERE id=%s
            """, (name, mobile, email, address, city, state, pincode, profile_photo, session["user_id"]))
            conn.commit()
        conn.close()

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user, current_page='profile')

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= STARTUP =================

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)