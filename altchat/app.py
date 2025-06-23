import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, g
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), 'database', 'altchat.sqlite3')
ADMIN_CODE = os.environ.get('ALTCHAT_ADMIN_CODE', 'admin123')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('ALTCHAT_SECRET', 'changeme')

socketio = SocketIO(app)

# ----- Database utilities -----

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute(
        'CREATE TABLE IF NOT EXISTS user ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'username TEXT UNIQUE NOT NULL,'
        'password TEXT NOT NULL,'
        'role TEXT NOT NULL DEFAULT "User",'
        'color TEXT NOT NULL DEFAULT "#00ff00"'
        ')' )
    db.commit()

# ----- Helper -----

def convert_alt(text: str) -> str:
    """Very naive alt language conversion."""
    return text.replace('s', 'z').replace('S', 'Z')

# ----- Auth -----

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        code = request.form.get('code', '')
        if code != ADMIN_CODE:
            return render_template('register.html', error='Invalid admin code')
        db = get_db()
        try:
            db.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username taken')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['color'] = user['color']
            session['role'] = user['role']
            return redirect(url_for('chat'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ----- Routes -----

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'], color=session['color'])

# ----- Socket.IO -----

online_users = set()

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users.add(session['username'])
        emit('user_list', list(online_users), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        online_users.discard(session['username'])
        emit('user_list', list(online_users), broadcast=True)

@socketio.on('chat_message')
def handle_chat(data):
    text = data.get('text', '')
    alt = data.get('alt', False)
    if alt:
        text = convert_alt(text)
    emit('chat_message', {
        'user': session.get('username', 'anon'),
        'color': session.get('color', '#00ff00'),
        'text': text
    }, broadcast=True)

# ----- Main -----

if __name__ == '__main__':
    with app.app_context():
        init_db()
    socketio.run(app, host='0.0.0.0', port=5000)
