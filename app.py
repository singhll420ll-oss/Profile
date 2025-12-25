from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import psycopg
import os
from dotenv import load_dotenv
import hashlib
import uuid

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

# ---------------- UPLOAD CONFIG ----------------
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
                    photo VARCHAR(255),
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
    return redirect(url_for('profile')) if 'user_id' in session else redirect(url_for('login'))

# ---------------- INIT DB ----------------
@app.route('/init-db')
def init_db():
    create_tables()
    return "✅ Database initialized"

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        if not mobile or not password:
            flash("Mobile and password required", "error")
            return render_template('login.html')

        password = hash_password(password)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, mobile, email, address, photo
                    FROM users
                    WHERE mobile=%s AND password=%s
                """, (mobile, password))
                user = cur.fetchone()

        if not user:
            flash("Invalid mobile or password", "error")
            return render_template('login.html')

        session.update({
            "user_id": user[0],
            "name": user[1],
            "mobile": user[2],
            "email": user[3],
            "address": user[4],
            "photo": user[5]
        })

        return redirect(url_for('profile'))

    return render_template('login.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        address = request.form.get('address')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            flash("Passwords do not match", "error")
            return render_template('register.html')

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
                if cur.fetchone():
                    flash("Mobile already registered", "error")
                    return render_template('register.html')

                cur.execute("""
                    INSERT INTO users (name, mobile, email, address, password)
                    VALUES (%s,%s,%s,%s,%s)
                    RETURNING id
                """, (name, mobile, email, address, hash_password(password)))

                user_id = cur.fetchone()[0]
            conn.commit()

        session.update({
            "user_id": user_id,
            "name": name,
            "mobile": mobile,
            "email": email,
            "address": address,
            "photo": None
        })

        return redirect(url_for('profile'))

    return render_template('register.html')

# ---------------- PROFILE ----------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

# ---------------- EDIT PROFILE ----------------
@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        address = request.form.get('address')
        photo = request.files.get('photo')

        filename = session.get("photo")

        if photo and allowed_file(photo.filename):
            ext = photo.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users
                    SET name=%s, email=%s, address=%s, photo=%s
                    WHERE id=%s
                """, (name, email, address, filename, session["user_id"]))
            conn.commit()

        session.update({
            "name": name,
            "email": email,
            "address": address,
            "photo": filename
        })

        flash("Profile updated successfully", "success")
        return redirect(url_for('profile'))

    return render_template('edit_profile.html')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- HEALTH CHECK ----------------
@app.route('/check-status')
def check_status():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return "✅ DB OK"
    except Exception as e:
        return f"❌ DB ERROR: {e}"

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)