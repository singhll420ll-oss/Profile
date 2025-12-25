import os
import psycopg
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                mobile VARCHAR(15) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                profile_photo VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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

# ================= ROUTES =================

@app.route("/")
def home():
    return redirect(url_for("profile")) if "user_id" in session else redirect(url_for("login"))

# ---------- REGISTER (AUTO LOGO SET) ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("profile"))

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

        conn = get_db_connection()
        with conn.cursor() as cur:
            # Create user
            cur.execute(
                "INSERT INTO users (name, mobile, password) VALUES (%s,%s,%s) RETURNING id",
                (name, mobile, hashed)
            )
            user_id = cur.fetchone()[0]

            # 🔥 AUTO LOGO = USER ID
            default_logo = f"profile/user_{user_id}.png"
            cur.execute(
                "UPDATE users SET profile_photo=%s WHERE id=%s",
                (default_logo, user_id)
            )

            conn.commit()
        conn.close()

        session["user_id"] = user_id
        return redirect(url_for("profile"))

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("profile"))

    if request.method == "POST":
        mobile = request.form.get("mobile")
        password = request.form.get("password")

        user = get_user_by_mobile(mobile)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))

        flash("Invalid credentials", "error")

    return render_template("login.html")

# ---------- PROFILE ----------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    photo = user.get("profile_photo")
    if photo:
        user["profile_photo"] = url_for("static", filename=photo)
    else:
        user["profile_photo"] = url_for("static", filename="img/default-avatar.png")

    return render_template("profile.html", user=user)

# ---------- EDIT PROFILE (CHANGE LOGO) ----------
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
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
                SET name=%s, mobile=%s, profile_photo=%s
                WHERE id=%s
            """, (name, mobile, profile_photo, session["user_id"]))
            conn.commit()
        conn.close()

        flash("Profile updated", "success")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user)

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= STARTUP =================

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=False)