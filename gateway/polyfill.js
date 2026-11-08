import crypto from 'node:crypto';

try {
  Object.defineProperty(globalThis, 'crypto', {
    value: crypto,
    writable: true,
    configurable: true,
  });
} catch (e) {
  globalThis.crypto = crypto;
}

if (!globalThis.crypto.randomUUID) {
  globalThis.crypto.randomUUID = () => crypto.randomBytes(16).toString('hex');
}
