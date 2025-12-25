import os
import psycopg
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'static/uploads/profile'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database connection function
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Parse DATABASE_URL (Render uses postgresql:// but psycopg needs postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url)
        return conn
    except psycopg.Error as e:
        print(f"Database connection error: {e}")
        raise

# Initialize database tables
def init_db():
    try:
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
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to get user by mobile
def get_user_by_mobile(mobile):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE mobile = %s", (mobile,))
            user = cur.fetchone()
            if user:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, user))
        conn.close()
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

# Helper function to get user by ID
def get_user_by_id(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if user:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, user))
        conn.close()
        return None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not name or not mobile or not password:
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        if len(mobile) < 10:
            flash('Mobile number must be at least 10 digits', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        existing_user = get_user_by_mobile(mobile)
        if existing_user:
            flash('Mobile number already registered', 'error')
            return render_template('register.html')
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (name, mobile, password) 
                    VALUES (%s, %s, %s) RETURNING id
                """, (name, mobile, hashed_password))
                user_id = cur.fetchone()[0]
                conn.commit()
            
            conn.close()
            
            # Auto login after registration
            session['user_id'] = user_id
            flash('Registration successful!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        
        if not mobile or not password:
            flash('Mobile and password are required', 'error')
            return render_template('login.html')
        
        user = get_user_by_mobile(mobile)
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid mobile or password', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Set default photo if none exists
    if not user['profile_photo'] or not os.path.exists(user['profile_photo']):
        user['profile_photo'] = url_for('static', filename='img/default-avatar.png')
    else:
        user['profile_photo'] = url_for('static', filename=user['profile_photo'].replace('static/', ''))
    
    return render_template('profile.html', user=user)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        
        if not name or not mobile:
            flash('Name and mobile are required', 'error')
            return redirect(url_for('edit_profile'))
        
        # Check if mobile is being changed to another user's mobile
        if mobile != user['mobile']:
            existing_user = get_user_by_mobile(mobile)
            if existing_user:
                flash('Mobile number already registered by another user', 'error')
                return redirect(url_for('edit_profile'))
        
        # Handle file upload
        profile_photo = user['profile_photo']
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Secure the filename
                filename = secure_filename(file.filename)
                # Create unique filename
                unique_filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                
                try:
                    # Save new file
                    file.save(filepath)
                    
                    # Delete old photo if it exists and is not default
                    if user['profile_photo'] and os.path.exists(user['profile_photo']):
                        if 'default-avatar.png' not in user['profile_photo']:
                            os.remove(user['profile_photo'])
                    
                    profile_photo = filepath.replace('static/', '')
                except Exception as e:
                    print(f"Error saving file: {e}")
                    flash('Error uploading photo', 'error')
                    return redirect(url_for('edit_profile'))
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET name = %s, mobile = %s, profile_photo = %s 
                    WHERE id = %s
                """, (name, mobile, profile_photo, session['user_id']))
                conn.commit()
            conn.close()
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            print(f"Update error: {e}")
            flash('Error updating profile', 'error')
            return redirect(url_for('edit_profile'))
    
    return render_template('edit_profile.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/static/uploads/profile/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Error handlers
@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 2MB.', 'error')
    return redirect(request.referrer or url_for('edit_profile'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Initialize database on startup
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Failed to initialize database: {e}")

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')