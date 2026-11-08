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

## Attacker capabilities and limits

| Scenario | Protection and remaining responsibility |
| --- | --- |
| An attacker steals a locked vault | Password/recovery slots wrap a random seed with Argon2id-derived keys; XChaCha20-Poly1305 authenticates the slots and payload. Weak passwords remain subject to offline guessing. |
| An attacker modifies header, nonce, ciphertext or tag | Authentication fails. Size limits bound input; failed validation must not replace the source. |
| An attacker has an earlier copy and its password | That snapshot remains readable. Earlier reset implementations also retained its payload seed. The unreleased recovery hardening rotates the seed, preventing the old seed from opening the updated file. It cannot revoke old plaintext. |
| A recovery secret is exposed | Password reset preserves that secret. Renew the emergency sheet from the unlocked vault if it may be exposed. Old copies still retain old access paths. |
| An attacker restores an older authentic file | KCV1/KCV2 still authenticate older files. Optional KCV3 compares an authenticated counter with separately retained local state; resetting that state, first use on another device and equal-epoch forks remain outside its protection. Vault has no trusted external freshness state or rollback detector. AAD and signatures alone do not prove the newest file was selected. |
| A local attacker reads UI/process memory | Rust clears selected owned buffers; Python/Qt/JSON copies, swap and crash dumps may persist. Locking stops access through the app but cannot guarantee forensic erasure. |
| A relay or website requests browser access | The v5 encrypted channel, paired secret, origin/tab/frame/session checks and lock invalidation enforce their documented scope. A compromised extension, app or OS is outside that scope. |
| Credentials were already filled, exported or copied | Vault cannot retract plaintext or reset the corresponding website accounts. The user must rotate affected service credentials. |

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

See [security policy](SECURITY.md), [usage](USAGE.md),
[recovery hardening](RECOVERY-HARDENING.md) and the
[Core threat model](https://github.com/kryptocorelabs/kryptocore/blob/main/THREAT_MODEL.md).
