const nativeHost = 'com.kryptocorelabs.vault';
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });
const channelKeyContext = encoder.encode('KryptoCore Vault Firefox v5 channel key');
const toHex = (bytes) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
let browserKey;
let wasmReady;

function fromHex(hex) {
  if (typeof hex !== 'string' || !hex.length || hex.length > 32768 ||
      hex.length % 2 || !/^[0-9a-f]+$/.test(hex)) throw new Error('Invalid native frame');
  return Uint8Array.from(hex.match(/../g), (byte) => parseInt(byte, 16));
}

function pairingStorage(key) {
  return new Promise((resolve, reject) => {
    const opening = indexedDB.open('vault-connection', 1);
    opening.onupgradeneeded = () => opening.result.createObjectStore('keys');
    opening.onerror = () => reject(opening.error);
    opening.onsuccess = () => {
      const db = opening.result;
      const transaction = db.transaction('keys', key ? 'readwrite' : 'readonly');
      const store = transaction.objectStore('keys');
      const request = key ? store.put(key, 'firefox-v5') : store.get('firefox-v5');
      transaction.oncomplete = () => {
        db.close();
        resolve(request.result);
      };
      transaction.onabort = () => {
        db.close();
        reject(transaction.error);
      };
    };
  });
}

async function loadChannel() {
  let instance;
  const random = (offset, length) => {
    crypto.getRandomValues(new Uint8Array(instance.exports.memory.buffer, offset, length));
  };
  const response = await fetch(browser.runtime.getURL('vault_firefox_channel.wasm'));
  ({ instance } = await WebAssembly.instantiate(await response.arrayBuffer(), { env: { vault_random: random } }));
  return instance.exports;
}

async function exchange(key, pairing, request, authorize) {
  const wasm = await (wasmReady ??= loadChannel());
  const port = browser.runtime.connectNative(nativeHost);
  const handle = wasm.vault_channel_new();
  let pending;
  const timeout = setTimeout(() => {
    pending?.reject(new Error('Vault connection timed out'));
    port.disconnect();
  }, 5000);

  function copyResult(length) {
    if (length < 0 || length > 16384) throw new Error('Invalid encrypted Firefox message');
    const buffer = new Uint8Array(wasm.memory.buffer, wasm.vault_channel_buffer(handle), length);
    const result = buffer.slice();
    buffer.fill(0);
    return result;
  }

  function step(operation, bytes) {
    if (bytes.length > 16384) throw new Error('Message too large');
    new Uint8Array(wasm.memory.buffer, wasm.vault_channel_buffer(handle), bytes.length).set(bytes);
    return copyResult(wasm.vault_channel_step(handle, operation, bytes.length));
  }

  function send(frame) {
    return new Promise((resolve, reject) => {
      pending = { resolve, reject };
      port.postMessage(frame);
    });
  }

  port.onMessage.addListener((message) => {
    const callback = pending;
    pending = undefined;
    callback?.resolve(message);
  });
  port.onDisconnect.addListener(() => {
    pending?.reject(new Error('Vault connection closed'));
  });
  try {
    new Uint8Array(wasm.memory.buffer, wasm.vault_channel_buffer(handle), 32).set(key);
    const first = copyResult(wasm.vault_channel_start(handle, 1, Number(pairing)));
    const handshake = await send({ v: 5, enroll: pairing, m: toHex(first) });
    if (handshake?.v !== 5) return { code: 'upgrade_required' };
    if (['unavailable', 'pair_required'].includes(handshake.code)) return { code: handshake.code };
    step(0, fromHex(handshake.m));
    if (authorize) await authorize();
    const plaintext = encoder.encode(JSON.stringify(request));
    let encrypted;
    try {
      encrypted = step(1, plaintext);
    } finally {
      plaintext.fill(0);
    }
    const result = await send({ v: 5, m: toHex(encrypted) });
    if (result?.v !== 5) throw new Error('Unexpected native reply');
    const decoded = step(2, fromHex(result.m));
    try {
      return JSON.parse(decoder.decode(decoded));
    } finally {
      decoded.fill(0);
    }
  } finally {
    clearTimeout(timeout);
    wasm.vault_channel_free(handle);
    port.disconnect();
  }
}

async function pairFirefox(code) {
  const key = fromHex(code);
  try {
    const reply = await exchange(key, true, { action: 'pair' });
    if (reply.code !== 'paired') return reply;
    const raw = fromHex(reply.key);
    try {
      const pairing = await crypto.subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      await pairingStorage(pairing);
      browserKey = pairing;
      return { code: 'paired' };
    } finally {
      raw.fill(0);
    }
  } finally {
    key.fill(0);
  }
}

async function nativeFirefoxRequest(action, site, payload, authorize, session) {
  if (!browserKey) return { code: 'pair_required' };
  if (payload !== undefined && encoder.encode(JSON.stringify(payload)).length > 4096) return { code: 'too_large' };
  const key = new Uint8Array(await crypto.subtle.sign('HMAC', browserKey, channelKeyContext));
  try {
    return await exchange(key, false, { action, site: site?.origin, data: payload, session }, authorize);
  } finally {
    key.fill(0);
  }
}
