(() => {
  if (globalThis.vaultPageInstalled || window.top !== window || location.protocol !== 'https:') return;
  globalThis.vaultPageInstalled = true;
  const origin = location.origin;
  const call = (action, data) => browser.runtime.sendMessage({ channel: 'vault-assist', action, ...data });
  const host = document.createElement('div');
  host.style.setProperty('all', 'initial', 'important');
  host.style.setProperty('position', 'fixed', 'important');
  host.style.setProperty('inset', 'auto 16px 16px auto', 'important');
  host.style.setProperty('z-index', '2147483647', 'important');
  const shadow = host.attachShadow({ mode: 'closed' });
  const style = document.createElement('style');
  style.textContent = `
    .actions { display: flex; gap: 5px; }
    [hidden] { display: none !important; }
    button {
      box-sizing: border-box; display: flex; align-items: center; gap: 8px;
      max-width: calc(100vw - 32px); min-height: 36px; padding: 6px 12px;
      font: 600 13px/1.35 system-ui, sans-serif; cursor: pointer; text-align: left;
      border: 1px solid #30454e; border-radius: 11px; color: #e4edf3;
      background: #1b2832; box-shadow: 0 3px 15px #07101966;
    }
    button[data-state=found] { border-color: #71c5b3; color: #b6f5e6; background: #193b3b; }
    button[data-state=offer], button[data-state=missing] {
      border-color: #e5b571; color: #ffe3b9; background: #3c3027;
    }
    button:focus-visible { outline: 2px solid #80e5cf; outline-offset: 2px; }
    svg { flex: none; width: 18px; height: 18px; }
  `;
  const button = document.createElement('button');
  button.type = 'button';
  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('viewBox', '0 0 20 20');
  icon.setAttribute('aria-hidden', 'true');
  const lock = document.createElementNS(icon.namespaceURI, 'path');
  lock.setAttribute('d', 'M6 9V6a4 4 0 0 1 8 0v3M4 9h12v9H4zM10 12v3');
  lock.setAttribute('fill', 'none');
  lock.setAttribute('stroke', 'currentColor');
  lock.setAttribute('stroke-width', '1.6');
  lock.setAttribute('stroke-linejoin', 'round');
  icon.append(lock);
  const caption = document.createElement('span');
  button.append(icon, caption);
  const fill = document.createElement('button');
  fill.type = 'button';
  fill.dataset.state = 'found';
  fill.textContent = '↳ Ausfüllen';
  fill.setAttribute('aria-label', 'Gespeicherten Login direkt ausfüllen');
  const actions = document.createElement('div');
  actions.className = 'actions';
  actions.append(button, fill);
  shadow.append(style, actions);

  let enabled = false;
  let capture = false;
  let captureSession;
  let previousDetection;
  let running = false;
  let rescan;
  let timer;
  let configuration = 0;
  let pageGeneration = 0;
  addEventListener('pagehide', () => { pageGeneration++; });

  function render(state, directFill = false) {
    fill.hidden = !directFill;
    if (!state || !enabled) {
      host.remove();
      return;
    }
    button.dataset.state = state;
    caption.textContent = {
      offer: 'Vault · Login speichern?',
      found: 'Vault · Login verfügbar',
      missing: 'Vault · Login anlegen',
      form: 'Vault · Anmeldefeld erkannt',
    }[state];
    if (!host.isConnected) document.documentElement.append(host);
  }

  async function scan(force = false) {
    if (!enabled || document.hidden) return;
    if (running) {
      rescan = force || rescan === true;
      return;
    }
    const detected = Boolean(loginForm(origin, 'inspect')?.hasPassword);
    if (!force && detected === previousDetection && (host.isConnected || !detected)) return;
    const revision = configuration;
    const generation = pageGeneration;
    running = true;
    try {
      const reply = await call('scan', { detected }).catch(() => null);
      if (revision !== configuration || generation !== pageGeneration) return;
      const valid = reply && typeof reply.state === 'string';
      previousDetection = valid ? detected : undefined;
      capture = valid && reply.capture === true;
      captureSession = capture ? reply.captureSession : undefined;
      render(valid ? reply.state : '', valid && reply.directFill === true);
    } finally {
      running = false;
      if (rescan !== undefined) {
        const forceNext = rescan;
        rescan = undefined;
        void scan(forceNext);
      }
    }
  }

  function scheduleScan() {
    if (timer !== undefined) return;
    timer = setTimeout(() => {
      timer = undefined;
      void scan();
    }, 350);
  }

  const observer = new MutationObserver(scheduleScan);

  async function configure() {
    const revision = ++configuration;
    const allowed = await call('enabled').catch(() => false) === true;
    if (revision !== configuration) return;
    enabled = allowed;
    if (!enabled) {
      capture = false;
      captureSession = undefined;
      previousDetection = undefined;
      observer.disconnect();
      render();
      return;
    }
    observer.observe(document.documentElement, {
      childList: true, subtree: true, attributes: true,
      attributeFilter: ['type', 'hidden', 'style', 'class', 'autocomplete', 'disabled', 'readonly',
        'inert', 'method', 'action', 'name', 'form', 'formaction', 'formmethod'],
    });
    await scan(true);
  }

  function intentionalClick(event) {
    if (!event.isTrusted || !enabled || document.hidden || !document.hasFocus() ||
        host.parentElement !== document.documentElement || !host.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    const rect = host.getBoundingClientRect();
    const style = getComputedStyle(host);
    if (style.position !== 'fixed' || Number(style.opacity) !== 1 ||
        Math.abs(rect.right - document.documentElement.clientWidth + 16) > 2 ||
        Math.abs(rect.bottom - document.documentElement.clientHeight + 16) > 2) return false;
    return event.detail === 0
      ? shadow.activeElement === event.currentTarget
      : document.elementFromPoint(event.clientX, event.clientY) === host;
  }

  async function openPopup() {
    try {
      if (await call('open')) return;
    } catch {
      // The toolbar shortcut also works when Firefox cannot open the popup here.
    }
    caption.textContent = 'Vault öffnen · Alt+Umschalt+K';
  }

  button.addEventListener('click', async (event) => {
    if (!intentionalClick(event)) return;
    if (button.dataset.state === 'missing') {
      const reply = await call('new-login').catch(() => null);
      if (reply?.code === 'opening') {
        caption.textContent = 'Neuer Login · in Vault';
        return;
      }
      if (reply?.code === 'busy') {
        caption.textContent = 'Vault · Dialog bereits offen';
        return;
      }
    }
    await openPopup();
  });

  fill.addEventListener('click', async (event) => {
    if (!intentionalClick(event) || fill.hidden || fill.disabled ||
        !loginForm(origin, 'inspect')?.hasPassword) return;
    const generation = pageGeneration;
    fill.disabled = true;
    try {
      const entry = await call('fill').catch(() => null);
      if (generation !== pageGeneration || !document.hasFocus() || document.hidden) return;
      if (entry?.origin !== origin || typeof entry.username !== 'string' || typeof entry.password !== 'string') {
        caption.textContent = entry?.code === 'locked' ? 'Vault · entsperren' : 'Vault · bitte erneut prüfen';
        return;
      }
      const result = loginForm(origin, 'fill', entry.username, entry.password);
      caption.textContent = ['both', 'password'].includes(result)
        ? 'Vault · ausgefüllt' : 'Vault · Formular prüfen';
    } finally {
      fill.disabled = false;
    }
  });

  document.addEventListener('submit', (event) => {
    if (!enabled || !capture || !event.isTrusted || !navigator.userActivation.isActive ||
        typeof captureSession !== 'string' || event.target?.localName !== 'form') return;
    const credentials = loginForm(origin, 'capture', '', '', event.target);
    if (!credentials) return;
    capture = false;
    void call('submit', { credentials, session: captureSession }).then(() => scan(true)).catch(() => {});
  }, true);

  browser.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && (Object.hasOwn(changes, 'assist:' + origin) ||
        Object.hasOwn(changes, 'assist-all'))) void configure();
  });
  document.addEventListener('focusin', scheduleScan);
  document.addEventListener('load', event => {
    if (['iframe', 'frame'].includes(event.target?.localName)) scheduleScan();
  }, true);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pageGeneration++;
    else void configure();
  });
  window.addEventListener('pageshow', () => void configure());
  window.addEventListener('focus', () => void scan(true));
  setInterval(() => void scan(true), 5_000);
  void configure();
})();
