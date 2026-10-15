import { BotClient } from '../dist/index.js';

const token = process.env.BALE_BOT_TOKEN;
if (!token) throw new Error('Set BALE_BOT_TOKEN in the environment.');
const bot = new BotClient({ token });
bot.onCommand('start', (msg, _args, client) => client.sendMessage(msg.chat.id, 'سلام! من ربات اکو هستم.'));
bot.onMessage((msg, client) => {
  if (typeof msg.text === 'string' && !msg.text.startsWith('/')) return client.sendMessage(msg.chat.id, `گفتی: ${msg.text}`);
});
const stop = new AbortController();
process.once('SIGINT', () => stop.abort());
process.once('SIGTERM', () => stop.abort());
await bot.polling({ signal: stop.signal });
