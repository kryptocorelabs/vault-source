# Vault threat model

Vault is a development preview. Tests are maintained by KryptoCoreLabs;
no independent security audit has been completed. This document describes
boundaries, not a guarantee of confidentiality, availability or recovery.

## Assets and trust

Assets include stored logins, the vault password, emergency-sheet secret,
payload seed and key, browser pairing secrets, unlocked sessions and backups.
The Rust parser/worker, Python/Qt UI, Firefox extension and native channel
are separate boundaries. The OS, random source, dependencies and distributed
binaries must be trustworthy. A filled website receives its login plaintext.
JSON migration deliberately creates a plaintext copy on selected storage. The
Rust worker validates versioned/Rescue JSON, bounds input and rejects duplicate
websites before creating a fresh vault. The source/export directories and OS
remain trusted. A preview digest detects changed bytes, not a trusted sender.
Local backup receipts and filesystem dates are informational, editable state.

## Firefox release dependencies

| Dependency | Why it is trusted | Possible alternative |
| --- | --- | --- |
| [Mozilla Add-ons signing](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/) | Stock Firefox requires a Mozilla signature for persistent release installs. An AMO outage or review delay can block new releases. | Use the AMO API to replace manual submission, or list the add-on on AMO to change distribution. Both routes still use Mozilla signing. |
| Release Firefox and GeckoDriver | Firefox enforces signature trust and checks persistent installation. GeckoDriver drives a disposable profile for the release check. | Verify with the same release Firefox in a disposable profile through a manual test. Repeat unsigned and modified-package rejection and restart checks. |
| GitHub Actions artifact attestation | Binds the unsigned submission ZIP to the build workflow and source. | An independently operated builder could attest the same artifact. The Firefox signature check still applies to the returned XPI. |

The signing hand-off takes the exact unsigned submission ZIP and returns an
XPI. The AMO adapter checks payload equivalence and the expected add-on ID and
version. Firefox establishes trust in the browser signature separately. See the
[release verification procedure](FIREFOX_RELEASE.md#signing-hand-off-and-release-verification).

## Attacker capabilities and limits

| Scenario | Protection and remaining responsibility |
| --- | --- |
| An attacker steals a locked vault | Password/recovery slots wrap a random seed with Argon2id-derived keys; XChaCha20-Poly1305 authenticates the slots and payload. Weak passwords remain subject to offline guessing. |
| An attacker modifies header, nonce, ciphertext or tag | Authentication fails. Size limits bound input; failed validation must not replace the source. |
| An attacker has an earlier copy and its password | That snapshot remains readable. Earlier reset implementations also retained its payload seed. The unreleased recovery hardening rotates the seed, preventing the old seed from opening the updated file. It cannot revoke old plaintext. |
| A recovery secret is exposed | Password reset preserves that secret. Renew the emergency sheet from the unlocked vault if it may be exposed. Old copies still retain old access paths. |
| An attacker restores or substitutes an authentic snapshot | KCV1/KCV2 still authenticate older files. Optional KCV3 records the counter and fingerprint of authenticated bytes locally. It rejects lower counters and different snapshots at a recorded counter. Resetting the history with the file, first use on another device and unseen higher-counter forks remain outside this check. |
| A local attacker reads UI/process memory | Rust clears selected owned buffers, including the serialized desktop request before processing. The worker still holds the vault password while unlocked. Python/Qt, buffered I/O, swap and crash dumps may retain copies. Locking ends the worker session and browser access. |
| A relay or website requests browser access | The v5 encrypted channel, paired secret, origin/tab/frame/session checks and lock invalidation enforce their documented scope. A compromised extension, app or OS is outside that scope. |
| Credentials were already filled, exported or copied | Vault cannot retract plaintext or reset the corresponding website accounts. The user must rotate affected service credentials. |
| A normal password change is made without re-keying | For KCV2/KCV3 only password wrapping changes; the seed and recovery access remain. An old extracted seed still works against current payloads. Explicit re-keying replaces the seed and, in the GUI, recovery credential; it cannot revoke old copies. |
| An attacker replaces a file and its recorded hash | SHA-256 comparison needs a separately trusted baseline. It is not sender authentication, a signature or malware detection. |
| An export is stolen or imported from an untrusted sender | JSON has no encryption or origin authentication. It exposes every transferred login. A fresh vault seed protects future ciphertext, not this plaintext or the sender's claims. |

## Persistence and recovery

Normal saves retain the seed and choose a fresh payload nonce. Recovery reset
in the hardened implementation rotates the seed and both wrapping slots without
changing KCV2 interpretation. Existing readers still open the resulting file.
Recovering through older software may retain the seed again; do not infer the
hardening from the filename or RC.2 version string alone.

Authentication and record parsing precede replacement. An in-directory temporary
file is synced before persistence; this does not promise survival of every power
failure, filesystem defect or concurrent external writer. Protect independent,
dated backups and test recovery on a disposable copy. Authenticity is not a
rollback detector, identity proof or malware scan.

## Further hardening

- For shorter password lifetime, evaluate a file-scoped unlock handle in the
  Rust worker. Verify the current wrapping slot and authenticated revision
  before using it. Password changes and slot renewal still need fresh
  authorization. Test replacement while unlocked, re-key, lock and KCV1
  compatibility before switching session storage.
- For side-channel review, start at fixed-size key and token checks and
  authorization paths observable over the browser bridge. Retest response
  behavior on compiled builds. Argon2id uses some data-dependent memory
  accesses by design. Track timing measurements separately from functional
  test results.
- For an optional hardware slot, evaluate CTAP2 `hmac-secret` with per-vault
  context, token verification, a spare token and independent paper recovery.
  The authenticator retains its internal secret. The derived secret and
  decrypted records still need protection in the application. A hardware
  requirement must be reflected in every normal unlock route. Test loss,
  replacement and offline recovery before adopting a format or policy.

See [security policy](SECURITY.md), [usage](USAGE.md),
[recovery hardening](RECOVERY-HARDENING.md) and the
[Core threat model](https://github.com/kryptocorelabs/kryptocore/blob/main/THREAT_MODEL.md).
