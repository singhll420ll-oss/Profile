from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import psycopg
import os
from dotenv import load_dotenv
import hashlib

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)

# Database connection function
def get_db_connection():
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://bite_me_buddy_user:6Mb7axQ89EkOQTQnqw6shT5CaO2lFY1Z@dpg-d536f8khg0os738kuhm0-a/bite_me_buddy'
    )

    conn = psycopg.connect(DATABASE_URL, sslmode="require")
    return conn

# Create users table if not exists
def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    mobile_number VARCHAR(15) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    name VARCHAR(100),
                    email VARCHAR(100),
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()

# Hash password function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile_number = request.form['mobile_number']
        password = request.form['password']
        hashed_password = hash_password(password)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM users WHERE mobile_number = %s AND password = %s",
                        (mobile_number, hashed_password)
                    )
                    user = cur.fetchone()

            if user:
                session['user_id'] = user[0]
                session['mobile_number'] = user[1]
                session['name'] = user[3]
                session['email'] = user[4]
                session['address'] = user[5]
                flash('Login successful!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Invalid mobile number or password', 'error')

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        mobile_number = request.form['mobile_number']
        email = request.form['email']
        address = request.form['address']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        hashed_password = hash_password(password)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM users WHERE mobile_number = %s",
                        (mobile_number,)
                    )
                    if cur.fetchone():
                        flash('Mobile number already registered', 'error')
                        return render_template('register.html')

                    cur.execute("""
                        INSERT INTO users (name, mobile_number, email, address, password)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (name, mobile_number, email, address, hashed_password))

                    user_id = cur.fetchone()[0]
                    conn.commit()

            session['user_id'] = user_id
            session['mobile_number'] = mobile_number
            session['name'] = name
            session['email'] = email
            session['address'] = address

            flash('Registration successful!', 'success')
            return redirect(url_for('profile'))

        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')

    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, mobile_number, email, address FROM users WHERE id = %s",
                (session['user_id'],)
            )
            user_data = cur.fetchone()

    if user_data:
        session['name'], session['mobile_number'], session['email'], session['address'] = user_data

    return render_template('profile.html')

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users
                        SET name = %s, email = %s, address = %s
                        WHERE id = %s
                    """, (name, email, address, session['user_id']))
                conn.commit()

            session['name'] = name
            session['email'] = email
            session['address'] = address
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))

        except Exception as e:
            flash(f'Update failed: {str(e)}', 'error')

    return render_template('edit_profile.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/check-status')
def check_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.before_first_request
def initialize():
    create_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)