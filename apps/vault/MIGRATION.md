# Move to a new vault and check its state

These features are in development source and current evaluation builds. Older
published downloads may not include them. Keep tested encrypted backups.

## Export and create a fresh vault

1. Unlock the source vault. Choose **Einstellungen → Logins als JSON exportieren**
   (Settings → Export logins as JSON).
2. Read the plaintext warning and explicitly confirm. Choose a new `.json` file
   in a protected folder. Export never overwrites an existing file.
3. On the destination computer choose **Aus JSON-Export umziehen** on the start
   page, or **Einstellungen → Neuen Tresor aus JSON erstellen**.
4. Check the filename and entry count. Continue to the usual new-vault setup:
   choose a new `.kcv` file, a new password and save the new emergency-sheet PDF.
   Continuing locks an open source session. Cancellation preserves the source;
   the normal inactivity/focus/session lock policy still applies.
5. Vault creates the complete new KCV2 file with a freshly generated random seed,
   fresh password/recovery wrapping and a fresh payload nonce. It opens the new
   vault. Check the logins, make an encrypted backup and test recovery on a copy.
6. Protect and remove the plaintext transfer file when it is no longer needed.
   Deletion does not guarantee erasure from SSDs, snapshots, sync or backups.

The original vault and JSON file remain unchanged. Nothing is merged or silently
replaced. Passwords/usernames transfer, but old vault keys, the old emergency
credential, browser pairings, local history and backup receipts do not. The GUI
generates a new emergency credential. Old snapshots and disclosed site passwords
remain sensitive; migration cannot revoke them. Rotate passwords at the affected
services if they may have been exposed.

The new file uses the existing KCV2 profile, readable by compatible older readers
and Rescue. A KCV3 source does not carry over its identity/history. You can then
enable the [optional KCV3 copy](EPOCHS.md) for the new vault. Existing formats,
Core cryptography and default creation have not been reinterpreted.

For a platform move without a new-key requirement, moving an encrypted `.kcv`
copy and its separately protected access credential avoids a plaintext export.
Use native evaluation builds for the destination OS. Firefox pairing remains
Windows-only and is configured independently.

## Transfer contract

The desktop exporter writes UTF-8 JSON without a BOM:

```json
{
  "format": "kryptocore-vault-export",
  "schema_version": 1,
  "entries": [
    {
      "origin": "www.example.invalid",
      "username": "synthetic-user",
      "password": "synthetic-password"
    }
  ]
}
```

The importer also accepts Rescue's existing bare array of the same records.
Unknown envelope versions/fields, invalid records, empty passwords and duplicate
websites are rejected. Websites follow the editor's normalization rules; collisions
after normalization fail rather than picking one login. Scheme-free websites
remain scheme-free. Multiple accounts for one stored website are not supported.
There is no arbitrary third-party CSV or browser-export import in this change.

Input JSON is capped at 16 MiB. Re-serialized login data must fit the existing
4 MiB KCV2 total-file limit, including its 221-byte overhead. Validation happens
before writing a vault. A SHA-256 fingerprint binds the preview to the bytes
re-read at creation; an intervening edit requires selecting the file again.
That fingerprint does not authenticate who created an untrusted plaintext export.

Plaintext export needs an unlocked, authenticated session and explicit confirmation.
Stale KCV3 revisions are rejected before export. The Rust worker writes the JSON
directly to a temporary file in the selected directory and publishes it without
clobbering. Unix files use mode 0600; Windows files inherit the directory's ACL.
Linked/reparse output ancestors are rejected; the destination directory must
still be trusted and access-restricted. The GUI receives counts, not exported secrets.
Managed memory and serialization can still leave copies; this is not protection
against a compromised process or OS. Exports are not sent to a service.

## Vault status

Open **Status** beside **Sperren**, or **Einstellungen → Tresor-Status**.
The view shows the authenticated entry count, format and whether the format
contains a recovery slot. It does not prove the saved PDF matches that slot;
test recovery on an additional copy.

**Zuletzt hier gesichert** records only successful encrypted backups made through
this GUI at this path. Failed or cancelled backups do not update it. The local
timestamp is stored beside settings; it does not travel with the vault, prove
the backup still exists, or record manual copies. Unknown history stays unknown.

**Datei zuletzt geändert** uses the filesystem modification time. At 180 days
without changes the view suggests checking the expected state and testing a
backup; a future date suggests checking the clock. This is a snapshot when the
view opens. These local, editable dates are not authenticated timestamps, an
expiry rule, a full health scan or a security score.
