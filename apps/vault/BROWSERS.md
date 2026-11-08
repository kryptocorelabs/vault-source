# Browser support

## Available implementation

Firefox 140+ is the implemented browser companion. Package it with
`manifest.firefox.json` through `package-firefox.ps1`; the packaging script
includes `popup.css`. Existing pairings and the local encrypted channel are
unchanged by the interface update. Global website access remains optional.
The Mozilla-signed 0.1.16 XPI supports normal persistent installation. The
unsigned ZIP remains a development/reviewer artifact. See the public
[Firefox installation guide](https://github.com/kryptocorelabs/vault/blob/main/FIREFOX.md).

The popup's HTML, CSS, form recognition and user-facing states can be shared
with future browser ports. Styling lives in `extension/popup.css`; it does not
depend on Firefox APIs. Browser integration still uses Firefox-specific scripts
and is not presented as working Chromium support.

## Next: Chrome and Edge

1. Add an explicit Chromium Manifest V3 entry point and background service
   worker. Keep browser API differences behind a small adapter rather than
   duplicating form matching and UI logic.
2. Provision a separate native messaging registration with an exact allowlist
   of the released extension IDs. Firefox IDs and pairings must not silently
   authorize a second browser.
3. Preserve explicit pairing, session invalidation, top-frame and exact-origin
   checks. Test service-worker suspension, browser restarts and permissions
   being revoked while a request is in flight.
4. Produce store-specific packages, review notes, notices and hashes, and run
   the same negative tests before claiming support. Test actual Chrome and Edge
   on Windows in addition to mocked APIs.

The old `extension/manifest.json` is a historical loopback prototype, not a
supported Chrome/Edge build. Do not distribute it or infer compatibility from
it. Safari requires a separate packaging and native-host investigation. Mobile
browsers are not currently supported.

No browser port should require broad website permissions by default, bypass
Vault's lock or share passwords through an unencrypted HTTP fallback. A shared
design is only the first step; compatibility requires its own security review
and integration tests.

Implementation references:
[MDN cross-browser extensions](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Build_a_cross_browser_extension),
[Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).
