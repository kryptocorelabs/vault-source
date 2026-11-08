# Vault security

Vault 0.1.0-rc.2 and Firefox 0.1.14 or later use the encrypted v5 channel.
See the [usage notes](USAGE.md) for recovery instructions.

Testing to date has been carried out by the KryptoCoreLabs maintainers, locally
and through automated CI. No independent security audit has been completed.
We welcome community testing, code reviews and scrutiny of our security
assumptions. Please use synthetic data and report suspected vulnerabilities
privately through the project's security-reporting channel.

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
