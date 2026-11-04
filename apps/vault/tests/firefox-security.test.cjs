const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const origin = 'https://example.invalid:8443';
const popupUrl = 'moz-extension://test/popup.html';
const credentials = { username: 'test-user', password: 'synthetic password' };
const background = readFileSync(process.env.VAULT_FIREFOX_BASELINE ||
  join(__dirname, '../extension/firefox-background.js'), 'utf8');

function fixture({ enabled = true } = {}) {
  function event() {
    let listener;
    return { addListener(callback) { listener = callback; }, emit(...args) { return listener?.(...args); } };
  }
  function storage(initial = {}) {
    const values = { ...initial };
    return {
      values,
      async get(key) { return key ? { [key]: values[key] } : { ...values }; },
      async set(update) { Object.assign(values, update); },
      async remove(key) { delete values[key]; },
    };
  }
  const local = storage(enabled ? { ['assist:' + origin]: true } : {});
  const session = storage();
  const tab = { id: 7, url: origin + '/', windowId: 3, active: true };
  const browser = {
    action: { async setBadgeBackgroundColor() {}, async setBadgeText() {}, async setTitle() {} },
    runtime: { getURL: () => popupUrl, onMessage: event() },
    tabs: { get: async () => ({ ...tab }), onActivated: event(), onUpdated: event(), onRemoved: event() },
    storage: { local, session, onChanged: event() },
    alarms: { async create() {}, async clear() {}, onAlarm: event() },
    permissions: { contains: async () => state.hostGranted, onRemoved: event() },
  };
  const state = {
    epoch: 'first-session', locked: false, hostGranted: true, now: 1_000, calls: [],
    fill: async () => ({ origin, ...credentials, session: state.epoch }),
  };
  const context = vm.createContext({
    browser, URL, TextEncoder, encoder: new TextEncoder(), crypto: { randomUUID: () => 'offer-1' },
    Date: class extends Date { static now() { return state.now; } },
    browserKey: null,
    pairingStorage: async () => ({}),
    async nativeFirefoxRequest(action, site, payload, authorize, epoch) {
      await authorize();
      state.calls.push({ action, site, payload, epoch });
      if (action === 'status') {
        return state.locked ? { code: 'locked' } :
          { code: 'ready', boundSave: true, saveLogin: true, directFill: true, session: state.epoch };
      }
      if (action === 'lookup') return { code: state.saved ? 'login_found' : 'no_login' };
      if (action === 'fill_page') return state.fill();
      if (action === 'save') return { code: 'saved' };
      throw new Error('Unexpected request');
    },
  });
  vm.runInContext(background, context);
  return {
    state, tab, browser, local, session,
    page(action, data = {}, overrides = {}) {
      return browser.runtime.onMessage.emit({ channel: 'vault-assist', action, ...data },
        { frameId: 0, url: tab.url, tab: { ...tab }, ...overrides });
    },
    popup(action, data = {}) {
      return browser.runtime.onMessage.emit({ channel: 'vault-assist', action, site: { tab: tab.id, origin }, ...data },
        { url: popupUrl });
    },
    async settled() {
      await new Promise(resolve => setImmediate(resolve));
      await vm.runInContext('inTabOrder(7, () => {})', context);
    },
  };
}

test('website assistance requires opt-in, an exact HTTPS origin and the top frame', async () => {
  const setup = fixture({ enabled: false });
  assert.equal(await setup.page('enabled'), false);
  assert.equal((await setup.popup('settings')).global, false);
  setup.local.values['assist:' + origin] = true;
  assert.equal(await setup.page('enabled'), true);
  assert.equal(await setup.page('fill', {}, { frameId: 1 }), undefined);
  assert.equal(await setup.page('fill', {}, { url: 'http://example.invalid:8443/' }), undefined);
  setup.tab.url = 'https://example.invalid:9443/';
  assert.equal(await setup.page('fill'), false);
  assert.equal(setup.state.calls.length, 0);
});

test('a submission and its pending offer cannot survive a vault session change', async () => {
  const setup = fixture();
  const scan = await setup.page('scan', { detected: true });
  assert.equal(scan.capture, true);
  await setup.page('submit', { credentials, session: scan.captureSession });
  assert.equal((await setup.popup('settings')).offer, 'offer-1');
  setup.state.epoch = 'replacement-session';
  assert.equal((await setup.popup('save', { id: 'offer-1' })).code, 'expired');
  assert.equal(setup.session.values['save:7'], undefined);
  await setup.page('submit', { credentials, session: scan.captureSession });
  assert.equal(setup.session.values['save:7'], undefined);
  assert.equal(setup.state.calls.some(call => call.action === 'save'), false);
});

test('save authorization carries the session to the native endpoint', async () => {
  const setup = fixture();
  await setup.page('submit', { credentials, session: setup.state.epoch });
  assert.equal((await setup.popup('save', { id: 'offer-1' })).code, 'saved');
  assert.equal(setup.state.calls.find(call => call.action === 'save').epoch, setup.state.epoch);
  assert.equal(setup.session.values['save:7'], undefined);
});

test('a login added in Vault supersedes a pending save offer without toggling permissions', async () => {
  const setup = fixture();
  await setup.page('submit', { credentials, session: setup.state.epoch });
  assert.equal((await setup.page('scan', { detected: true })).state, 'offer');
  setup.state.saved = true;
  const scan = await setup.page('scan', { detected: true });
  assert.equal(scan.state, 'found');
  assert.equal(scan.directFill, true);
  assert.equal(scan.capture, false);
  assert.equal((await setup.popup('settings')).offer, undefined);
  assert.equal(setup.session.values['save:7'], undefined);
});

test('expiry, lock, permission revocation and tab close discard pending credentials', async () => {
  for (const action of ['expired', 'locked', 'revoked', 'site-disabled', 'closed', 'dismissed']) {
    const setup = fixture();
    await setup.page('submit', { credentials, session: setup.state.epoch });
    assert.equal(setup.session.values['save:7']?.id, 'offer-1');
    if (action === 'expired') {
      setup.state.now += 120_001;
      setup.browser.alarms.onAlarm.emit({ name: 'save:7' });
    } else if (action === 'locked') {
      setup.state.locked = true;
      await setup.popup('settings');
    } else if (action === 'revoked') {
      setup.state.hostGranted = false;
      setup.browser.permissions.onRemoved.emit({ origins: ['https://example.invalid/*'] });
    } else if (action === 'site-disabled') {
      const key = 'assist:' + origin;
      delete setup.local.values[key];
      setup.browser.storage.onChanged.emit({ [key]: { oldValue: true } }, 'local');
    } else if (action === 'closed') {
      setup.browser.tabs.onRemoved.emit(7);
    } else {
      await setup.popup('dismiss', { id: 'offer-1' });
    }
    await setup.settled();
    assert.equal(Object.hasOwn(setup.session.values, 'save:7'), false, action);
  }
});

test('in-flight fill drops credentials after lock, reload, or switching away and back', async () => {
  for (const change of ['lock', 'reload', 'switch']) {
    const setup = fixture();
    let started;
    const reachedFill = new Promise(resolve => { started = resolve; });
    let release;
    setup.state.fill = () => new Promise(resolve => { release = resolve; started(); });
    const result = setup.page('fill');
    await reachedFill;
    if (change === 'lock') setup.state.locked = true;
    if (change === 'reload') setup.browser.tabs.onUpdated.emit(7, { status: 'loading' }, setup.tab);
    if (change === 'switch') {
      setup.browser.tabs.onActivated.emit({ tabId: 8, windowId: 3 });
      setup.browser.tabs.onActivated.emit({ tabId: 7, windowId: 3 });
    }
    release({ origin, ...credentials, session: setup.state.epoch });
    const reply = await result;
    assert.equal(Object.hasOwn(reply ?? {}, 'password'), false, change);
  }
});
