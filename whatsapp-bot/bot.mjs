import express from 'express';
// Placeholder for WhatsApp bot using Baileys
const app = express();
app.post('/send', (req, res) => {
  // TODO: Implement message sending via WhatsApp
  res.json({status: 'ok'});
});
app.listen(3001, () => console.log('Bot running on port 3001'));
