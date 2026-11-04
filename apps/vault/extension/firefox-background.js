const assistPrefix = 'assist:';
const globalKey = 'assist-all';
const globalPattern = 'https://*/*';
const globalScript = 'vault-all-https';
const pendingPrefix = 'save:';
const offerLifetime = 120_000;
const pageScripts = ['login-form.js', 'firefox-page.js'];
const popupUrl = browser.runtime.getURL('popup.html');
const tabJobs = new Map();
const pendingFills = new Map();

function httpsOrigin(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? parsed.origin : '';
  } catch {
    return '';
  }
}

function sitePermission(origin) {
  return 'https://' + new URL(origin).hostname + '/*';
}

function scriptId(origin) {
  return 'vault-' + toHex(encoder.encode(new URL(origin).hostname));
}

async function siteEnabled(origin) {
  const key = assistPrefix + origin;
  const values = await browser.storage.local.get(key);
  return values[key] === true && browser.permissions.contains({ origins: [sitePermission(origin)] });
}

async function globalEnabled() {
  const values = await browser.storage.local.get(globalKey);
  return values[globalKey] === true && browser.permissions.contains({ origins: [globalPattern] });
}

async function authorizeSite(site, { active = false, assisted = true, allowGlobal = false } = {}) {
  const tab = await browser.tabs.get(site.tab);
  if (httpsOrigin(tab.url) !== site.origin || (active && !tab.active) ||
      (assisted && !await siteEnabled(site.origin) && !(allowGlobal && await globalEnabled()))) {
    throw new Error('Site authorization changed');
  }
  return tab;
}

async function requestVault(action, site, payload, session) {
  browserKey = (await pairingStorage()) ?? null;
  if (!browserKey) return { code: 'pair_required' };
  // Connection status contains no site. The tab still has to be authorized.
  return nativeFirefoxRequest(action, action === 'status' ? null : site, payload,
    () => authorizeSite(site, { active: true }), session);
}

function inTabOrder(tab, job) {
  const next = (tabJobs.get(tab) ?? Promise.resolve()).catch(() => {}).then(job);
  tabJobs.set(tab, next);
  return next.finally(() => {
    if (tabJobs.get(tab) === next) tabJobs.delete(tab);
  });
}

async function setIndicator(tab, state) {
  const states = {
    offer: ['+', '#85530e', 'Login speichern?'],
    found: ['✓', '#226657', 'Gespeicherter Login verfügbar'],
    missing: ['+', '#85530e', 'Anmeldeformular erkannt · Login anlegen'],
    form: ['•', '#505b92', 'Anmeldeformular erkannt'],
  };
  const [text, color, title] = states[state] ?? ['', '#505b92', ''];
  try {
    await browser.action.setBadgeBackgroundColor({ tabId: tab, color });
    await browser.action.setBadgeText({ tabId: tab, text });
    await browser.action.setTitle({ tabId: tab, title: title ? 'Vault · ' + title : 'KryptoCore Vault' });
  } catch {
    // The user can close the tab while its badge is being updated.
  }
}

async function pendingOffer(tab) {
  const key = pendingPrefix + tab;
  const item = (await browser.storage.session.get(key))[key];
  if (item && item.until > Date.now()) return item;
  if (item) await clearOffer(tab);
}

async function clearOffer(tab) {
  const key = pendingPrefix + tab;
  await browser.storage.session.remove(key);
  await browser.alarms.clear(key);
}

async function saveCandidate(site, credentials, session) {
  if (typeof credentials?.username !== 'string' || !credentials.username.trim() ||
      typeof credentials.password !== 'string' || !credentials.password ||
      encoder.encode(JSON.stringify(credentials)).length > 4096) return;
  const status = await requestVault('status', site);
  if (status.code !== 'ready' || !status.saveLogin || !status.boundSave ||
      typeof session !== 'string' || status.session !== session) return;
  const lookup = await requestVault('lookup', site);
  if (lookup.code !== 'no_login') return;
  await authorizeSite(site, { active: true });
  const key = pendingPrefix + site.tab;
  const item = { id: crypto.randomUUID(), until: Date.now() + offerLifetime, origin: site.origin, session, credentials };
  await browser.alarms.create(key, { when: item.until });
  await browser.storage.session.set({ [key]: item });
  await setIndicator(site.tab, 'offer');
}

async function eligibleOffer(site) {
  const item = await pendingOffer(site.tab);
  if (!item || item.origin !== site.origin) return;
  const status = await requestVault('status', site).catch(() => null);
  if (status?.code === 'ready' && status.saveLogin && status.boundSave &&
      typeof item.session === 'string' && item.session === status.session && item.until > Date.now()) {
    const lookup = await requestVault('lookup', site).catch(() => null);
    if (lookup?.code === 'no_login' && item.until > Date.now()) return item;
  }
  await clearOffer(site.tab);
  await setIndicator(site.tab);
}

function clearRevokedOffers() {
  void browser.storage.session.get().then((values) => {
    for (const key of Object.keys(values).filter(key => key.startsWith(pendingPrefix))) {
      const tab = Number(key.slice(pendingPrefix.length));
      void inTabOrder(tab, async () => {
        const item = await pendingOffer(tab);
        if (item && !await siteEnabled(item.origin)) {
          await clearOffer(tab);
          await setIndicator(tab);
        }
      }).catch(() => {});
    }
  }).catch(() => {});
}

async function configureSite(site, enable) {
  await authorizeSite(site, { active: true, assisted: false });
  const id = scriptId(site.origin);
  const pattern = sitePermission(site.origin);
  const key = assistPrefix + site.origin;
  const registered = await browser.scripting.getRegisteredContentScripts({ ids: [id] });
  if (enable) {
    if (!await browser.permissions.contains({ origins: [pattern] })) return false;
    if (!registered.length) {
      await browser.scripting.registerContentScripts([{
        id, matches: [pattern], js: pageScripts, runAt: 'document_idle',
      }]);
    }
    await browser.storage.local.set({ [key]: true });
    await browser.scripting.executeScript({ target: { tabId: site.tab }, files: pageScripts });
  } else {
    await browser.storage.local.remove(key);
    await clearOffer(site.tab);
    await setIndicator(site.tab);
    const settings = await browser.storage.local.get();
    if (!Object.keys(settings).some((item) => item.startsWith(assistPrefix) &&
        sitePermission(item.slice(assistPrefix.length)) === pattern)) {
      if (registered.length) await browser.scripting.unregisterContentScripts({ ids: [id] });
      await browser.permissions.remove({ origins: [pattern] });
    }
  }
  return enable;
}

async function configureGlobal(site, enable) {
  const registered = await browser.scripting.getRegisteredContentScripts({ ids: [globalScript] });
  if (enable) {
    if (!await browser.permissions.contains({ origins: [globalPattern] })) return false;
    if (!registered.length) {
      await browser.scripting.registerContentScripts([{
        id: globalScript, matches: [globalPattern], js: pageScripts, runAt: 'document_idle',
      }]);
    }
    await browser.storage.local.set({ [globalKey]: true });
    await browser.scripting.executeScript({ target: { tabId: site.tab }, files: pageScripts });
  } else {
    await browser.storage.local.remove(globalKey);
    if (registered.length) await browser.scripting.unregisterContentScripts({ ids: [globalScript] });
    await browser.permissions.remove({ origins: [globalPattern] });
    if (!await siteEnabled(site.origin)) await setIndicator(site.tab);
  }
  return enable;
}

async function handleMessage(message, site, fromPopup) {
  if (fromPopup) {
    await authorizeSite(site, { active: true, assisted: false });
    if (message.action === 'enable') return configureSite(site, true);
    if (message.action === 'disable') return configureSite(site, false);
    if (message.action === 'enable-all') return configureGlobal(site, true);
    if (message.action === 'disable-all') return configureGlobal(site, false);
    const enabled = await siteEnabled(site.origin);
    const item = enabled ? await eligibleOffer(site) : undefined;
    if (message.action === 'settings') return { enabled, global: await globalEnabled(), offer: item?.id };
    if (!item || item.id !== message.id) return { code: 'expired' };
    if (message.action === 'dismiss' || message.action === 'save') {
      await clearOffer(site.tab);
      await setIndicator(site.tab);
      return message.action === 'save'
        ? requestVault('save', site, item.credentials, item.session)
        : { code: 'dismissed' };
    }
    return;
  }

  const direct = ['submit', 'fill', 'new-login'].includes(message.action);
  const tab = await authorizeSite(site, { active: message.action !== 'enabled', allowGlobal: !direct });
  if (message.action === 'enabled') return true;
  if (message.action === 'submit') return saveCandidate(site, message.credentials, message.session);
  if (message.action === 'new-login') {
    return requestVault('new_login', site);
  }
  if (message.action === 'fill') {
    if (tab.url !== site.url) return { code: 'document_changed' };
    const intent = { window: tab.windowId };
    pendingFills.set(site.tab, intent);
    try {
      const reply = await requestVault('fill_page', site);
      if (typeof reply.session !== 'string') return reply;
      const status = await requestVault('status', site);
      const current = await authorizeSite(site, { active: true });
      if (pendingFills.get(site.tab) !== intent || current.url !== site.url) {
        return { code: 'document_changed' };
      }
      return status.code === 'ready' && status.directFill && status.session === reply.session
        ? reply : { code: 'locked' };
    } finally {
      pendingFills.delete(site.tab);
    }
  }
  if (message.action === 'open') {
    await browser.action.openPopup({ windowId: tab.windowId });
    return true;
  }
  if (message.action === 'scan') {
    const scoped = await siteEnabled(site.origin);
    const item = scoped ? await eligibleOffer(site) : undefined;
    let state = item ? 'offer' : '';
    let capture = false;
    let captureSession;
    let directFill = false;
    if (!state && message.detected === true) {
      const reply = scoped ? await requestVault('lookup', site).catch(() => null) : null;
      state = reply?.code === 'login_found' ? 'found' : reply?.code === 'no_login' ? 'missing' : 'form';
      if (scoped && (state === 'missing' || state === 'found')) {
        const status = await requestVault('status', site).catch(() => null);
        if (status?.code === 'ready') {
          capture = state === 'missing' && status.saveLogin === true && status.boundSave === true &&
            typeof status.session === 'string';
          if (capture) captureSession = status.session;
          directFill = state === 'found' && status.directFill === true;
        } else {
          state = 'form';
        }
      }
    }
    await authorizeSite(site, { active: true, allowGlobal: true });
    await setIndicator(site.tab, state);
    return { state, capture, captureSession, directFill };
  }
}

browser.runtime.onMessage.addListener((message, sender) => {
  if (message?.channel !== 'vault-assist') return;
  const fromPopup = sender.url === popupUrl && !sender.tab;
  if (!fromPopup && (sender.frameId !== 0 || !sender.tab)) return;
  const site = fromPopup ? message.site : { tab: sender.tab.id, origin: httpsOrigin(sender.url), url: sender.url };
  if (!Number.isInteger(site?.tab) || !site.origin || httpsOrigin(site.origin) !== site.origin) return;
  return inTabOrder(site.tab, () => handleMessage(message, site, fromPopup)).catch(() => false);
});

browser.tabs.onUpdated.addListener((tab, change, info) => {
  if (change.status !== 'loading' && !change.url) return;
  pendingFills.delete(tab);
  void inTabOrder(tab, async () => {
    const item = await pendingOffer(tab);
    const matches = item && item.origin === httpsOrigin(change.url ?? info.url);
    if (item && !matches) await clearOffer(tab);
    await setIndicator(tab, matches ? 'offer' : '');
  }).catch(() => {});
});

browser.tabs.onRemoved.addListener((tab) => {
  pendingFills.delete(tab);
  void inTabOrder(tab, () => clearOffer(tab)).catch(() => {});
});

browser.tabs.onActivated.addListener(({ windowId }) => {
  for (const [tab, intent] of pendingFills) {
    if (intent.window === windowId) pendingFills.delete(tab);
  }
});

browser.permissions.onRemoved.addListener(clearRevokedOffers);
browser.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && Object.keys(changes).some(key =>
    key.startsWith(assistPrefix) && changes[key].newValue !== true)) clearRevokedOffers();
});

browser.alarms.onAlarm.addListener(({ name }) => {
  if (!name.startsWith(pendingPrefix)) return;
  const tab = Number(name.slice(pendingPrefix.length));
  void inTabOrder(tab, async () => {
    if (!await pendingOffer(tab)) await setIndicator(tab);
  }).catch(() => {});
});
