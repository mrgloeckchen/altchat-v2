import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for, g
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), 'database', 'altchat.sqlite3')
ADMIN_CODE = os.environ.get('ALTCHAT_ADMIN_CODE', 'admin123')
ALTCHAT_VERSION = 'v2.0.0'

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
        'color TEXT NOT NULL DEFAULT "#00ff00",'
        'status TEXT NOT NULL DEFAULT "available"'
        ')' )
    db.execute(
        'CREATE TABLE IF NOT EXISTS friend ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'user_id INTEGER NOT NULL,'
        'friend_id INTEGER NOT NULL,'
        'status TEXT NOT NULL DEFAULT "pending"'
        ')')
    db.execute(
        'CREATE TABLE IF NOT EXISTS message ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'sender_id INTEGER NOT NULL,'
        'receiver_id INTEGER NOT NULL,'
        'text TEXT NOT NULL,'
        'created TIMESTAMP NOT NULL,'
        'read INTEGER NOT NULL DEFAULT 0'
        ')')
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
            return render_template('register.html', error='Invalid admin code', version=ALTCHAT_VERSION)
        db = get_db()
        try:
            db.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username taken', version=ALTCHAT_VERSION)
        return redirect(url_for('login'))
    return render_template('register.html', version=ALTCHAT_VERSION)

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
        return render_template('login.html', error='Invalid credentials', version=ALTCHAT_VERSION)
    return render_template('login.html', version=ALTCHAT_VERSION)

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
    return render_template('chat.html', username=session['username'], color=session['color'], version=ALTCHAT_VERSION)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        color = request.form.get('color', '#00ff00')
        if color.lower() in ('#ff0000', 'hotpink'):
            user = db.execute('SELECT color, status FROM user WHERE id = ?', (session['user_id'],)).fetchone()
            return render_template('profile.html', username=session['username'], color=user['color'], status=user['status'], error='Color not allowed', version=ALTCHAT_VERSION)
        status = request.form.get('status', 'available')
        db.execute('UPDATE user SET color = ?, status = ? WHERE id = ?', (color, status, session['user_id']))
        db.commit()
        session['color'] = color
    user = db.execute('SELECT color, status FROM user WHERE id = ?', (session['user_id'],)).fetchone()
    return render_template('profile.html', username=session['username'], color=user['color'], status=user['status'], version=ALTCHAT_VERSION)

@app.route('/dm/<username>')
def direct_message(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    other = db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone()
    if not other:
        return redirect(url_for('chat'))
    return render_template('dm.html', other=username, version=ALTCHAT_VERSION)

@app.route('/admin')
def admin():
    if session.get('role') != 'Admin':
        return redirect(url_for('chat'))
    db = get_db()
    users = db.execute('SELECT id, username, role FROM user').fetchall()
    return render_template('admin.html', users=users, version=ALTCHAT_VERSION)

@app.route('/add_friend/<username>')
def add_friend(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    other = db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone()
    if other:
        db.execute('INSERT INTO friend (user_id, friend_id, status) VALUES (?,?,?)',
                   (session['user_id'], other['id'], 'pending'))
        db.commit()
    return redirect(url_for('chat'))

# ----- Socket.IO -----

online_users = set()
user_sid = {}

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        username = session['username']
        online_users.add(username)
        user_sid[username] = request.sid
        emit('user_list', list(online_users), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        username = session['username']
        online_users.discard(username)
        user_sid.pop(username, None)
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

@socketio.on('direct_message')
def handle_dm(data):
    text = data.get('text', '')
    receiver = data.get('to')
    db = get_db()
    user = db.execute('SELECT id FROM user WHERE username = ?', (receiver,)).fetchone()
    if not user:
        return
    sender_id = session.get('user_id')
    db.execute('INSERT INTO message (sender_id, receiver_id, text, created) VALUES (?,?,?,?)',
               (sender_id, user['id'], text, datetime.utcnow()))
    db.commit()
    emit('direct_message', {
        'from': session.get('username'),
        'to': receiver,
        'text': text
    }, room=request.sid)
    # send to receiver if online
    sid = user_sid.get(receiver)
    if sid:
        emit('direct_message', {
            'from': session.get('username'),
            'to': receiver,
            'text': text
        }, room=sid)

# ----- Main -----

if __name__ == '__main__':
    with app.app_context():
        init_db()
    socketio.run(app, host='0.0.0.0', port=5000)
