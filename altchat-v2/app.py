import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify, make_response
import sqlite3
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from werkzeug.utils import secure_filename
import requests
import logging
from datetime import datetime, timedelta
from database import (
    init_db, add_user, verify_user, user_exists, delete_user,
    get_phone_by_username, get_all_usernames, get_all_users_with_roles,
    get_all_user_phones, get_role, ban_user, temp_ban_user, unban_user,
    reset_user_password, rename_user, set_user_color, toggle_mod_status,
    promote_to_admin, log_admin_action, get_user_history,
    set_user_color, get_user_color_from_db, set_user_role,
    update_user_status, get_user_status, set_user_dnd, get_user_dnd, init_altchat_tables,
    is_user_banned,
)
from random import choice

app = Flask(__name__)
init_altchat_tables()
app.secret_key = os.urandom(24)
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    max_http_buffer_size=1000000,
    transports=["websocket", "polling"]  # ✅ wichtig!
)

logging.basicConfig(level=logging.DEBUG)


ADMIN_PASSWORD = "80024042"
online_users = set()
last_seen = {}
USER_COLORS = {}
user_sids = {}
COLOR_PALETTE = ["#00ff00", "#66ff66", "#00cc00", "#33ff33", "#FF69B4", "#3333FF", "#FF69B4", "#FF0000"]
chat_history = {"main": []}
MAX_PN_MESSAGES = 50

def get_user_color(username):
    if username not in USER_COLORS:
        USER_COLORS[username] = choice(COLOR_PALETTE)
    return USER_COLORS[username]

def save_main_message(username, message, timestamp):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS main_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    c.execute("INSERT INTO main_messages (username, message, timestamp) VALUES (?, ?, ?)", (username, message, timestamp))
    conn.commit()
    conn.close()

def save_private_message(room, username, message):
    timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS private_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT, username TEXT, message TEXT, timestamp TEXT)")
    c.execute("INSERT INTO private_messages (room, username, message, timestamp) VALUES (?, ?, ?, ?)", (room, username, message, timestamp))
    conn.commit()
    conn.close()

def load_main_messages(limit=20):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("SELECT username, message, timestamp FROM main_messages ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows[::-1]

def load_private_messages(room, limit=50):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("SELECT username, message, timestamp FROM private_messages WHERE room = ? ORDER BY id DESC LIMIT ?", (room, limit))
    rows = c.fetchall()
    conn.close()
    return rows[::-1]

def to_alt_language(text):
    mapping = {
        'a': 'å', 'b': '∫', 'c': 'ç', 'd': '∂', 'e': '€', 'f': 'ƒ', 'g': '©', 'h': 'ª',
        'i': '⁄', 'j': 'º', 'k': '∆', 'l': '@', 'm': 'µ', 'n': '~', 'o': 'ø', 'p': 'π',
        'q': '«', 'r': '®', 's': '‚', 't': '†', 'u': '¨', 'v': '√', 'w': '∑', 'x': '≈',
        'y': '¥', 'z': 'Ω', 'ä': 'æ', 'ö': 'œ', 'ü': '•', '1': '¡', '2': '“', '3': '¶',
        '4': '¢', '5': '[', '6': ']', '/': '7', '8': '{', '9': '}', '0': '≠', '?': '¿',
        ':': '…', ';': '∞'
    }
    return ''.join(mapping.get(char.lower(), char) for char in text)

@app.context_processor
def override_url_for():
    def dated_url_for(endpoint, **values):
        if endpoint == 'static':
            filename = values.get('filename', None)
            if filename:
                file_path = os.path.join(app.root_path, 'static', filename)
                if os.path.exists(file_path):
                    values['q'] = int(os.stat(file_path).st_mtime)
        return url_for(endpoint, **values)
    return dict(url_for=dated_url_for)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        admin_pass = request.form.get('admin_pass')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if admin_pass != ADMIN_PASSWORD:
            flash('Admin-Passwort falsch!')
            return redirect(url_for('register'))
        if user_exists(username):
            flash('User existiert schon!')
            return redirect(url_for('register'))
        if add_user(username, password, phone):
            flash('User erfolgreich registriert!')
            return redirect(url_for('login'))
        else:
            flash('Fehler beim Anlegen des Users.')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if verify_user(username, password):
            if is_user_banned(username):
                flash('User ist gebannt!')
                return redirect(url_for('login'))
            session['username'] = username
            update_user_status(username, "online")
            return redirect(url_for('mychats'))
        else:
            flash('Login fehlgeschlagen!')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/mychats")
def mychats():
    if "username" not in session:
        return redirect(url_for("login"))
    
    username = session["username"]
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()

    c.execute('''
        SELECT user2 FROM friends WHERE user1=? AND status='accepted'
        UNION
        SELECT user1 FROM friends WHERE user2=? AND status='accepted'
    ''', (username, username))

    rows = c.fetchall()
    friends = []

    for row in rows:
        friend_username = row[0]
        c.execute("SELECT profile_pic FROM profiles WHERE username=?", (friend_username,))
        profile = c.fetchone()
        profile_pic = profile[0] if profile else "/static/profile_pics/default.png"
        friends.append({"username": friend_username, "profile_pic": profile_pic})

    conn.close()
    return render_template("mychats.html", friends=friends)

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username:
        update_user_status(username, "offline")
        if not get_user_dnd(username):  
            set_user_dnd(username, False)
        online_users.discard(username)
        socketio.emit('message', {
            'username': 'System',
            'message': f'{username} hat den Chat verlassen.',
            'color': '#999999',
            'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        }, room='main_room')
    return render_template('logout.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    update_user_status(username, "online")

    target = request.args.get("user")

    if not target or target == "main":
        raw_messages = load_main_messages()
        messages = []
        for uname, message, timestamp in raw_messages:
            messages.append({
                "timestamp": timestamp,
                "username": uname,
                "message": message,
                "color": get_user_color_from_db(uname)
            })

        return render_template('chat.html',
            username=username,
            messages=messages,
            role=get_role(username),
            all_users=get_all_usernames(),
            get_user_color=get_user_color_from_db,
            status=get_user_status(username),
            room="main_room"
        )

    if target == username:
        return redirect(url_for('mychats'))

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("""
        SELECT * FROM friends 
        WHERE ((user1=? AND user2=?) OR (user1=? AND user2=?)) AND status='accepted'
    """, (username, target, target, username))
    if not c.fetchone():
        conn.close()
        return redirect(url_for("mychats"))
    
    conn.close()

    room = "pm_" + "_".join(sorted([username, target]))
    
    if room not in chat_history:
        chat_history[room] = []

    messages = []
    raw = load_private_messages(room)
    for uname, message, timestamp in raw:
        messages.append({
            "timestamp": timestamp,
            "username": uname,
            "message": message,
            "color": get_user_color_from_db(uname)
        })

    if not target or target == "main":
        room = "main"
    else:
        room = "pm_" + "_".join(sorted([username, target]))

    return render_template('chat.html',
        username=username,
        messages=messages,
        role=get_role(username),
        all_users=get_all_usernames(),
        get_user_color=get_user_color_from_db,
        status=get_user_status(username),
        room=room  # ✅ wird korrekt gesetzt!
    )

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon'
    )

@app.route('/admin')
def admin_panel():
    if 'username' not in session:
        return redirect(url_for('login'))
    role = get_role(session['username'])
    if role not in ['admin', 'mod']:
        return redirect(url_for('chat'))
    return render_template('admin.html',
        username=session['username'],
        role=role,
        users=get_all_users_with_roles()
    )

@app.route('/admin/set-color', methods=['POST'])
def admin_set_color():
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403

    current_user = session['username']
    role = get_role(current_user)

    if role not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403

    data = request.get_json()
    target = data.get('username')
    color = data.get('color')

    if not target or not color:
        return jsonify({'status': 'invalid'}), 400

    set_user_color(target, color)
    log_admin_action(current_user, f"set color of {target} to {color}", target)
    return jsonify({'status': 'success'})

@app.route('/user_history/<username>')
def user_history(username):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    requester = session['username']
    if get_role(requester) not in ['admin', 'mod']:
        return jsonify({'error': 'Forbidden'}), 403
    history = get_user_history(username)
    return jsonify({'history': history})

@app.route('/temp_ban/<username>', methods=['POST'])
def route_temp_ban(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    temp_ban_user(username, 86400)
    log_admin_action(session['username'], 'temp ban', username)
    return jsonify({'status': 'success'})

@app.route('/unban/<username>', methods=['POST'])
def route_unban(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    unban_user(username)
    log_admin_action(session['username'], 'unban', username)
    return jsonify({'status': 'success'})

@app.route('/perm_ban/<username>', methods=['POST'])
def route_perm_ban(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    ban_user(username)
    log_admin_action(session['username'], 'perm ban', username)
    return jsonify({'status': 'success'})

@app.route('/kick/<username>', methods=['POST'])
def route_kick(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    online_users.discard(username)
    update_user_status(username, 'offline')
    sid = user_sids.pop(username, None)
    socketio.emit('user_update', list(online_users), broadcast=True)
    if sid:
        socketio.emit('force_logout', to=sid)
    log_admin_action(session['username'], 'kick', username)
    return jsonify({'status': 'success'})

@app.route('/reset_password/<username>', methods=['POST'])
def route_reset_password(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    new_pw = request.get_json().get('password')
    if not new_pw:
        return jsonify({'status': 'invalid'}), 400
    reset_user_password(username, new_pw)
    log_admin_action(session['username'], 'reset password', username)
    return jsonify({'status': 'success'})

@app.route('/rename_user/<username>', methods=['POST'])
def route_rename_user(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    new_name = request.get_json().get('new_username')
    if not new_name:
        return jsonify({'status': 'invalid'}), 400
    rename_user(username, new_name)
    log_admin_action(session['username'], f'rename to {new_name}', username)
    return jsonify({'status': 'success'})

@app.route('/set_color/<username>', methods=['POST'])
def route_set_color(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) not in ['admin', 'mod']:
        return jsonify({'status': 'forbidden'}), 403
    color = request.get_json().get('color')
    if not color:
        return jsonify({'status': 'invalid'}), 400
    set_user_color(username, color)
    log_admin_action(session['username'], f'set color to {color}', username)
    return jsonify({'status': 'success'})

@app.route('/promote_mod/<username>', methods=['POST'])
def route_promote_mod(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) != 'admin':
        return jsonify({'status': 'forbidden'}), 403
    toggle_mod_status(username)
    log_admin_action(session['username'], 'toggle mod', username)
    return jsonify({'status': 'success'})

@app.route('/promote_admin/<username>', methods=['POST'])
def route_promote_admin(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) != 'admin':
        return jsonify({'status': 'forbidden'}), 403
    promote_to_admin(username)
    log_admin_action(session['username'], 'promote admin', username)
    return jsonify({'status': 'success'})

@app.route('/set_role_user/<username>', methods=['POST'])
def route_set_role_user(username):
    if 'username' not in session:
        return jsonify({'status': 'unauthorized'}), 403
    if get_role(session['username']) != 'admin':
        return jsonify({'status': 'forbidden'}), 403
    set_user_role(username, 'user')
    log_admin_action(session['username'], 'set role user', username)
    return jsonify({'status': 'success'})

@app.route('/set_status/<status>')
def set_status(status):
    if 'username' in session:
        username = session['username']
        if status == "online":
            update_user_status(username, "online")
            set_user_dnd(username, False)
        elif status == "dnd":
            update_user_status(username, "dnd")
            set_user_dnd(username, True)
        elif status == "offline":
            update_user_status(username, "offline")
            set_user_dnd(username, False)
        return '', 204
    return redirect(url_for('login'))

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    return "<h1 style='color:#00ff00; background:black; font-family:monospace;'>⚙️ Einstellungen kommen bald!</h1>"

@app.route("/profile/<username>")
def profile(username):
    if "username" not in session:
        return redirect(url_for("login"))

    viewer = session["username"]
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT bio, profile_pic FROM profiles WHERE username=?", (username,))
    row = c.fetchone()
    if not row:
        profile = {"username": username, "bio": "", "profile_pic": "/static/profile_pics/default.png"}
    else:
        profile = {"username": username, "bio": row[0], "profile_pic": row[1]}

    if viewer == username:
        friend_status = "self"
    else:
        c.execute("SELECT status FROM friends WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
                  (viewer, username, username, viewer))
        row = c.fetchone()
        if not row:
            friend_status = "none"
        elif row[0] == "pending":
            friend_status = "pending" if viewer < username else "received"
        elif row[0] == "accepted":
            friend_status = "accepted"

    conn.close()
    return render_template("profile.html", profile=profile,
                           is_own_profile=(viewer == username),
                           friend_status=friend_status)

@app.route("/update_bio", methods=["POST"])
def update_bio():
    if "username" not in session:
        return redirect(url_for("login"))

    bio = request.form["bio"]
    username = session["username"]

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("UPDATE profiles SET bio=? WHERE username=?", (bio, username))
    conn.commit()
    conn.close()
    return redirect(url_for("profile", username=username))


@app.route("/send_friend_request", methods=["POST"])
def send_friend_request():
    if "username" not in session:
        return redirect(url_for("login"))

    from_user = session["username"]
    to_user = request.form.get("to_user", "").strip()
    if not to_user:
        flash("Kein Empfänger ausgewählt.")
        return redirect(url_for("profile", username=from_user))


    if from_user == to_user:
        flash("Du kannst dir selbst keine Freundschaftsanfrage senden.")
        return redirect(url_for("profile", username=to_user))

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT * FROM friends WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
              (from_user, to_user, to_user, from_user))
    if c.fetchone():
        flash("Ihr seid bereits befreundet oder eine Anfrage besteht schon.")
        conn.close()
        return redirect(url_for("profile", username=to_user))

    c.execute("INSERT INTO friends (user1, user2, status) VALUES (?, ?, 'pending')", (from_user, to_user))
    conn.commit()
    conn.close()

    if not get_user_dnd(to_user):
        phone = get_phone_by_username(to_user)
        if phone:
            try:
                requests.post("http://localhost:3000/send", json={
                    "number": phone,
                    "message": f"{from_user} würde gerne mit dir befreundet sein"
                })
            except Exception as e:
                print(f"Fehler beim WhatsApp-Versand an {to_user}: {e}")

    flash("Freundschaftsanfrage gesendet.")
    return redirect(url_for("profile", username=to_user))


@app.route("/accept_friend_request", methods=["POST"])
def accept_friend_request():
    if "username" not in session:
        return redirect(url_for("login"))

    to_user = session["username"]
    from_user = request.form["from_user"]

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute("UPDATE friends SET status='accepted' WHERE user1=? AND user2=?",
              (from_user, to_user))
    conn.commit()
    conn.close()
    return redirect(url_for("profile", username=from_user))

@app.route("/upload_profile_pic", methods=["POST"])
def upload_profile_pic():
    if "username" not in session:
        return redirect(url_for("login"))

    file = request.files["profile_pic"]
    if file:
        filename = secure_filename(session["username"] + ".png")
        path = os.path.join("static", "profile_pics", filename)
        file.save(path)

        conn = sqlite3.connect("chat.db")
        c = conn.cursor()

        c.execute("SELECT * FROM profiles WHERE username=?", (session["username"],))
        if not c.fetchone():
            c.execute("INSERT INTO profiles (username, bio, profile_pic) VALUES (?, '', '')", (session["username"],))

        c.execute("UPDATE profiles SET profile_pic=? WHERE username=?",
                  ("/static/profile_pics/" + filename, session["username"]))
        conn.commit()
        conn.close()

    return redirect(url_for("profile", username=session["username"]))

@app.route("/friend_requests", methods=["GET"])
def friend_requests():
    if "username" not in session:
        return redirect(url_for("login"))

    me = session["username"]
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT user1 FROM friends WHERE user2=? AND status='pending'", (me,))
    requests_list = [row[0] for row in c.fetchall()]
    conn.close()

    from database import get_all_usernames
    query = request.args.get("search", "").strip()
    results = []
    if query:
        all_users = get_all_usernames()
        results = [u for u in all_users if query.lower() in u.lower() and u != me]

    return render_template("friend_requests.html", requests=requests_list, results=results)

@socketio.on('join')
def handle_join(data):
    username = session.get('username')
    room = data.get('room')

    if not username or username != data.get('username') or not room:
        return

    join_room(room)
    user_sids[username] = request.sid
    print(f"[SOCKET] {username} joined room: {room}")

    if username not in online_users:
        online_users.add(username)
        emit('user_update', list(online_users), broadcast=True)
    else:
        emit('user_update', list(online_users), to=request.sid)

    if room == 'main_room':
        emit('message', {
            'username': 'System',
            'message': f'{username} ist beigetreten.',
            'color': '#999999',
            'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'room': 'main_room'
        }, room='main_room')


@socketio.on('leave')
def handle_leave(data):
    username = session.get('username')
    room = data.get('room')
    if username:
        online_users.discard(username)
        user_sids.pop(username, None)
        emit('user_update', list(online_users), broadcast=True)

        if room:
            leave_room(room)

        if room == 'main_room':
            emit('message', {
                'username': 'System',
                'message': f'{username} hat den Chat verlassen.',
                'color': '#999999',
                'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            }, room='main_room')

def monitor_inactive_users():
    while True:
        now = datetime.now()
        for user, seen in list(last_seen.items()):
            if now - seen > timedelta(minutes=2):
                print(f"{user} ist inaktiv – wird ausgeloggt.")
                update_user_status(user, "offline")
                set_user_dnd(user, False)
                online_users.discard(user)
                socketio.emit('user_update', list(online_users), to='main_room')
                last_seen.pop(user)
        eventlet.sleep(60)  

eventlet.spawn_n(monitor_inactive_users)

@socketio.on('keep_alive')
def handle_keep_alive():
    username = session.get('username')
    if username:
        last_seen[username] = datetime.now()


@socketio.on('typing')
def handle_typing(data):
    username = session.get('username')
    room = data.get('room', 'main_room')
    if username:
        emit('typing', {'username': username}, room=room, include_self=False)

@socketio.on('message')
def handle_message(data):
    username = session.get('username')
    if not username:
        return

    message = data.get("message", "")
    room = data.get("room", "main_room")
    alt_msg = to_alt_language(message)
    formatted_message = alt_msg
    timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    # Nutzer getaggt?
    if "@" in message:
        words = message.split()
        tagged_users = [word[1:] for word in words if word.startswith("@")]
        for tagged_user in tagged_users:
            if user_exists(tagged_user) and tagged_user != username:
                        phone = get_phone_by_username(tagged_user)
        if phone and not get_user_dnd(tagged_user):
            try:
                requests.post("http://localhost:3000/send", json={
                    "number": phone,
                    "message": f"{username} hat dich im {'Main Room' if room == 'main_room' else 'Privatchat'} getaggt."
                })
            except Exception as e:
                print(f"Fehler beim WhatsApp-Versand an {tagged_user}: {e}")


    if room == "main_room":
        # MAIN ROOM Nachricht
        save_main_message(username, formatted_message, timestamp)
    else:
        # PRIVATE NACHRICHT
        print(f"[SOCKET] -> Erwähnte Nutzer: {room}")

        if room not in chat_history:
            chat_history[room] = []

        chat_history[room].append({
            "username": username,
            "message": formatted_message,
            "timestamp": timestamp
        })

        if len(chat_history[room]) > 50:
            chat_history[room] = chat_history[room][-50:]

        save_private_message(room, username, formatted_message)

    emit('message', {
        "username": username,
        "message": formatted_message,
        "timestamp": timestamp,
        "room": room,
        "color": get_user_color_from_db(username)
    }, room=room)

    all_users = get_all_usernames()
    mentioned_users = [word[1:] for word in message.split() if word.startswith('@')]
    mentioned_users = list(set(mentioned_users))

    print(f"[SOCKET] Erwähnte Nutzer: {mentioned_users}")

    for mentioned in mentioned_users:
        if mentioned in all_users and mentioned != username:
            if get_user_dnd(mentioned):
                print(f"[SOCKET] {mentioned} ist im DND – keine WhatsApp")
                continue
            phone = get_phone_by_username(mentioned)
            if phone:
                try:
                    print(f"[SOCKET] WhatsApp-Benachrichtigung an {mentioned}")
                    requests.post("http://localhost:3000/send", json={
                        "number": phone,
                        "message": f"{username} hat dich getaggt"
                    })
                except Exception as e:
                    print(f"❌ Fehler beim WhatsApp-Versand an {mentioned}: {e}")

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5002
    )