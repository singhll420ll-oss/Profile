import os
import uuid
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
                UNIQUE(category_id, item_number