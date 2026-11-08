# KryptoCore Vault 0.1.0-rc.2

Local password manager with a cross-platform Qt desktop interface, Rust CLI and Firefox
companion. Vault and its extension are open source under the workspace's MIT
license. Dependencies retain their own terms. This remains a development preview;
use synthetic data and retain backups. Independent security audit is pending.

Software defects, device failure and lost credentials can cause data loss.
Read the [usage notes](USAGE.md), [security boundaries](SECURITY.md) and
[third-party notices](../../THIRD_PARTY_NOTICES.md). Statutory rights and
applicable legal responsibilities are not displaced by these notices.

Testing to date has been carried out by the KryptoCoreLabs maintainers, locally
and through automated CI. No independent security audit has been completed.
We welcome community testing, code reviews and scrutiny of our security
assumptions. Please use synthetic data and report suspected vulnerabilities
privately through the project's security-reporting channel.

The unreleased [recovery hardening](RECOVERY-HARDENING.md) rotates the payload
seed on password reset. Existing published binaries may retain the old behavior.
See [Vault's threat model](THREAT_MODEL.md) for snapshot, rollback and memory limits.

See [desktop platforms](PLATFORMS.md) for native Linux and macOS build/test
instructions and limitations. Firefox pairing remains Windows-only; no alternate
plaintext transport or key store is used on other platforms.

[Security in 30 seconds](https://github.com/kryptocorelabs/kryptocore/blob/main/SECURITY-IN-BRIEF.md) · [Rescue-first guide](https://github.com/kryptocorelabs/kryptocore/blob/main/RESCUE-FIRST.md) · [Verify a download](https://github.com/kryptocorelabs/kryptocore/blob/main/VERIFY-DOWNLOADS.md)

## End-user builds and development

The [single-file Windows build](WINDOWS-ONEFILE.md) bundles Python, Qt and the
Rust components. Users of that build do not install the development environment.
Historical public previews may still have the older setup workflow: use the
instructions for the exact artifact you downloaded.

For source development on Windows, install Rust and its MSVC build prerequisites,
Python 3.13 x64, and the pinned GUI requirements. From the workspace root:

```powershell
cargo build --locked --release -p kryptocore-vault -p vault-firefox-channel
python -m pip install -r apps/vault/desktop/requirements.txt
python apps/vault/desktop/vault.pyw
```

See [CI and build consistency](CI.md) for tests and exact toolchain details.
The [shared format reader](../../modules/vault-format/README.md) supports
KCV1/KCV2; format/API compatibility changes must be explicit and tested.

## Everyday use

Create or open a vault, search logins, edit or delete entries and generate
passwords. **Sperren**, `Ctrl+L`, inactivity or the applicable Windows session
events end the unlocked session. Firefox cannot request new credentials until
Vault is unlocked again.

New vaults use a vault password/passphrase. The local zxcvbn estimate is guidance,
not a security guarantee. Longer passphrases are accepted; inputs above 72
characters are outside the estimator's range. Password fields provide deliberate
reveal/hide controls, including generated passwords.

Settings offer two policies using the same vault encryption and recovery:

- **Alltag:** remembers the most recent vault path, asks for its password at
  startup and locks after five minutes without activity in Vault. Supports
  deliberate browser save offers.
- **Streng:** does not retain a recent path, locks after one minute and saves
  new logins through the desktop editor. Browser filling uses the popup.

The optional Windows glass effect changes the background only. Settings and
recovery dialogs scroll on smaller displays; the compact start tiles follow
the shared Messenger palette. UI language is separate from documentation language.

## Firefox

The [Mozilla-signed 0.1.16 XPI](https://github.com/kryptocorelabs/vault/releases/tag/firefox-v0.1.16)
is installed persistently through Firefox `about:addons` → gear menu →
Install Add-on From File. Requires Firefox 140+ and Vault's v5 pairing support.
See [signing and verification](FIREFOX_RELEASE.md) for the exact test scope.

Unlock Vault, create a connection code under **Firefox**, then paste it into
the trusted extension popup once. The code expires after two minutes and is
consumed on successful pairing. Existing compatible v5 pairings carry over
when updating; **Firefox trennen** revokes the pairing.

The popup offers matching credentials for the current HTTPS origin. Use
**Login ausfüllen**, inspect the fields and submit the form yourself. On split
username/password pages, invoke filling on the appropriate step. Ambiguous
forms can need a focused field or manual transfer. Unsupported or unsafe forms
are rejected rather than filled speculatively.

Global HTTPS form detection is optional and initially disabled. Site assistance
requires a separate opt-in for the exact origin, including its port. It can
offer page actions for filling or opening a new Vault entry. Eligible save offers
require explicit confirmation; their session and navigation checks remain in
force. `Alt+Shift+K` opens the extension popup.

Vault and Firefox authenticate/encrypt each request with a fresh Noise session.
The helper relays ciphertext. Windows DPAPI protects Vault's pairing key; Firefox
stores its key through Web Crypto. The browser, unlocked processes and Windows
account are trust boundaries. A page can read credentials inserted into its own
fields. Signing is not a claim of absolute security or an independent audit.

Chrome and Edge are planned separately. The old loopback prototype manifest is
not a supported browser port. See [browser support](BROWSERS.md).

## Backups and recovery

In an unlocked vault choose **Einstellungen → Sicherung erstellen** to create a
checked encrypted copy. Existing destinations are protected. Keep dated backups
on separate storage and test an additional copy before relying on recovery.

Creating a vault includes a separate emergency-sheet step. Save its PDF and keep
it protected, retrievable and separate from the vault file. Anyone holding both
can use the recovery credential. Recovery does not repair missing or corrupted
ciphertext. Loss of every valid credential can make the contents inaccessible.

An unlocked vault can configure/renew the sheet under **Einstellungen →
Notfallblatt einrichten oder erneuern**. Old vault copies keep their old access
credentials. Earlier applications without KCV2 support cannot read that format.
YubiKey integration and a dedicated password blocklist remain future work.

## CLI

```sh
cargo run --locked --release -p kryptocore-vault -- init demo.kcv
cargo run --locked --release -p kryptocore-vault -- add demo.kcv https://example.invalid
cargo run --locked --release -p kryptocore-vault -- list demo.kcv
```

The terminal prompts for credentials with input hidden. `list` shows websites
and usernames; `remove demo.kcv https://example.invalid` removes that entry.
Each command opens the vault for its own operation. Use only disposable test data.
