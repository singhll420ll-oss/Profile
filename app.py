from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
import psycopg
import os
from dotenv import load_dotenv
import hashlib

# ---------------- LOAD ENV ----------------
load_dotenv()

app = Flask(__name__)

# ---------------- RENDER PROXY FIX ----------------
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1
)

# ---------------- SECRET KEY ----------------
app.secret_key = os.getenv("SECRET_KEY", "DEV_SECRET_CHANGE_ME")

# ---------------- DATABASE ----------------
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")
    return psycopg.connect(db_url, sslmode="require")

def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    mobile VARCHAR(15) UNIQUE NOT NULL,
                    email VARCHAR(100),
                    address TEXT,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

# ---------------- UTIL ----------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- HOME ----------------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

# ---------------- INIT DB ----------------
@app.route('/init-db')
def init_db():
    create_tables()
    return "✅ Database initialized successfully"

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile_number')
        password = request.form.get('password')

        if not mobile or not password:
            flash("Mobile and password required", "error")
            return render_template('login.html')

        password = hash_password(password)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, mobile, email, address
                        FROM users
                        WHERE mobile = %s AND password = %s
                    """, (mobile, password))
                    user = cur.fetchone()

            if user:
                session['user_id'] = user[0]
                session['name'] = user[1]
                session['mobile'] = user[2]
                session['email'] = user[3]
                session['address'] = user[4]

                flash("Login successful", "success")
                return redirect(url_for('profile'))

            flash("Invalid mobile or password", "error")

        except Exception as e:
            flash(str(e), "error")

    return render_template('login.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        name = request.form.get('name')
        mobile = request.form.get('mobile_number')
        email = request.form.get('email')
        address = request.form.get('address')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not mobile:
            flash("Mobile number is required", "error")
            return render_template('register.html')

        if password != confirm:
            flash("Passwords do not match", "error")
            return render_template('register.html')

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:

                    cur.execute("SELECT id FROM users WHERE mobile = %s", (mobile,))
                    if cur.fetchone():
                        flash("Mobile already registered", "error")
                        return render_template('register.html')

                    cur.execute("""
                        INSERT INTO users (name, mobile, email, address, password)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (name, mobile, email, address, hash_password(password)))

                    user_id = cur.fetchone()[0]
                conn.commit()

            session['user_id'] = user_id
            session['name'] = name
            session['mobile'] = mobile
            session['email'] = email
            session['address'] = address

            flash("Registration successful", "success")
            return redirect(url_for('profile'))

        except Exception as e:
            flash(str(e), "error")

    return render_template('register.html')

# ---------------- PROFILE ----------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

# ---------------- HEALTH CHECK ----------------
@app.route('/check-status')
def check_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return "✅ Database connection OK"
    except Exception as e:
        return f"❌ Database error: {e}"

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)