# Shared Vault format implementation

Internal application-format crate for Vault and Rescue. This is separate from
the minimal cryptographic Core. KCV1/KCV2 bytes, KDF parameters, slot roles,
associated data and validation are unchanged.

Vault and Rescue share this implementation. Rescue pins an exact public
revision of this crate. Vault's current desktop creates [KCV4](KCV4.md) files
with the local revision check and a random payload key.

The existing `apps/vault/src/container.rs` implementation and its tests
were moved here. Vault re-exports this API and uses the same zeroizing Login
schema. Rescue calls `open` or the new read-only `open_with_recovery`; it never
calls `reset_password`, `save` or a migration routine on an input file.

```sh
cargo test --locked --release -p kryptocore-vault-format
```

This crate is maintained with the open-source application workspaces. It is not a new
public encryption primitive or a replacement format. No general recovery key,
back door or bypass is provided.

## Revision profiles

[KCV3](KCV3.md) is the earlier epoch profile with authenticated ID/epoch and
caller-supplied freshness minima. KCV4 uses the same revision checks. Rescue
can authenticate a copy for recovery without claiming backup freshness.

`open_with_metadata` returns format and recovery facts from the same authenticated
bytes as the plaintext. The current desktop uses `create_with_recovery_v4` for
new vaults and imports. `create_with_recovery` serves KCV2 compatibility. Both
create a fresh seed and slots, using a new destination. JSON transfer validation
and the UI live in Vault. [Format lifecycle and writer policy](../../apps/vault/FORMAT-LIFECYCLE.md)

`change_password_with_revision` adds an unlocked change without altering format
interpretation. Its default retains the existing payload secret and recovery slot. Explicit
rotation takes a recovery credential for newly wrapped access. The GUI generates
a fresh one and saves a replacement sheet. KCV1 always derives a fresh key and
stays KCV1. The return value reports the observed revision and whether the key
changed. Earlier snapshots are not revoked. Existing recovery reset still rotates
unconditionally. `verified_snapshot` exposes only authenticated ciphertext bytes
for backups/checksums; SHA-256 remains an application concern, outside this crate
and the minimal Core.

## Recovery slots

KCV2 generates a random 32-byte seed. Each password or recovery slot stores a
salt, a nonce and the seed encrypted under a key derived from that slot's
credential and salt. The slot authenticates the `KCV2` marker, a zero byte and
the slot role as associated data. On open, Core's `decrypt` authenticates the
slot and returns the seed. `derive_key` constructs the opaque payload key using
the fixed KCV2 profile below. Core's generic wrapping profile has its own AAD
encoding for new formats.

## Recovery reset boundary

The hardened `reset_password` authenticates the source
and parses the login records before creating a fresh random 32-byte seed.
Both slots wrap the new seed with fresh salts/nonces, using the new password
and the existing recovery secret. The payload is encrypted under the new key,
with the complete new header as AAD, then atomically replaces the selected file.
KCV2 bytes, readers and recovery-secret compatibility remain unchanged.

Earlier resets retained the seed. Ordinary `save` still retains it. Rekeying
protects updated files from a key recovered from a pre-reset snapshot. The old
snapshot keeps its old access. A current recovery secret still opens the updated
file. Freshness checks require a trusted local revision floor for KCV3 or KCV4.
[Key lifecycle by format](../../apps/vault/FORMAT-LIFECYCLE.md#key-lifecycle-by-format)

KCV2 and KCV3 retain the fixed Argon2id payload derivation and `KCV2 payload key`
salt for compatibility. KCV4 imports the authenticated random 32-byte slot
secret as the payload key. See [the new format and migration rules](KCV4.md).
