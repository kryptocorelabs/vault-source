# Password changes, key rotation and file checksums

These features are in development source and evaluation builds. Existing
published releases may not contain them; identify the exact source/build.

## Change an unlocked vault's password

Choose **Einstellungen → Tresorpasswort ändern** (Settings → Change vault
password). Re-enter the current password, choose a different new password of
at least 15 characters and confirm it. The local strength estimate is guidance.

For KCV2/KCV3 the switch **Neuen Tresorschlüssel erzeugen** (Generate a new
vault key) is **off by default**:

| Mode | Current file | Recovery sheet | Earlier copies |
| --- | --- | --- | --- |
| Password only | Fresh password wrapping and payload nonce; same payload seed | Existing sheet stays valid | Their matching credentials still work; an extracted old seed also remains useful against the current file until the seed is rotated |
| Explicit re-key | Fresh random payload seed, both fresh wrapping slots and fresh nonce | GUI generates a new credential and requires a new PDF before committing | Copies retain their old access; their old seed cannot decrypt the re-keyed current payload |

The re-key sheet becomes valid only after the password change succeeds. Until
then the existing file/credentials remain authoritative. Keep old credentials
with old backups you intend to retain. After either mode make an encrypted
backup and test a disposable copy. Never overwrite the original for a test.

**A re-key cannot make old copies unreadable.** It does not retract plaintext
or change stored account passwords at their services. If those passwords were
exposed, rotate them at the services too. Old copies and their matching access
credentials remain sensitive.

KCV1 has no separate wrapped seed or recovery slot. Changing its password always
derives a fresh key with a fresh salt, retaining KCV1 compatibility. Its GUI switch
is therefore checked/disabled and explains the behavior. Configure a recovery
sheet separately if you want to move that legacy file to the recovery profile.

This is separate from **Recovery reset**: resetting through an emergency
credential continues to rotate the seed unconditionally while preserving that
credential. Enabling/renewing recovery also rotates the seed; the current
password stays the same and the GUI saves a fresh emergency credential.

KCV3 retains its vault ID and advances its authenticated epoch on a successful
password change. Stale revisions and counter overflow are rejected before
replacement. KCV1/KCV2/KCV3 interpretation, Core primitives and KDF parameters
are unchanged. The worker changes its session password only after a successful
atomic write. GUI success invalidates pending browser requests; persistent v5
pairings remain. Cancellation and failed operations do not replace source data.

## What the short UI notes mean

- **Password change:** the mode explains whether the internal key and sheet
  remain valid. A common note says that old copies stay readable.
- **Enable/renew recovery:** the note states that the internal key also changes,
  the new sheet belongs to the current file and old copies retain old access.
- **Backup:** the note states that the copy retains its current credentials,
  even after changing the active vault. Store dated copies separately.

## Record and compare a file fingerprint

With a vault unlocked choose **Einstellungen → Datei-Prüfwert (SHA-256)**,
or the same action in **Status**. Vault authenticates and validates a bounded
snapshot, checks its remembered KCV3 minimum where applicable and hashes the
**exact encrypted bytes** of that snapshot. No plaintext or key is hashed/exported
by this action. Ordinary AEAD checking remains in place; a checksum is additional
reference information.

Copy the displayed value, note it separately or select **Prüfwert separat
speichern**. The `.sha256` file contains 64 lowercase hexadecimal characters
and one newline, without an embedded path or filename. Existing destinations
are never overwritten. Keep a baseline in a trusted location separate from the
vault; an attacker who can replace both can defeat this comparison.

**Mit notiertem SHA-256 vergleichen** accepts a recorded value, ignoring its
letter case/whitespace. The result compares against the displayed snapshot,
not an automatically refreshed file. Close and reopen the view to refresh it.
Saving re-authenticates/re-hashes the file and rejects a changed snapshot rather
than writing an out-of-date reference. Linked/reparse output folders are rejected;
use an access-restricted destination. The output is not a secret, but can identify
a particular encrypted file/copy.

Normal saving, password changes, key rotation and recovery changes can alter
the digest even when the login content is unchanged. An exact encrypted backup
has the same digest as its source snapshot. A mismatch can mean an expected edit,
a different copy, corruption or tampering; it does not diagnose which.
A matching value is not a publisher signature, identity proof, malware scan or
complete rollback protection. A trusted prior reference is necessary.

The minimal Core is unchanged. SHA-256 uses the already-resolved RustCrypto
`sha2` 0.10.9 dependency; existing notices/license texts apply. Tests remain
maintainer/CI testing, not an independent security audit.
