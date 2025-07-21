# 🟢 ALTCHAT v2.0.0 Base

*(Based on ALTCHAT v1.0.5 – now with full feature expansion groundwork)*

AltChat is a private real-time webchat system with built-in WhatsApp notifications, terminal-style UI, and custom encoding.

> ⚠️ This is the BASE release of v2 – building on the stable v1.0.5
> All new features (DMs, Roles, Profiles etc.) will be added step-by-step.

---

## 📁 Project Structure

```
├── altchat-v2
│   ├── app.py
│   ├── chat.db
│   ├── database.py
│   ├── static
│   │   ├── favicon.ico
│   │   ├── logo.gif
│   │   └── profile_pics
│   │       ├── default.png
│   │       └── mainroom.gif
│   ├── templates
│   │   ├── 404.html
│   │   ├── 500.html
│   │   ├── admin.html
│   │   ├── chat.html
│   │   ├── friend_requests.html
│   │   ├── login.html
│   │   ├── logout.html
│   │   ├── mychats.html
│   │   ├── profile.html
│   │   ├── register.html
│   │   └── wartungsarbeiten.html
│   └── users.db
├── README.md
├── requirements.txt
└── whatsapp-bot
    ├── bot.cjs
    ├── package.json
    └── package-lock.json
```

---

## ⚙️ Requirements

* Python 3.10+
* Node.js v18+
* pip (Python)
* npm (Node.js)
* WhatsApp account to pair

---

## 🧪 Installation

```bash
git clone https://github.com/mrgloeckchen/altchat-v2.git
cd altchat-v2
```

### 1. Python (AltChat server)

```bash
cd altchat
pip install -r ../requirements.txt
```

### 2. Node.js (WhatsApp bot)

```bash
cd ../whatsapp-bot
npm install
```

---

## 🚀 Start the system

### 1. WhatsApp bot

```bash
cd whatsapp-bot
node bot.cjs
```

> Scan QR code (first time) via WhatsApp → Linked Devices

### 2. Flask server

```bash
cd ../altchat
python3 app.py
```

> App runs at: **[http://localhost:5000](http://localhost:5000)**

---

## 🔔 WhatsApp Notifications

If you are offline and someone tags you, you will receive a Whatsapp message,

```json
{
  "number": "491234567890",
  "message": "Du wurdest von user getaggt"
```

The bot delivers it via WhatsApp.

---

## 🎨 Features in this BASE version

✅ Flask + Socket.IO real-time chat,
✅ Custom user color system,
✅ Altsprache view toggle (encoded chat),
✅ WhatsApp Express bot (QR login, session save),
✅ Login & Register system (with Admin-Code),
✅ SQLite-based persistence,
✅ Live user list,
✅ Dark/Whitemode + TikTok sans,
✅ Responsive UI groundwork,
✅ Admin/Mod/User roles (Admin Panel),
✅ Cache-busting for static files,
✅ QR Pairing for WhatsApp,
✅ Simple bot API: `/send` with `number` & `message`,

---

## 📷 Screenshot

Comming soon!

---

## 🧼 Clean Git Repo

Included `.gitignore` to avoid committing:

* `auth_info/`
* `node_modules/`
* `*.db`
* `__pycache__/`

---

## 🧠 License

MIT – mod it, fork it, remix it.
Made with 💚 by [@mrgloeckchen](https://github.com/mrgloeckchen)

---

## 📌 What's next in v2?

Coming soon (next commits):

* Direct Messaging system with friend requests
* Admin panel with live actions
* Profile system with color/foto/status
* User search
* Roles, kicks, bans, mod tools
* Ping system & DND Mode
* Full WhatsApp notification logic for DMs, pings & system alerts
