import express from 'express';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { makeWASocket, DisconnectReason, useMultiFileAuthState } from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';
import pino from 'pino';

const app = express();
app.use(express.json());

const __dirname = dirname(fileURLToPath(import.meta.url));
let sock;

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState(join(__dirname, 'auth_info'));
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
    logger: pino({ level: 'info' })
  });

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (connection === 'close') {
      const reason = lastDisconnect?.error?.output?.statusCode;
      if (reason !== DisconnectReason.loggedOut) {
        startBot();
      } else {
        console.log('❌ Logged out from WhatsApp');
      }
    } else if (connection === 'open') {
      console.log('✅ WhatsApp bot connected');
    }
    if (qr) {
      console.log('Scan this QR to connect:');
      qrcode.generate(qr, { small: true });
    }
  });
}

startBot();

app.post('/send', async (req, res) => {
  const { number, message } = req.body;
  if (!sock || sock.state.connection !== 'open') {
    return res.status(503).json({ status: 'not_connected' });
  }
  if (!number || !message) {
    return res.status(400).json({ status: 'invalid' });
  }
  try {
    const jid = number.includes('@') ? number : number + '@s.whatsapp.net';
    await sock.sendMessage(jid, { text: message });
    res.json({ status: 'sent' });
  } catch (err) {
    console.error('Send error:', err);
    res.status(500).json({ status: 'error' });
  }
});

const PORT = 3000;
app.listen(PORT, () => console.log(`Bot API running on port ${PORT}`));

