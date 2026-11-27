# Using Vault

Vault is a local password manager. It encrypts saved logins in a `.kcv`
file on your device. Use synthetic credentials to evaluate the development
preview and keep original copies of any credentials separately.

## First use and daily use

The current desktop interface uses German labels. The instructions below keep
those labels so you can find the matching controls.

1. Start Vault and choose **Neuer Tresor**. Choose **Auswählen** to select a
   name and location for the `.kcv` file. Enter and confirm a vault password
   of at least 15 characters; the strength estimate is guidance, not a guarantee.
2. Choose **Weiter zum Notfallblatt**, read the recovery warning, and choose
   **PDF speichern und fortfahren**. Protect that PDF separately from the vault
   and its backups. It cannot replace a missing or damaged vault file.
3. Choose **Neuer Login**, enter **Website**, **Benutzername** and **Passwort**,
   then **Login speichern**. **Erzeugen** generates a login password;
   **Anzeigen** and **Verbergen** let you check and hide it deliberately.
4. Use **Website oder Benutzername suchen** to find an entry. Double-click it
   (or select it and press Enter) to show its details. Choose **Bearbeiten** to
   change it. Leave **Neues Passwort** empty to retain its current password.
5. Choose **Sperren** or press `Ctrl+L` when finished. To return, choose
   **Tresor entsperren** for the remembered file, or **Anderen Tresor öffnen**
   to choose another file. When no file is remembered, use **Tresor öffnen**.
   Enter its password. In **Alltag** mode, Vault remembers the file location,
   but still requires the password.

Make and test a separate backup before relying on the vault. Browser setup is
described in the [Firefox guide](README.md#firefox); pairing and each credential-fill
approval remain deliberate security steps.

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

The unlocked password-change dialog retains the KCV2–KCV4 seed and existing
sheet by default. Select the re-key option to generate a fresh seed and sheet.
Builds with hardened recovery rotate the seed during emergency reset and keep
the current sheet valid. Check your version before relying on seed rotation.
[Compatibility matrix and key lifecycle](FORMAT-LIFECYCLE.md)

After a reset, make and test a fresh backup. If the emergency sheet may have
been exposed, renew it from the unlocked vault. Older copies retain their
former recovery access. When restoring a copy, check the expected recent
entries. KCV3 and KCV4 use [local revision checks](EPOCHS.md) where trusted
history is available.

## Move and review a vault — development builds

Use **Einstellungen → Logins als JSON exportieren** (export logins as JSON) for
a deliberate plaintext transfer, then **Aus JSON-Export umziehen** on the start
screen to create a KCV4 file with fresh key
material, a new password and a new emergency sheet. The desktop also accepts
Rescue's JSON array. Keep the old file and protect the unencrypted JSON.
[Migration guide](MIGRATION.md)

**Status** beside **Sperren**, or **Einstellungen → Tresor-Status**, shows entries,
recovery-slot availability, the last backup recorded here and the filesystem
modification date. Unknown backup history stays unknown. A 180-day-old date
prompts a check; this is not a security score or proof that a backup is readable.

## Password changes and file fingerprints — development builds

Development builds also offer **Einstellungen → Tresorpasswort ändern** with an
optional new key/new emergency-sheet step and **Datei-Prüfwert (SHA-256)**
for recording/comparing encrypted file snapshots. Old copies remain readable
with matching credentials. See [access and integrity](ACCESS-AND-INTEGRITY.md).

## Security reports and rights

Report suspected vulnerabilities through the
[private reporting process](SECURITY.md). Use synthetic data for reproduction.

We give no voluntary guarantee that this software is error-free, that data
will remain available, or that every incident is recoverable. You manage
where you store and verify your backups and recovery material. Statutory
rights and any liability required by applicable law remain unaffected.
