# Using Vault

Vault is a local password manager. It encrypts saved logins in a `.kcv`
file on your device. Use synthetic credentials to evaluate the release
candidate and keep original copies of any credentials separately.

## What encryption protects

Encryption protects the contents of a locked vault file. Vault needs
access to login data while the vault is unlocked and when you fill a
website. A compromised device or browser can expose data during use.
Software defects, a lost device, a damaged file, and lost access credentials
can still cause data loss. We test these paths and investigate reported
issues as the project develops.

## Make and test backups

1. With the vault unlocked, choose **Settings → Create backup**
   (**Einstellungen → Sicherung erstellen**). Save the encrypted copy to
   separate storage. In earlier previews, close Vault and copy the `.kcv`
   file to separate storage using your file manager.
2. Keep more than one dated copy. Create a new backup after important
   changes and before updating Vault.
3. Keep the emergency sheet somewhere protected, apart from both the vault
   and its backups. It lets you reset the password for the matching file.
   A lost or damaged vault file requires a readable backup.
4. To check a backup, make a disposable copy of it, open that copy in Vault,
   and verify that your test logins are present. To check the emergency
   sheet, use **Recover vault** (**Wiederherstellen**) on the disposable
   copy and choose a new password. Recovery changes the password in the
   selected file. Keep the original vault and backup intact.

Backups preserve the credentials and recovery configuration from the time
they were taken. Keep the password or emergency sheet that matches each
backup you retain. If a file stops opening, preserve it and try a separate
copy of your latest known good backup.

## Password resets and old copies

Changing or resetting the vault password affects the selected file only. Old
copies remain readable with the password or emergency sheet that matched them.
If someone may have read a copy, also change the stored account passwords at
their services; changing the vault password cannot revoke exposed credentials.

The new unlocked password-change dialog retains the KCV2/KCV3 seed and existing
sheet by default. Its optional re-key mode generates a fresh seed and a replacement
sheet. This is separate from resetting through a recovery credential below.

The [unreleased recovery hardening](RECOVERY-HARDENING.md) also replaces the
internal data key while retaining the current emergency sheet. Earlier builds
kept that key when resetting the password. Keep a verified backup before trying
an updated build. After a reset, make and test a fresh backup. If the emergency
sheet itself may be exposed, renew it from the unlocked vault as well; older
copies still retain their former recovery access.

KCV1/KCV2 cannot detect that an authentic file is an older snapshot. The
[optional KCV3 profile](EPOCHS.md) adds a local history check with documented
limits. When restoring a copy, check the expected recent entries.

## Move and review a vault — development builds

Use **Settings → Export logins as JSON** for a deliberate plaintext transfer,
then **Create a new vault from JSON** to use fresh key material, a new password
and a new emergency sheet. Rescue's JSON array is also accepted. Existing files
are preserved; protect the unencrypted JSON. See [the migration guide](MIGRATION.md).

**Status** beside **Lock**, or **Settings → Vault status**, shows entries,
recovery-slot availability, the last backup recorded here and the filesystem
modification date. Unknown backup history stays unknown. A 180-day-old date
prompts a check; this is not a security score or proof that a backup is readable.

## Password changes and file fingerprints — development builds

Development builds also offer **Settings → Change vault password** with an
optional new key/new emergency-sheet step and **File fingerprint (SHA-256)**
for recording/comparing encrypted file snapshots. Old copies remain readable
with matching credentials. See [access and integrity](ACCESS-AND-INTEGRITY.md).

## Security reports and rights

Report suspected vulnerabilities through the
[private reporting process](SECURITY.md). Use synthetic data for reproduction.

We give no voluntary guarantee that this software is error-free, that data
will remain available, or that every incident is recoverable. You manage
where you store and verify your backups and recovery material. Statutory
rights and any liability required by applicable law remain unaffected.
