import assert from 'node:assert/strict';
import { Bale, BotClient, UserClient, BaleValidationError, parseBaleLink, chunkText } from '../dist/index.js';

assert.equal(typeof Bale.bot, 'function');
assert.equal(typeof Bale.user, 'function');
assert.deepEqual(parseBaleLink('https://ble.ai/channel/12'), { isBot: false, target: 'channel', messageId: 12 });
assert.equal(chunkText('x'.repeat(850), 300).length, 3);
assert.throws(() => new BotClient({ token: '' }), BaleValidationError);

const calls = [];
const fakeFetch = async (url, init) => {
  calls.push({ url, init });
  return { ok: true, status: 200, text: async () => JSON.stringify({ ok: true, result: { message_id: 7 } }) };
};
const bot = new BotClient({ token: 'TEST_TOKEN', baseUrl: 'https://api.example/bot', fetchImpl: fakeFetch, maxRetries: 0 });
const response = await bot.sendMessage('12345', 'سلام');
assert.equal(response.message_id, 7);
assert.match(calls[0].url, /TEST_TOKEN\/sendMessage$/);
assert.equal(JSON.parse(calls[0].init.body).text, 'سلام');

const updates = [];
bot.onCommand('start', async (msg) => updates.push(`command:${msg.text}`));
bot.onMessage(async (msg) => updates.push(`message:${msg.text}`));
await bot.handleUpdate({ message: { text: '/start hello', chat: { id: 1 } } });
assert.deepEqual(updates, ['command:/start hello', 'message:/start hello']);

let userPayload;
const user = new UserClient({ session: 'u:secret', adapter: { request: async (method, payload, ctx) => { userPayload = { method, payload, ctx }; return { ok: true }; } } });
await user.sendMessage('123', 'test');
assert.equal(userPayload.method, 'sendMessage');
assert.equal(userPayload.ctx.session, 'u:secret');

console.log('balejs selftest: PASS (exports, validation, bot REST transport, command/message handlers, saved user session adapter)');
