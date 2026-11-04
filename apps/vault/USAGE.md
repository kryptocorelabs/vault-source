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

## Security reports and rights

Report suspected vulnerabilities through the
[private reporting process](SECURITY.md). Use synthetic data for reproduction.

We give no voluntary guarantee that this software is error-free, that data
will remain available, or that every incident is recoverable. You manage
where you store and verify your backups and recovery material. Statutory
rights and any liability required by applicable law remain unaffected.
