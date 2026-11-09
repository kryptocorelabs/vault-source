# Recovery re-key review, 8 November 2026

This is the historical maintainer review of the recovery reset change. Use the
[current compatibility matrix and key lifecycle](FORMAT-LIFECYCLE.md) to identify
which public downloads include the fix.

## Confirmed finding

**High, conditional on access to an earlier vault and its unlocking secret:**
`reset_password` previously replaced the password slot but reused the seed and
recovery slot. A key recovered from a pre-reset snapshot could therefore decrypt
the updated payload despite rejection of the old password by the new slot.
This is not a break of XChaCha20-Poly1305 or Argon2id.

Synthetic reproduction in `modules/vault-format/src/container.rs`:

1. Create a KCV2 vault and save test entries. Retain a copy and its password.
2. Open the copy and recover its seed and derived payload key.
3. Reset the active file using its emergency sheet and a different password.
4. Decrypt the updated payload directly using the retained key, public nonce
   and complete header AAD. This succeeded before the fix, while opening the
   updated password slot using the old password correctly failed.

The regression test was run against the original implementation and failed at
the explicit old-key rejection assertion. It covers the updated payload and a
subsequent ordinary save, not only rejection by the password slot.

## Change and compatibility

After authenticating recovery access and parsing entries, reset now generates
a new random 32-byte seed, creates both wrapping slots with fresh salts/nonces
and encrypts the payload under the new derived key. The emergency-sheet secret
stays valid. The existing atomic replacement path and zeroizing owners remain.
KCV1/KCV2 layout, Argon2id parameters, APIs and browser pairings are unchanged.
No dependency was added. Read-only Rescue recovery continues to leave input intact.

The UI explains the limits before reset, warns about retained backup credentials
and clears recovery/password widgets after the dialog closes. Clearing widgets
reduces exposure but cannot guarantee erasure of Python/Qt-managed copies.

## Added regression coverage

- An old seed/key cannot decrypt the post-reset file or subsequent edits.
- The old password cannot open or overwrite the updated file; failed saving
  leaves its bytes unchanged. The new password and existing recovery secret work.
- Old snapshots remain independently readable with their original credentials.
- Ordinary saves preserve the seed/slots and refresh the payload nonce.
- Renewing recovery rotates the seed and rejects the former recovery secret.
- Repeated resets keep recovery working while rotating each new seed.
- Reset rejects damaged and legacy files without replacing them; existing tests
  also cover wrong secrets, invalid JSON, truncation and oversize limits.
- Desktop workflow exercises recovery of a disposable backup, unchanged original
  copies, the user-visible warnings and cleanup of password/recovery fields.

## Limits at the time of review

The reviewed KCV2 profile had no authenticated revision. Old snapshots kept
their matching credentials, and Python/Qt/JSON could retain secret copies.
The original Argon2id payload derivation remains part of the KCV2 compatibility
profile. See the [current threat model](THREAT_MODEL.md) and
[KCV4 payload profile](../../modules/vault-format/KCV4.md).

## Local validation

On Windows x64, all 10 shared-format tests, 16 Vault/channel/Rescue Rust tests,
six mocked Firefox session tests and the Qt desktop workflow passed. Recovery
cancel left the selected file unchanged and cleared its fields; successful
recovery preserved the original backup and cleared the accepted inputs too.
The recovery dialog was rendered and visually inspected.

A separate compatibility run used the unmodified previous container implementation
(SHA-256 `38fbb94338eba2484f6943820146bb0912101a39f3305a32852818ada1b29b87`)
as a legacy reader/writer. It opened a hardened reset by password and recovery;
old and new implementations could read subsequent saves from each other.
This checks KCV2 interoperability, not deployment of a patched release.

The Mozilla-signed Firefox 0.1.16 package remains byte-for-byte unchanged. Its
existing signing verification is separate from this review; live browser pairing
was not retested here. The local portable build's exact digest and source commit
are recorded in its build manifest; clean-machine validation remains pending.

Run the targeted checks with:

```sh
cargo test --locked --release -p kryptocore-vault-format -p kryptocore-vault -p vault-firefox-channel -- --test-threads=1
node --test apps/vault/tests/firefox-security.test.cjs
python apps/vault/tests/desktop-workflow.py
```
