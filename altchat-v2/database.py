import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

DB_PATH = 'users.db'

def init_db():
    conn = sqlite3.connect(chat.db)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            phone TEXT,
            role TEXT DEFAULT 'user',
            color TEXT,
            status TEXT DEFAULT 'offline',
            dnd INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def init_altchat_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1 TEXT NOT NULL,
            user2 TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'accepted'))
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            bio TEXT DEFAULT '',
            profile_pic TEXT DEFAULT '/static/profile_pics/default.png'
        )
    ''')

    conn.commit()
    conn.close()

def add_user(username, password, phone):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password, phone) VALUES (?, ?, ?)',
                  (username, password, phone))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0] == password
    return False

def user_exists(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM users WHERE username = ?', (username,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def get_role(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'user'

def get_phone_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT phone FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_usernames():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username FROM users')
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        keys = [description[0] for description in c.description]
        return dict(zip(keys, row))
    return None

def get_all_users_with_roles():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username, role FROM users')
    rows = c.fetchall()
    conn.close()
    return rows

def ban_user(username):
    # Dummy
    pass

def temp_ban_user(username, duration):
    # Dummy
    pass

def unban_user(username):
    # Dummy
    pass

def reset_user_password(username, new_password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hashed_pw = generate_password_hash(new_password)
    c.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_pw, username))
    conn.commit()
    conn.close()

def rename_user(old_username, new_username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET username = ? WHERE username = ?', (new_username, old_username))
    conn.commit()
    conn.close()

def set_user_color(username, color):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET color = ? WHERE username = ?', (color, username))
    conn.commit()
    conn.close()

def get_user_color_from_db(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT color FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def log_admin_action(actor, action, target):
    # Optional Logging
    pass

def get_user_history(username):
    # Dummy
    return []

# ✅ NEU: STATUS + DND Handling

def update_user_status(username, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET status = ? WHERE username = ?', (status, username))
    conn.commit()
    conn.close()

def get_user_status(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT status FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'offline'

def set_user_dnd(username, state: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET dnd = ? WHERE username = ?', (1 if state else 0, username))
    conn.commit()
    conn.close()

def get_user_dnd(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT dnd FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def delete_user(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Fehler beim Löschen von '{username}': {e}")
        return False
    finally:
        conn.close()

def get_all_user_phones():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("SELECT phone FROM users")
        result = c.fetchall()
        return [row[0] for row in result if row[0]]  
    except Exception as e:
        print(f"[DB] Fehler beim Abrufen der Telefonnummern: {e}")
        return []
    finally:
        conn.close()

def toggle_mod_status(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        # Aktuelle Rolle holen
        c.execute("SELECT role FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            print(f"[DB] User '{username}' nicht gefunden.")
            return False

        current_role = row[0]

        if current_role == 'admin':
            print(f"[DB] Admin-Rolle darf nicht geändert werden.")
            return False

        new_role = 'mod' if current_role == 'user' else 'user'
        c.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Fehler bei toggle_mod_status für '{username}': {e}")
        return False
    finally:
        conn.close()

def promote_to_admin(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        # Sicherstellen, dass der User existiert
        c.execute("SELECT role FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            print(f"[DB] Benutzer '{username}' nicht gefunden.")
            return False

        # Rolle aktualisieren
        c.execute("UPDATE users SET role = 'admin' WHERE username = ?", (username,))
        conn.commit()
        print(f"[DB] Benutzer '{username}' wurde zu Admin befördert.")
        return True
    except Exception as e:
        print(f"[DB] Fehler bei promote_to_admin für '{username}': {e}")
        return False
    finally:
        conn.close()