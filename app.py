from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg
import os
from werkzeug.utils import secure_filename

# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = "bite-me-buddy-secret-key"

DATABASE_URL = os.environ.get("DATABASE_URL")

UPLOAD_FOLDER = "static/uploads/profile"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- DB CONNECTION ----------------
def get_db():
    return psycopg.connect(DATABASE_URL)

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("profile"))
    return redirect(url_for("login"))

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        email = request.form.get("email")
        address = request.form.get("address")
        password = request.form.get("password")

        if not all([name, mobile, email, address, password]):
            flash("All fields required")
            return redirect(url_for("register"))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO users (name, mobile, email, address, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, mobile, email, address, password))

        conn.commit()
        conn.close()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mobile = request.form.get("mobile")
        password = request.form.get("password")

        if not mobile or not password:
            flash("Mobile and password required")
            return redirect(url_for("login"))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id FROM users
            WHERE mobile=%s AND password=%s
        """, (mobile, password))

        user = cur.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect(url_for("profile"))
        else:
            flash("Invalid mobile or password")
            return redirect(url_for("login"))

    return render_template("login.html")

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT name, mobile, email, address, photo
        FROM users WHERE id=%s
    """, (session["user_id"],))

    user = cur.fetchone()
    conn.close()

    return render_template("profile.html", user=user)

# ---------------- EDIT PROFILE ----------------
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name")
        address = request.form.get("address")

        photo_file = request.files.get("photo")
        photo_name = None

        if photo_file and photo_file.filename:
            photo_name = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config["UPLOAD_FOLDER"], photo_name))

        if photo_name:
            cur.execute("""
                UPDATE users
                SET name=%s, address=%s, photo=%s
                WHERE id=%s
            """, (name, address, photo_name, session["user_id"]))
        else:
            cur.execute("""
                UPDATE users
                SET name=%s, address=%s
                WHERE id=%s
            """, (name, address, session["user_id"]))

        conn.commit()
        conn.close()
        return redirect(url_for("profile"))

    cur.execute("""
        SELECT name, address FROM users WHERE id=%s
    """, (session["user_id"],))

    user = cur.fetchone()
    conn.close()

    return render_template("edit_profile.html", user=user)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)