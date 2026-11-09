# KCV4 payload key and revision profile

KCV4 uses the [KCV3 byte layout](KCV3.md) with the magic `KCV4\0`. It retains the
16-byte vault ID, big-endian `u64` revision, two 88-byte access slots, 24-byte
payload nonce and authenticated ciphertext. The payload authenticates the full
header through the end of both slots. Revision checks can compare the SHA-256
of the authenticated file to a caller-supplied floor at the same counter.

Each access slot derives a wrapping key from its password or recovery secret
with the existing Argon2id profile and its stored salt. Slot AAD remains
`KCV2\0 || role`. KCV4 uses the authenticated, uniformly random 32-byte slot
plaintext directly as the XChaCha20-Poly1305 payload key through
`Key::from_bytes`. That key is dedicated to the payload. KCV2 and KCV3 use their
original Argon2id payload derivation, selected by their own format markers.

Desktop creation and JSON import write KCV4. The worker's version-unspecified
requests and existing format-library entry points remain available for legacy
clients. Opening, saving and resetting an existing vault select its version
from the authenticated format. Use a KCV4-capable Vault or Rescue for KCV4 files.

Vault can authenticate an existing KCV2 or KCV3 file and create a new KCV4 copy.
The destination must be new. The copy starts a separate revision history at 1
with a fresh vault ID. It keeps both existing slots, so the current password
and emergency sheet still work. A format conversion retains the underlying
slot secret. Use explicit key rotation for a suspected key exposure. Keep the
original file and test the new copy before replacing your backup plan.
