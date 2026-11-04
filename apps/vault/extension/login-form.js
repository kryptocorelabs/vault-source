function loginForm(origin, action, user, secret, submittedForm, documentToken) {
  if (location.origin !== origin || location.protocol !== 'https:') return documentToken ? 'document-changed' : false;
  if (action === 'bind') {
    if (!globalThis.vaultDocumentToken) {
      globalThis.vaultDocumentToken = crypto.randomUUID();
      addEventListener('pagehide', () => { delete globalThis.vaultDocumentToken; }, { once: true });
    }
    return globalThis.vaultDocumentToken;
  }
  if (documentToken && globalThis.vaultDocumentToken !== documentToken) return 'document-changed';
  const visible = (element) => element.getClientRects().length > 0 && !element.closest('[inert]') &&
    (element.checkVisibility?.({ visibilityProperty: true, opacityProperty: true }) ??
      element.ownerDocument.defaultView.getComputedStyle(element).visibility === 'visible');
  const writable = (field) => !field.matches(':disabled, [readonly]');
  const autocomplete = (field, name) => (field.getAttribute('autocomplete') ?? '').toLowerCase().split(/\s+/).includes(name);
  const safeAction = (element, attribute) => {
    const value = element.getAttribute(attribute) || element.ownerDocument.URL;
    try {
      return new URL(value, element.baseURI).origin === origin;
    } catch {
      return false;
    }
  };

  function usernameRank(field) {
    if (!['text', 'email', 'tel', 'number'].includes(field.type) || autocomplete(field, 'one-time-code')) return 0;
    if (autocomplete(field, 'username')) return 4;
    const hint = [field.name, field.id, field.placeholder, field.getAttribute('aria-label'),
      ...Array.from(field.labels ?? [], (label) => label.textContent)].join(' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_:.-]+/g, ' ');
    if (/\b(?:search|suche|otp|totp|mfa|2fa|captcha|token|passcode|verification|sicherheitscode)\b/i.test(hint)) return 0;
    if (/\b(?:user\s*(?:name|id)?|login|benutzername|anmeldename|kennung|kundennummer|account\s*id)\b/i.test(hint)) return 3;
    if (field.type === 'email' || /\b(?:e\s*mail|mail\s*address)\b/i.test(hint)) return 2;
    return field.type === 'text' ? 1 : 0;
  }

  const roots = [document];
  const groups = new Map();
  const focused = new Set();
  for (let active = document.activeElement; active && !focused.has(active);) {
    focused.add(active);
    active = active.shadowRoot?.activeElement ?? active.contentDocument?.activeElement;
  }
  for (const root of roots) {
    for (const element of root.querySelectorAll('*')) {
      if (element.shadowRoot) roots.push(element.shadowRoot);
      if ((element.localName === 'iframe' || element.localName === 'frame') && visible(element)) {
        const child = element.contentDocument;
        if (child && new URL(child.URL).origin === origin) roots.push(child);
      }
      if (element.localName !== 'input' || !visible(element)) continue;
      const group = element.form ?? element.closest('dialog, [role="dialog"], [role="form"]') ?? root;
      if (submittedForm && group !== submittedForm) continue;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(element);
    }
  }

  const matches = [];
  for (const [group, fields] of groups) {
    const passwords = fields.filter((field) => field.type === 'password' && !autocomplete(field, 'one-time-code'));
    if (passwords.length > 1 || passwords.some((field) => !writable(field) || autocomplete(field, 'new-password'))) continue;
    const pass = passwords[0];
    const form = pass?.form ?? (group.localName === 'form' ? group : null);
    const overrides = form ? [...form.getRootNode().querySelectorAll('[formaction], [formmethod]')]
      .filter((element) => element.form === form) : [];
    if (form && (!safeAction(form, 'action') || overrides.some((field) =>
      field.hasAttribute('formaction') && !safeAction(field, 'formaction')))) continue;
    const passwordIndex = pass ? fields.indexOf(pass) : fields.length;
    let login;
    let rank = 0;
    for (let index = passwordIndex - 1; index >= 0; index--) {
      const field = fields[index];
      const candidate = usernameRank(field);
      if (candidate > rank || (candidate && candidate === rank && focused.has(field))) {
        login = field;
        rank = candidate;
      }
    }
    if (!login && pass) login = fields.slice(passwordIndex + 1).find((field) => autocomplete(field, 'username'));
    if (pass && !form && rank === 1 && fields.slice(0, passwordIndex).filter(usernameRank).length > 1) continue;
    if (!pass) {
      const possible = fields.filter((field) => writable(field) && usernameRank(field) >= 3);
      login = possible.find((field) => focused.has(field)) ?? (possible.length === 1 ? possible[0] : undefined);
      if (!login) continue;
    }
    if (pass && !form && !login && !focused.has(pass) && !autocomplete(pass, 'current-password')) continue;
    if (pass && form) {
      // Native GET cannot serialize unnamed inputs in a JavaScript-managed form.
      const unnamed = !form.hasAttribute('method') && !pass.name && (!login || !login.name);
      if ((form.getAttribute('method')?.toLowerCase() !== 'post' && !unnamed) || overrides.some((field) =>
        field.hasAttribute('formmethod') && field.getAttribute('formmethod').toLowerCase() !== 'post')) continue;
    }
    matches.push({ login, pass, focused: focused.has(login) || focused.has(pass) });
  }

  const preferred = matches.filter((match) => match.focused);
  const passwordMatches = matches.filter((match) => match.pass);
  const choices = preferred.length ? preferred : passwordMatches.length ? passwordMatches : matches;
  if (choices.length > 1) return action === 'inspect' ? { ambiguous: true } : action === 'fill' ? 'ambiguous' : false;
  if (!choices.length) return false;
  const { login, pass } = choices[0];
  if (action === 'inspect') return { capturable: Boolean(pass && login), hasPassword: Boolean(pass) };
  if (action === 'capture') {
    return pass && login && login.value.trim() && pass.value
      ? { username: login.value, password: pass.value } : false;
  }
  if ((pass?.value && pass.value !== secret) || (login && (!writable(login) || login.value) && login.value !== user)) {
    return 'occupied';
  }
  if (login?.type === 'number' && user && !/^\d+$/.test(user)) return false;

  const changed = [[login, user], [pass, secret]].filter(([field, value]) => field && writable(field) && field.value !== value);
  for (const [field, value] of changed) {
    const view = field.ownerDocument.defaultView;
    Object.getOwnPropertyDescriptor(view.HTMLInputElement.prototype, 'value').set.call(field, value);
  }
  for (const [field] of changed) {
    const Event = field.ownerDocument.defaultView.Event;
    field.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return pass ? (login ? 'both' : 'password') : 'username';
}
