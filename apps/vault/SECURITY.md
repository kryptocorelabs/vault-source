# Vault security

Vault 0.1.0-rc.2 and Firefox 0.1.14 or later use the encrypted v5 channel.
See the [usage notes](USAGE.md) for recovery instructions.

Testing to date has been carried out by the KryptoCoreLabs maintainers, locally
and through automated CI. No independent security audit has been completed.
We welcome community testing, code reviews and scrutiny of our security
assumptions. Please use synthetic data and report suspected vulnerabilities
privately through the project's security-reporting channel.

## Password reset, snapshots and memory

Resetting a password does not revoke old vault copies. Anyone with an old file
and its matching password or emergency sheet can still read that snapshot.
If credentials were exposed, change them at the corresponding services too.

The unreleased recovery hardening rotates the random 32-byte payload seed,
rewraps it in both slots and re-encrypts the authenticated payload. The existing
emergency sheet remains valid. A seed recovered from a pre-reset copy cannot
decrypt the updated file or its later edits. Earlier builds only rewrote the
password slot and retained the seed; their resets did not provide that boundary.
Use the hardening change described in [the review](RECOVERY-HARDENING.md);
the version label alone does not establish that a build includes it.

Ordinary saves retain the seed. A copy and its matching credentials therefore
remain sensitive even after editing the active vault. The current emergency
sheet can also unlock later files until it is renewed. If it may be exposed,
renew it from the unlocked vault and protect the replacement separately.

KCV1/KCV2 do not detect whole-file rollback. The unreleased, opt-in
[KCV3 epoch profile](EPOCHS.md) adds a best-effort local high-water check.
Without retained trusted local state, an older, authentic file can still open.
There is no trusted monotonic counter or external freshness record. AEAD detects
modification, not rollback of an entire valid file. Dated, separately stored
backups and checking expected entries help recovery but do not prevent rollback.

Rust uses zeroizing owners for session passwords, seeds, derived keys, decrypted
buffers and login fields where implemented. Python strings, JSON serialization
and Qt widgets can create additional managed copies. Clearing a field or locking
Vault does not guarantee erasure of all copies, swap or crash dumps. Do not rely
on memory secrecy against a compromised process, user account or operating system.
See the [Vault threat model](THREAT_MODEL.md) for trust boundaries.

## Plaintext migration and local status

The development [JSON migration workflow](MIGRATION.md) deliberately exports all
login secrets to plaintext after explicit confirmation. Protect that file and
its storage; deletion cannot guarantee erasure from snapshots or backups.
Import validates the input and atomically creates a new KCV2 vault with fresh
key material and a new GUI-generated emergency credential. It does not revoke
old copies or rotate passwords at external services. The preview fingerprint
detects an intervening file edit; it does not authenticate an export's sender.

Vault status reports authenticated format/entry facts and untrusted local dates.
Backup timestamps record successful GUI copies at a path, not continued existence
or a restore test. A recovery slot does not prove that the user holds its matching
emergency sheet. These indicators are not a security certification.

## Firefox channel

The Windows app and add-on use the same pinned Snow implementation of
`Noise_NNpsk0_25519_ChaChaPoly_SHA256`. Vault displays a random one-time
pairing code. Both endpoints use it as a pre-shared key for an encrypted
session that provisions a separate long-term key. Pairing and regular requests
use distinct Noise prologues. Each request uses fresh ephemeral keys. The
native host relays framed ciphertext over a user-scoped named pipe.
Existing v5 pairings carry over. Session-bound saving requires Firefox
0.1.14 or later and Vault 0.1.0-rc.2.

The active HTTPS origin and operation are inside the encrypted request.
The add-on checks the active tab and document before filling and checks that
the same unlocked vault session remains active. Strict mode requires the
browser popup. The desktop locks on session lock, disconnect, and suspend.
Firefox checks the session again before releasing a fill result. The native
endpoint rejects save requests from expired or different vault sessions.

This channel protects against passive observation and a relay impersonator
without the pairing secret. The pairing code must be copied into the trusted
extension UI. The extension, Vault processes, and Windows account can access
plaintext while in use. A page can read the values inserted into its fields.
An independent review of the integration and release artifacts is pending.

## Report a vulnerability

Use **Security → Report a vulnerability** on the
[Vault repository](https://github.com/kryptocorelabs/vault/security)
when GitHub private reporting is available. If the option is unavailable,
open an issue asking the maintainers for a private contact. Keep technical
details for the private conversation.

Include the Vault and add-on versions, operating system, browser version
if relevant, possible impact, and steps to reproduce with synthetic data.
Leave real vault files, passwords, and emergency sheets out of the report.
For an ordinary support request about an opening error, share the error
message and versions and remove any private details.

## How reports are handled

Maintainers aim to acknowledge reports privately, reproduce issues, and
assess affected versions. We coordinate disclosure with the reporter and
document affected versions, fixes, and available mitigations when a public
advisory is appropriate.
