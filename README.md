# ALTCHAT v2.0.0

A modern, Flask-SocketIO based chat platform with user roles and WhatsApp notification support.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python altchat/app.py
```

The WhatsApp bot can be started separately via Node.js:

```bash
cd whatsapp-bot && npm install && node bot.mjs
```

## Features (Early Preview)

* Login & registration with admin code
* Real-time chat with online list
* Simple admin panel
* Profile editing
* WhatsApp bot placeholder

More features will be added soon.
