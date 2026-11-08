import crypto from 'node:crypto';

if (!globalThis.crypto) {
  globalThis.crypto = crypto;
}
if (!globalThis.crypto.randomUUID) {
  globalThis.crypto.randomUUID = crypto.randomUUID.bind(crypto);
}
