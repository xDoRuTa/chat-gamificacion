import crypto from 'node:crypto';

if (!globalThis.crypto) {
  globalThis.crypto = crypto;
}
if (!globalThis.crypto.randomUUID) {
  globalThis.crypto.randomUUID = () => crypto.randomBytes(16).toString('hex');
}