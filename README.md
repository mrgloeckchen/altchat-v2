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
cd whatsapp-bot && npm install && node bot.cjs
```

## Features (Early Preview)

* Login & registration with admin code - ready
* Real-time chat with online list - ready
* Simple admin panel - ready
* Profile editing - ready
* WhatsApp bot placeholder - ready

More features will be added soon.
