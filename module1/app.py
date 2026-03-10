from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__) 
app.secret_key = os.environ.get('SECRET_KEY', 'module1-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB limit

DATABASE = 'module1.db'
CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Bills', 'Shopping', 'Health', 'Education', 'Other']
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'avatars')
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp'}


# ── Database helpers ───────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def is_valid_image(stream):
    """Validate file is a real image by checking magic bytes."""
    header = stream.read(512)
    stream.seek(0)
    if header[:3] == b'\xff\xd8\xff':               return True  # JPEG
    if header[:8] == b'\x89PNG\r\n\x1a\n':          return True  # PNG
    if header[:6] in (b'GIF87a', b'GIF89a'):        return True  # GIF
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP': return True  # WEBP
    return False


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            avatar        TEXT    NOT NULL DEFAULT '',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            title      TEXT    NOT NULL,
            amount     REAL    NOT NULL,
            date       TEXT    NOT NULL,
            category   TEXT    NOT NULL,
            notes      TEXT    NOT NULL DEFAULT '',
            tags       TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    ''')
    conn.close()


# ── Auth decorator ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if '@' not in email or '.' not in email:
            errors.append('A valid email address is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if not errors:
            try:
                conn = get_db()
                conn.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, hash_password(password))
                )
                conn.commit()
                conn.close()
                flash('Account created! You can now log in.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                conn.close()
                errors.append('That username or email is already taken.')

        for err in errors:
            flash(err, 'danger')

    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password_hash = ?',
            (username, hash_password(password))
        ).fetchone()
        conn.close()

        if user:
            session.clear()
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['avatar']   = user['avatar'] if user['avatar'] else ''
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Feature 1 (Sanzinan): Profile – view & update name, email ─────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']

    if request.method == 'POST':
        action           = request.form.get('action', 'update')
        username         = request.form.get('username', '').strip()
        email            = request.form.get('email', '').strip().lower()
        current_password = request.form.get('current_password', '')
        new_password     = request.form.get('new_password', '')

        # Remove avatar action
        if action == 'remove_avatar':
            conn = get_db()
            row = conn.execute('SELECT avatar FROM users WHERE id = ?', [user_id]).fetchone()
            if row and row['avatar']:
                old_path = os.path.join('static', row['avatar'].lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)
            conn.execute("UPDATE users SET avatar = '' WHERE id = ?", [user_id])
            conn.commit()
            conn.close()
            session['avatar'] = ''
            flash('Profile picture removed.', 'success')
            return redirect(url_for('profile'))

        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if '@' not in email or '.' not in email:
            errors.append('A valid email address is required.')

        conn = get_db()
        pwd_ok = conn.execute(
            'SELECT id FROM users WHERE id = ? AND password_hash = ?',
            [user_id, hash_password(current_password)]
        ).fetchone()
        conn.close()

        if not pwd_ok:
            errors.append('Current password is incorrect.')
        if new_password and len(new_password) < 6:
            errors.append('New password must be at least 6 characters.')

        # Avatar upload
        new_avatar_rel = None
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            if not allowed_file(avatar_file.filename):
                errors.append('Only JPG, PNG, GIF, and WEBP images are allowed.')
            elif not is_valid_image(avatar_file.stream):
                errors.append('The uploaded file does not appear to be a valid image.')
            else:
                ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                filename = f'user_{user_id}.{ext}'
                for old_ext in ALLOWED_EXT:
                    old_path = os.path.join(UPLOAD_FOLDER, f'user_{user_id}.{old_ext}')
                    if os.path.exists(old_path):
                        os.remove(old_path)
                avatar_file.save(os.path.join(UPLOAD_FOLDER, filename))
                new_avatar_rel = f'uploads/avatars/{filename}'

        if not errors:
            fields = 'username = ?, email = ?'
            params = [username, email]
            if new_password:
                fields += ', password_hash = ?'
                params.append(hash_password(new_password))
            if new_avatar_rel is not None:
                fields += ', avatar = ?'
                params.append(new_avatar_rel)
            params.append(user_id)
            try:
                conn = get_db()
                conn.execute(f'UPDATE users SET {fields} WHERE id = ?', params)
                conn.commit()
                conn.close()
                session['username'] = username
                if new_avatar_rel is not None:
                    session['avatar'] = new_avatar_rel
                flash('Profile updated successfully.', 'success')
                return redirect(url_for('profile'))
            except sqlite3.IntegrityError:
                conn.close()
                flash('That username or email is already taken.', 'danger')
        else:
            for err in errors:
                flash(err, 'danger')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', [user_id]).fetchone()
    conn.close()

    # Check if the avatar file actually exists on disk
    avatar_exists = False
    if user['avatar']:
        avatar_path = os.path.join('static', user['avatar'])
        if os.path.exists(avatar_path):
            avatar_exists = True
        else:
            # Stale DB entry – clear it silently so Remove Photo button hides
            conn = get_db()
            conn.execute("UPDATE users SET avatar = '' WHERE id = ?", [user_id])
            conn.commit()
            conn.close()
            session['avatar'] = ''

    if request.method == 'GET':
        session['avatar'] = user['avatar'] if avatar_exists else ''
    return render_template('profile.html', user=user, avatar_exists=avatar_exists)


# ── Feature 2 (Jannatunnesa): Add new expense ──────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, created_at DESC',
        [user_id]
    ).fetchall()
    conn.close()
    return render_template('expenses/dashboard.html', expenses=expenses, categories=CATEGORIES)


@app.route('/expense/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        amount   = request.form.get('amount', '').strip()
        date     = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()   # Feature 3 (Sadia)
        notes    = request.form.get('notes', '').strip()       # Feature 4 (Sanzinan)
        tags     = request.form.get('tags', '').strip()        # Feature 4 (Sanzinan)

        errors     = []
        amount_val = None
        if not title:
            errors.append('Title is required.')
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('A valid positive amount is required.')
        if not date:
            errors.append('Date is required.')
        else:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                errors.append('Invalid date format.')
        if category not in CATEGORIES:
            errors.append('Please select a valid category.')

        if not errors:
            conn = get_db()
            conn.execute(
                'INSERT INTO expenses (user_id, title, amount, date, category, notes, tags) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (session['user_id'], title, amount_val, date, category, notes, tags)
            )
            conn.commit()
            conn.close()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('dashboard'))

        for err in errors:
            flash(err, 'danger')

    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('expenses/add_expense.html', categories=CATEGORIES,
                           today=today, form=request.form)


# ── Feature 4 continued: Edit expense (notes & tags) ──────────────────────────

@app.route('/expense/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    conn    = get_db()
    expense = conn.execute(
        'SELECT * FROM expenses WHERE id = ? AND user_id = ?',
        [expense_id, session['user_id']]
    ).fetchone()
    conn.close()

    if not expense:
        flash('Expense not found.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        amount   = request.form.get('amount', '').strip()
        date     = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()
        notes    = request.form.get('notes', '').strip()
        tags     = request.form.get('tags', '').strip()

        errors     = []
        amount_val = None
        if not title:
            errors.append('Title is required.')
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('A valid positive amount is required.')
        if not date:
            errors.append('Date is required.')
        else:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                errors.append('Invalid date format.')
        if category not in CATEGORIES:
            errors.append('Please select a valid category.')

        if not errors:
            conn = get_db()
            conn.execute(
                "UPDATE expenses SET title=?, amount=?, date=?, category=?, notes=?, tags=?, "
                "updated_at=datetime('now') WHERE id=? AND user_id=?",
                (title, amount_val, date, category, notes, tags, expense_id, session['user_id'])
            )
            conn.commit()
            conn.close()
            flash('Expense updated successfully.', 'success')
            return redirect(url_for('dashboard'))

        for err in errors:
            flash(err, 'danger')

    return render_template('expenses/edit_expense.html', expense=expense, categories=CATEGORIES)


@app.route('/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    conn   = get_db()
    result = conn.execute(
        'DELETE FROM expenses WHERE id = ? AND user_id = ?',
        [expense_id, session['user_id']]
    )
    conn.commit()
    conn.close()
    if result.rowcount:
        flash('Expense deleted.', 'success')
    else:
        flash('Expense not found.', 'danger')
    return redirect(url_for('dashboard'))


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
