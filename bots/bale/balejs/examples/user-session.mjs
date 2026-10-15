import { UserClient } from '../dist/index.js';

// Adapter deliberately not bundled: provide one based on a documented,
// authorized Bale user-session protocol. The library does not guess endpoints.
const adapter = globalThis.baleUserAdapter;
if (!adapter) throw new Error('Provide a documented user-session adapter as globalThis.baleUserAdapter.');
const session = process.env.BALE_USER_SESSION;
if (!session) throw new Error('Store a session in BALE_USER_SESSION; do not commit it.');
const user = new UserClient({ adapter, session });
await user.sendMessage(process.env.BALE_CHAT_ID, 'پیام آزمایشی از نشست کاربر');
