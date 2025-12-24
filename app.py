from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
import psycopg
import os
from dotenv import load_dotenv
import hashlib

# ---------------- LOAD ENV ----------------
load_dotenv()

app = Flask(__name__)

# ✅ REQUIRED FOR RENDER (FIX 400 BAD REQUEST)
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_port=1
)

# ---------------- SECRET KEY ----------------
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# ---------------- DATABASE ----------------
def get_db_connection():
    return psycopg.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )

def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    mobile VARCHAR(15) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    name VARCHAR(100),
                    email VARCHAR(100),
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

# ---------------- UTIL ----------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return redirect(url_for('profile')) if 'user_id' in session else redirect(url_for('login'))

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile_number')
        password = hash_password(request.form.get('password'))

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, mobile, name, email, address
                        FROM users
                        WHERE mobile = %s AND password = %s
                    """, (mobile, password))
                    user = cur.fetchone()

            if user:
                session['user_id'] = user[0]
                session['mobile'] = user[1]
                session['name'] = user[2]
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

        if request.form.get('password') != request.form.get('confirm_password'):
            flash("Passwords do not match", "error")
            return render_template('register.html')

        mobile = request.form.get('mobile_number')

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
                    """, (
                        request.form.get('name'),
                        mobile,
                        request.form.get('email'),
                        request.form.get('address'),
                        hash_password(request.form.get('password'))
                    ))

                    user_id = cur.fetchone()[0]
                conn.commit()

            session['user_id'] = user_id
            session['mobile'] = mobile
            session['name'] = request.form.get('name')
            session['email'] = request.form.get('email')
            session['address'] = request.form.get('address')

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
        return "Database connection successful!"
    except Exception as e:
        return f"Database error: {e}"

# ---------------- INIT ----------------
with app.app_context():
    create_tables()

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)