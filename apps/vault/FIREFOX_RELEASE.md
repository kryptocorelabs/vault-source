# Firefox add-on signing

KryptoCore Vault Preview requires Firefox 140 or later and the Vault desktop
build for Windows with the Firefox pairing workflow. The extension ID is
`vault@kryptocorelabs`. The Windows native host uses the same ID.

## Submit the package

1. Submit the Firefox ZIP in the [Mozilla Add-ons Developer Hub](https://addons.mozilla.org/developers/addon/submit/distribution).
   Choose **On your own** to get a signed build for self-distribution.
   Select Firefox desktop when specifying supported applications.
2. Include the review notes below and give reviewers access to a current
   Windows Vault build with the pairing workflow and its setup instructions.
3. After Mozilla signs the package, download the signed XPI. In Firefox,
   remove the temporary copy and use **Add-ons and themes → Settings →
   Install Add-on From File** to install the XPI.

The signed extension and its pairing persist after a Firefox restart.
Use Firefox 0.1.15 with Vault 0.1.0-rc.2 for session-bound saving.
Existing v5 pairings from Vault RC.1 carry over to RC.2.
Self-distributed updates need their own distribution path.

## Version 0.1.15 release notes

The popup and website assistant refresh when logins are added or removed
in Vault. The assistant rechecks sign-in forms as they appear and retries
interrupted checks. Website permissions and the existing pairing stay in place.

## Version 0.1.14 release notes

Save offers and native save requests are bound to the unlocked Vault session.
Navigation and tab activation invalidate in-flight fill requests. Firefox
clears pending save data when its website authorization is revoked.

## Version 0.1.13 release notes

The Firefox popup gives the connection status, current website, and main
action a consistent layout. Website assistant settings are available in
an expandable section. This version works with the same Windows release
candidate and pairing as 0.1.12.

## Version 0.1.12 release notes

Vault and Firefox now communicate over an encrypted and authenticated local
channel. Pair once using a short-lived connection code generated in Vault.
Strict mode fills from the Firefox popup. Standard mode also offers direct
fill on individually enabled HTTPS sites. Vault locks when the Windows
session locks or the computer suspends.

## Notes for Mozilla reviewers

This extension is a companion to KryptoCore Vault for Windows. It ships
readable HTML and JavaScript and a compiled Rust WebAssembly module.
Provide the separate source archive for review. No account is required.
Please use synthetic credentials.

1. Open a Vault build that includes Firefox pairing and create or open a test
   vault. Save a synthetic login for an HTTPS page with a standard sign-in form.
2. In Vault select **Firefox → Verbindungscode erstellen**. Paste the code
   into the extension and select **Firefox verbinden**. The extension shows
   **Mit Vault verbunden**.
3. Open the saved site. In the extension click **Login ausfüllen** and check
   that the matching fields are filled. The extension never submits the form.
4. Lock Vault and try again. The extension should ask you to open or unlock
   Vault without filling the form.
5. Unlock Vault. Turn on detection for all HTTPS sites in the popup and grant
   Firefox's permission. Open a second HTTPS sign-in page. The neutral page
   button opens the extension popup. Global detection alone offers no direct
   fill or submission capture.
6. In the popup choose **Für diese Website einschalten**. On the page, click
   the yellow **Vault · Login anlegen** button. Verify that Vault opens a new
   editor with the address prefilled. Cancel it. On a test site you control,
   submit a standard sign-in form with synthetic credentials. Click
   **Vault · Login speichern?** and confirm **Speichern** in the Firefox popup.
7. Reopen the sign-in page and use **Ausfüllen** next to the green indicator.
   Verify that the fields are filled and that the form stays unsubmitted.
   In **Streng** mode, use the popup to fill and Vault to save new entries.

Opening the extension on a recognized sign-in form sends the active HTTPS
origin to Vault through the encrypted local channel. Filling retrieves
credentials for that exact origin. The extension
places them into matching fields on the site. Saving an entry sends the
form's credentials to the local desktop app only when the user chooses to save.
Pairing uses a one-time code as a pre-shared key. The helper relays encrypted
messages. Connection checks carry no tab data. Vault protects
the pairing key with Windows DPAPI. Firefox keeps a non-extractable Web Crypto
key in the extension database. The extension has no telemetry or cloud service.

Firefox Native Messaging and a user-scoped Windows named pipe carry encrypted
frames. The endpoints use Snow's Noise NNpsk0 with X25519, ChaChaPoly and
SHA-256 and create a fresh session per request. A filled page can read its
own field values.

Global detection uses an optional HTTPS host permission. It inspects form
structure without reading field values or contacting Vault. The site assistant
requires a separate opt-in for each exact HTTPS origin, including the port.
After an eligible form submission, the proposed login stays in browser session memory
for up to two minutes, until dismissed, or until the tab leaves the origin or
closes. The proposed credentials are sent to the desktop app only after the
user confirms in the browser popup. The extension stores enabled origins as
local preferences.

## Package from source

From the workspace root, add the `wasm32-unknown-unknown` Rust target and
run `./apps/vault/package-firefox.ps1` in PowerShell. It builds the locked
WebAssembly module, copies the extension files and license texts, and writes
the ZIP to `dist`. Run `web-ext lint --self-hosted --source-dir
dist/vault-firefox-amo-0.1.15`. The build script also writes SHA-256
checksums for the ZIP and the WebAssembly module.
The Chrome manifest and desktop binaries are separate from the Firefox package.
The current linter may report an [Android compatibility warning](https://github.com/mozilla/web-ext/issues/3561)
even though this package targets desktop Firefox.
