const form = document.querySelector('#request');
const code = document.querySelector('#code');
const status = document.querySelector('#status');
const password = document.querySelector('#password');
const username = document.querySelector('#username');
const fill = document.querySelector('#fill');
const connection = document.querySelector('#connection');
const submit = form.querySelector('button');
const offer = document.querySelector('#offer');
const saveLogin = document.querySelector('#save-login');
const newLogin = document.querySelector('#new-login');
const pairing = document.querySelector('#pairing');
const pairingCode = document.querySelector('#pairing-code');
const pairingForm = document.querySelector('#pair-firefox');
const siteTools = document.querySelector('#site-tools');
const toggleAssist = document.querySelector('#toggle-assist');
const toggleGlobal = document.querySelector('#toggle-global');
const submitted = document.querySelector('#submitted');
const confirmSubmit = document.querySelector('#confirm-submit');
const dismissSubmit = document.querySelector('#dismiss-submit');
const firefox = typeof browser !== 'undefined' && browser.runtime.getURL('').startsWith('moz-extension://');
const extension = firefox ? browser : chrome;
let probing = false;
let submitting = false;
let activeFormSite;
let lookupSupported = false;
let saveSupported = false;
let boundSaveSupported = false;
let newLoginSupported = false;
let offerRevision = 0;
let assistEnabled = false;
let globalEnabled = false;
let submittedOffer;
let assistBusy = false;
let manualFirefoxFill;
let loginTimer;
let pageRevision = 0;

function fillProblem(result) {
  if (result === 'ambiguous') return 'Mehrere Formulare gefunden. Klicke zuerst in das gewünschte Anmeldefeld und öffne Vault erneut.';
  if (result === 'occupied') return 'Im Formular stehen bereits andere Daten. Prüfe die Felder vor dem Ausfüllen.';
  return 'Kein eindeutiges Anmeldeformular gefunden. Du kannst den Login manuell übernehmen.';
}

async function activeSite() {
  const [tab] = await extension.tabs.query({ active: true, currentWindow: true });
  const url = new URL(tab?.url);
  if (url.protocol !== 'https:') throw new Error('HTTPS required');
  return { tab: tab.id, window: tab.windowId, origin: url.origin, url: url.href };
}

async function requireSameTab(site) {
  const current = await activeSite();
  if (current.tab !== site.tab || current.origin !== site.origin ||
      (site.revision !== undefined && site.revision !== pageRevision) ||
      (site.documentToken && current.url !== site.url)) throw new Error('Active page changed');
}

async function runLoginForm(site, action, user = '', secret = '') {
  try {
    await requireSameTab(site);
    const [result] = await extension.scripting.executeScript({
      target: { tabId: site.tab, frameIds: [0] },
      func: loginForm,
      args: [site.origin, action, user, secret, null, site.documentToken ?? null],
    });
    if (result?.error && site.documentToken) return 'document-changed';
    return result?.result;
  } catch (error) {
    if (site.documentToken) return 'document-changed';
    throw error;
  }
}

function showLogin(entry) {
  username.value = entry.username;
  password.value = entry.password;
  document.querySelector('#login').hidden = false;
  form.hidden = true;
  clearTimeout(loginTimer);
  loginTimer = setTimeout(() => {
    if (password.value) clearLogin('Anzeige beendet.');
  }, 30_000);
}

function firefoxRequest(action, site, payload, session) {
  return nativeFirefoxRequest(action, site, payload, site && (() => requireSameTab(site)), session);
}

function assist(action, data) {
  return browser.runtime.sendMessage({ channel: 'vault-assist', action, site: activeFormSite, ...data });
}

async function updateAssist() {
  if (assistBusy || !activeFormSite) return;
  const settings = await assist('settings').catch(() => false);
  if (!settings) {
    siteTools.hidden = submitted.hidden = true;
    return;
  }
  assistEnabled = settings.enabled;
  globalEnabled = settings.global === true;
  submittedOffer = settings.offer;
  siteTools.hidden = false;
  toggleAssist.textContent = assistEnabled ? 'Für diese Website ausschalten' : 'Für diese Website einschalten';
  toggleGlobal.textContent = globalEnabled ? 'Allgemeine Erkennung ausschalten' : 'Auf allen HTTPS-Seiten erkennen';
  submitted.hidden = !submittedOffer;
}

async function changeAssist(allSites) {
  if (assistBusy || !activeFormSite) return;
  assistBusy = toggleAssist.disabled = toggleGlobal.disabled = true;
  const enable = !(allSites ? globalEnabled : assistEnabled);
  try {
    const pattern = allSites ? 'https://*/*' : 'https://' + new URL(activeFormSite.origin).hostname + '/*';
    if (enable && !await browser.permissions.request({ origins: [pattern] })) {
      status.textContent = 'Der Website-Assistent bleibt ausgeschaltet.';
      return;
    }
    const action = (enable ? 'enable' : 'disable') + (allSites ? '-all' : '');
    if (await assist(action) !== enable) throw new Error('Site setup failed');
    const name = allSites ? 'Allgemeine Erkennung' : 'Website-Assistent';
    status.textContent = name + (enable ? ' eingeschaltet.' : ' ausgeschaltet.');
  } catch {
    status.textContent = 'Der Website-Assistent konnte hier nicht umgestellt werden.';
  } finally {
    assistBusy = toggleAssist.disabled = toggleGlobal.disabled = false;
    await updateAssist();
  }
}

async function finishSubmitted(action) {
  if (assistBusy || !submittedOffer) return;
  assistBusy = confirmSubmit.disabled = dismissSubmit.disabled = true;
  try {
    const reply = await assist(action, { id: submittedOffer });
    const messages = {
      saved: 'Login in Vault gespeichert.',
      exists: 'Für diese Website gibt es bereits einen Login.',
      dismissed: 'Login verworfen.',
      locked: 'Entsperre Vault und melde dich erneut an.',
      save_disabled: 'Im strengen Modus legst du neue Logins in Vault an.',
      expired: 'Der Speicherhinweis ist abgelaufen.',
      stale_session: 'Die Tresorsitzung hat gewechselt. Melde dich erneut an.',
    };
    status.textContent = messages[reply?.code] ?? 'Der Login konnte nicht gespeichert werden.';
    if (reply?.code === 'saved' || reply?.code === 'exists') await refreshLoginOffer();
  } catch {
    status.textContent = 'Der Login konnte nicht gespeichert werden.';
  } finally {
    assistBusy = confirmSubmit.disabled = dismissSubmit.disabled = false;
    await updateAssist();
  }
}

function showConnection(code) {
  const messages = {
    ready: 'Mit Vault verbunden',
    locked: 'Vault gesperrt · Tresor entsperren',
    unavailable: 'Vault öffnen, um zu verbinden',
    pair_required: 'Einmalige Verbindung mit Vault',
    upgrade_required: 'Aktualisiere die Vault-App und öffne sie erneut.',
    checking: 'Verbindung wird geprüft …',
  };
  const text = Object.hasOwn(messages, code) ? messages[code] : 'Vault-Verbindung fehlt · aktuelle Vault-App öffnen';
  connection.dataset.state = code;
  if (connection.textContent !== text) connection.textContent = text;
  pairing.hidden = code !== 'pair_required';
  submit.disabled = code !== 'ready' || submitting;
  if (code !== 'ready') {
    offerRevision++;
    offer.hidden = saveLogin.hidden = newLogin.hidden = true;
    submit.hidden = false;
    if (password.value) clearLogin('Anzeige beendet.');
  }
}

function showLoginOffer(text, { canFill = true, canSave = false, canCreate = false } = {}) {
  if (offer.textContent !== text) offer.textContent = text;
  offer.hidden = !text;
  submit.hidden = !canFill;
  saveLogin.hidden = !canSave;
  newLogin.hidden = !canCreate;
}

async function refreshLoginOffer() {
  if (!activeFormSite || connection.dataset.state !== 'ready') return;
  const revision = ++offerRevision;
  if (!lookupSupported) {
    showLoginOffer('Für Login-Vorschläge und Speichern ist ein Vault-Update nötig.');
    return;
  }
  if (offer.hidden) showLoginOffer('Anmeldeformular wird geprüft …');
  try {
    const site = { ...activeFormSite, revision: pageRevision };
    const detected = await runLoginForm(site, 'inspect');
    if (revision !== offerRevision) return;
    if (detected?.ambiguous) {
      showLoginOffer(fillProblem('ambiguous'));
      return;
    }
    if (!detected) {
      showLoginOffer('Kein eindeutiges Anmeldeformular erkannt.');
      return;
    }
    const entry = await firefoxRequest('lookup', site);
    if (revision !== offerRevision) return;
    if (entry.code === 'login_found') {
      showLoginOffer(entry.username ? 'Gespeicherter Login · ' + entry.username : 'Gespeicherter Login gefunden.');
    } else if (entry.code === 'no_login') {
      let text = 'Anmeldeformular erkannt. Für diese Website ist noch kein Login gespeichert.';
      if (detected.capturable && !saveSupported) {
        text = boundSaveSupported
          ? 'Im strengen Modus legst du neue Logins in Vault an.'
          : 'Aktualisiere Vault auf RC.2, um Logins im Add-on zu speichern.';
      }
      showLoginOffer(text, { canFill: false, canSave: detected.capturable && saveSupported, canCreate: newLoginSupported });
    } else {
      showLoginOffer('');
    }
  } catch {
    if (revision === offerRevision) showLoginOffer('Anmeldeformular konnte nicht erkannt werden.');
  }
}

async function openDesktopEditor() {
  if (newLogin.disabled || connection.dataset.state !== 'ready') return;
  newLogin.disabled = true;
  try {
    const reply = await firefoxRequest('new_login', activeFormSite);
    status.textContent = {
      opening: 'Der Editor für den neuen Login öffnet sich in Vault.',
      busy: 'Schließe zuerst den offenen Dialog in Vault.',
      exists: 'Für diese Website gibt es bereits einen Login.',
      locked: 'Entsperre zuerst deinen Tresor.',
    }[reply.code] ?? 'Der Editor konnte nicht geöffnet werden.';
  } catch {
    status.textContent = 'Der Editor konnte nicht geöffnet werden.';
  } finally {
    newLogin.disabled = false;
  }
}

async function saveFromFirefox() {
  if (submitting || !activeFormSite || !saveSupported || connection.dataset.state !== 'ready') return;
  submitting = saveLogin.disabled = submit.disabled = true;
  try {
    const current = await activeSite();
    if (current.tab !== activeFormSite.tab || current.origin !== activeFormSite.origin) return;
    const target = { ...current, revision: pageRevision };
    const connectionState = await firefoxRequest('status');
    if (connectionState.code !== 'ready' || !connectionState.boundSave ||
        typeof connectionState.session !== 'string') return;
    target.documentToken = await runLoginForm(target, 'bind');
    if (typeof target.documentToken !== 'string' || target.documentToken.length !== 36) return;
    const credentials = await runLoginForm(target, 'capture');
    if (typeof credentials?.password !== 'string') {
      status.textContent = 'Fülle Benutzername und Passwort im Anmeldeformular aus und versuche es erneut.';
      return;
    }
    const reply = await firefoxRequest('save', target, credentials, connectionState.session);
    if (reply.code === 'saved' || reply.code === 'exists') {
      status.textContent = reply.code === 'saved' ? 'Login in Vault gespeichert.' : 'Für diese Website gibt es bereits einen Login.';
      await refreshLoginOffer();
    } else if (reply.code === 'save_disabled') {
      status.textContent = 'Im strengen Modus legst du neue Logins in Vault an.';
    } else if (reply.code === 'too_large') {
      status.textContent = 'Dieser Login ist zu groß. Lege ihn direkt in Vault an.';
    } else if (reply.code === 'locked' || reply.code === 'unavailable') {
      showConnection(reply.code);
    } else if (reply.code === 'stale_session') {
      status.textContent = 'Die Tresorsitzung hat gewechselt. Gib den Login erneut frei.';
    } else {
      status.textContent = 'Login konnte nicht gespeichert werden.';
    }
  } catch {
    status.textContent = 'Login konnte nicht gespeichert werden. Prüfe den geöffneten Tab und Vault.';
  } finally {
    submitting = saveLogin.disabled = false;
    submit.disabled = connection.dataset.state !== 'ready';
  }
}

async function refreshConnection() {
  if (probing || submitting) return;
  probing = true;
  try {
    if (browserKey === undefined) browserKey = (await pairingStorage()) ?? null;
    const reply = await firefoxRequest('status');
    // A ready reply must have been authenticated with the stored browser key.
    if (reply.code === 'ready' && !browserKey) throw new Error('Unauthenticated status');
    const supportsBoundSave = reply.boundSave === true;
    const canSave = Boolean(reply.saveLogin && supportsBoundSave);
    lookupSupported = Boolean(reply.loginLookup);
    saveSupported = canSave;
    boundSaveSupported = supportsBoundSave;
    newLoginSupported = Boolean(reply.newLogin);
    showConnection(reply.code);
    if (manualFirefoxFill && reply.session !== manualFirefoxFill.session) {
      clearLogin('Vault-Freigabe beendet.');
    }
    if (reply.code === 'ready') await refreshLoginOffer();
  } catch {
    showConnection('upgrade_required');
  } finally {
    probing = false;
  }
}

async function setup() {
  if (firefox) {
    document.querySelector('#code-label').hidden = code.hidden = true;
    submit.textContent = 'Login ausfüllen';
    connection.hidden = false;
    showConnection('checking');
    pairingForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (submitting) return;
      const value = pairingCode.value.trim().toLowerCase();
      pairingCode.value = '';
      if (!/^[0-9a-f]{64}$/.test(value)) {
        status.textContent = 'Der Verbindungscode ist ungültig.';
        return;
      }
      submitting = true;
      const connect = pairingForm.querySelector('button');
      connect.disabled = true;
      try {
        const reply = await pairFirefox(value);
        status.textContent = reply.code === 'paired' ? 'Firefox verbunden.' :
          'Verbindung fehlgeschlagen. Öffne die aktuelle Vault-App und prüfe den Code.';
      } catch {
        status.textContent = 'Verbindung fehlgeschlagen. Öffne die aktuelle Vault-App und erstelle einen neuen Code.';
      } finally {
        submitting = connect.disabled = false;
        await refreshConnection();
      }
    });
    refreshConnection();
    setInterval(refreshConnection, 2000);
  }
  let site;
  try {
    site = await activeSite();
    document.querySelector('#site').textContent = site.origin;
  } catch {
    form.hidden = true;
    status.textContent = 'Öffne zuerst eine HTTPS-Seite.';
    return;
  }
  if (firefox) {
    activeFormSite = site;
    const invalidatePage = () => {
      pageRevision++;
      offerRevision++;
      showLoginOffer('');
      if (manualFirefoxFill) clearLogin('Die Seite hat gewechselt.');
    };
    browser.tabs.onActivated.addListener(({ windowId }) => {
      if (windowId === site.window) invalidatePage();
    });
    browser.tabs.onUpdated.addListener((tab, change) => {
      if (tab === site.tab && (change.status === 'loading' || change.url)) invalidatePage();
    });
    browser.tabs.onRemoved.addListener(tab => {
      if (tab === site.tab) invalidatePage();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) invalidatePage();
    });
    saveLogin.addEventListener('click', saveFromFirefox);
    newLogin.addEventListener('click', openDesktopEditor);
    toggleAssist.addEventListener('click', () => changeAssist(false));
    toggleGlobal.addEventListener('click', () => changeAssist(true));
    confirmSubmit.addEventListener('click', () => finishSubmitted('save'));
    dismissSubmit.addEventListener('click', () => finishSubmitted('dismiss'));
    void updateAssist();
    setInterval(updateAssist, 2000);
    if (connection.dataset.state === 'ready') refreshLoginOffer();
  }

  const copySite = document.querySelector('#copy-site');
  copySite.hidden = false;
  copySite.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(site.origin);
      status.textContent = 'Website kopiert. Füge sie im Vault-Feld „Website“ ein.';
    } catch {
      status.textContent = 'Kopieren fehlgeschlagen. Du kannst die angezeigte Adresse markieren und kopieren.';
    }
  });

  fill.addEventListener('click', async () => {
    if (!password.value) return;
    fill.disabled = true;
    try {
      const target = firefox ? manualFirefoxFill?.site : site;
      if (!target || (firefox && !await currentVaultSession(manualFirefoxFill.session))) {
        clearLogin('Vault-Freigabe beendet.');
        return;
      }
      const result = await runLoginForm(target, 'fill', username.value, password.value);
      if (result === 'document-changed') {
        clearLogin('Die Seite hat gewechselt. Fordere den Login erneut an.');
        return;
      }
      if (!['both', 'password', 'username'].includes(result)) {
        status.textContent = fillProblem(result);
        return;
      }
      if (result === 'username') {
        status.textContent = 'Benutzername eingesetzt. Gehe zum Passwortfeld. Nach einem Seitenwechsel gib den Login erneut frei.';
      } else {
        clearLogin('Ausgefüllt. Prüfe die Felder und melde dich selbst an.');
      }
    } catch {
      status.textContent = 'Ausfüllen fehlgeschlagen. Prüfe den geöffneten Tab.';
    } finally {
      fill.disabled = false;
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled || submitting) return;
    const match = firefox ? null : /^(\d{1,5}):([a-f0-9]{64})$/.exec(code.value.trim());
    code.value = '';
    if (!firefox && (!match || Number(match[1]) < 1 || Number(match[1]) > 65535)) {
      status.textContent = 'Der Einmalcode ist ungültig.';
      return;
    }
    submitting = submit.disabled = true;
    try {
      if (firefox) {
        await fillFromFirefox(site);
        return;
      }
      const response = await fetch('http://127.0.0.1:' + Number(match[1]) + '/login', {
        method: 'POST', headers: { 'X-Vault-Code': match[2], 'X-Vault-Site': site.origin },
        credentials: 'omit', redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error('Request rejected');
      const entry = await response.json();
      await requireSameTab(site);
      if (entry.origin !== site.origin) throw new Error('Active origin changed');
      showLogin(entry);
      status.textContent = 'Login für diese Seite freigegeben.';
    } catch {
      status.textContent = firefox ? 'Ausfüllen fehlgeschlagen. Prüfe den geöffneten Tab und die Vault-Verbindung.' :
        'Abruf fehlgeschlagen. Prüfe Seite und Einmalcode in Vault.';
    } finally {
      submitting = false;
      submit.disabled = firefox && connection.dataset.state !== 'ready';
    }
  });
}

async function fillFromFirefox(site) {
  const current = await activeSite();
  if (current.tab !== site.tab || current.origin !== site.origin) throw new Error('Active origin changed');
  const revision = pageRevision;
  const documentToken = await runLoginForm({ ...current, revision }, 'bind');
  if (typeof documentToken !== 'string' || documentToken.length !== 36) throw new Error('Document changed');
  const target = { ...current, documentToken, revision };
  const entry = await firefoxRequest('fill', target);
  if (['locked', 'unavailable', 'pair_required', 'upgrade_required'].includes(entry.code)) {
    showConnection(entry.code);
    return;
  }
  if (entry.code === 'no_login') {
    status.textContent = 'Für diese Website ist kein Login in Vault gespeichert.';
    return;
  }
  if (entry.origin !== site.origin || typeof entry.username !== 'string' || typeof entry.password !== 'string') {
    throw new Error('Unexpected login');
  }
  if (!await currentVaultSession(entry.session)) {
    clearLogin('Vault-Freigabe beendet.');
    return;
  }
  const result = await runLoginForm(target, 'fill', entry.username, entry.password);
  if (result === 'username') {
    status.textContent = 'Benutzername eingesetzt. Wähle beim Passwortschritt erneut „Login ausfüllen“.';
  } else if (result === 'both' || result === 'password') {
    status.textContent = 'Ausgefüllt. Prüfe die Felder und melde dich selbst an.';
  } else if (result === 'ambiguous' || result === 'occupied') {
    status.textContent = fillProblem(result);
  } else if (result === 'document-changed') {
    clearLogin('Die Seite hat gewechselt. Fordere den Login erneut an.');
  } else {
    await requireSameTab(target);
    manualFirefoxFill = { site: target, session: entry.session };
    showLogin(entry);
    status.textContent = fillProblem(result);
  }
}

async function currentVaultSession(expected) {
  if (typeof expected !== 'string') return false;
  const status = await firefoxRequest('status');
  return status.code === 'ready' && status.session === expected;
}

function clearLogin(message) {
  clearTimeout(loginTimer);
  manualFirefoxFill = undefined;
  username.value = '';
  password.value = '';
  password.type = 'password';
  document.querySelector('#reveal').textContent = 'Passwort anzeigen';
  document.querySelector('#login').hidden = true;
  if (firefox) form.hidden = false;
  status.textContent = message;
}

document.querySelector('#reveal').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  const show = password.type === 'password';
  if (show && firefox) {
    const pending = manualFirefoxFill;
    if (!pending) return;
    const ready = await currentVaultSession(pending.session).catch(() => false);
    if (pending !== manualFirefoxFill) return;
    if (!ready) {
      clearLogin('Vault-Freigabe beendet.');
      return;
    }
  }
  password.type = show ? 'text' : 'password';
  button.textContent = show ? 'Passwort verbergen' : 'Passwort anzeigen';
});

setup();
