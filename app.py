from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import psycopg
import os
from dotenv import load_dotenv
import hashlib

# ---------------- LOAD ENV ----------------
load_dotenv()

app = Flask(__name__)

# ---------------- SESSION CONFIG ----------------
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)

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
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form['mobile']
        password = hash_password(request.form['password'])

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, mobile, name, email, address FROM users WHERE mobile=%s AND password=%s",
                        (mobile, password)
                    )
                    user = cur.fetchone()

            if user:
                session['user_id'] = user[0]
                session['mobile'] = user[1]
                session['name'] = user[2]
                session['email'] = user[3]
                session['address'] = user[4]

                flash("Login successful", "success")
                return redirect(url_for('profile'))
            else:
                flash("Invalid mobile or password", "error")

        except Exception as e:
            flash(str(e), "error")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        if request.form['password'] != request.form['confirm_password']:
            flash("Passwords do not match", "error")
            return render_template('register.html')

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM users WHERE mobile=%s",
                        (request.form['mobile'],)
                    )
                    if cur.fetchone():
                        flash("Mobile already registered", "error")
                        return render_template('register.html')

                    cur.execute("""
                        INSERT INTO users (name, mobile, email, address, password)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        request.form['name'],
                        request.form['mobile'],
                        request.form['email'],
                        request.form['address'],
                        hash_password(request.form['password'])
                    ))

                    user_id = cur.fetchone()[0]
                    conn.commit()

            session['user_id'] = user_id
            session['mobile'] = request.form['mobile']
            session['name'] = request.form['name']
            session['email'] = request.form['email']
            session['address'] = request.form['address']

            flash("Registration successful", "success")
            return redirect(url_for('profile'))

        except Exception as e:
            flash(str(e), "error")

    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users
                        SET name=%s, email=%s, address=%s
                        WHERE id=%s
                    """, (
                        request.form['name'],
                        request.form['email'],
                        request.form['address'],
                        session['user_id']
                    ))
                conn.commit()

            session['name'] = request.form['name']
            session['email'] = request.form['email']
            session['address'] = request.form['address']

            flash("Profile updated", "success")
            return redirect(url_for('profile'))

        except Exception as e:
            flash(str(e), "error")

    return render_template('edit_profile.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

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