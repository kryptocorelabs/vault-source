# Vault format lifecycle

The current desktop app writes KCV4 when creating vaults, importing JSON and
making encrypted migration copies. KCV1–KCV3 remain compatibility profiles.
The shared Vault format crate owns the reader and writer. Rescue uses that
crate at a pinned source revision.
[KCV4 byte layout](../../modules/vault-format/KCV4.md)

## Which builds can open a vault?

Use the release notes, exact download filename and verified SHA-256 to
identify the build you installed.

| Build | Opens | New desktop files | Seed rotation on emergency reset |
| --- | --- | --- | --- |
| Public Windows Vault previews through `0.1.0-preview.3` | KCV1/KCV2, according to the preview's release notes | Legacy profiles | Treat these previews as pre-hardening. |
| Vault built from the current source | KCV1–KCV4 | KCV4 | KCV2–KCV4. KCV1 has no emergency credential. |
| Public Rescue `0.1.0-preview.3` | KCV1/KCV2 | Read-only Vault recovery | Exports authenticated records to a separate destination. |
| Rescue with the KCV4-capable reader | KCV1–KCV4 | Read-only Vault recovery | Exports authenticated records to a separate destination. |

Vault desktop handles the `.kcv` file and emergency password reset. The
Firefox extension has its own release version.

## Migrate one active vault

1. Make an encrypted backup and retain its matching password or emergency
   sheet. Verify that the destination Vault and Rescue builds read KCV4.
2. For KCV2 or KCV3, open the file in Vault and choose **Einstellungen → Neue
   KCV4-Kopie anlegen**. Choose a new path. Vault authenticates the source,
   checks any available local revision floor, and creates an encrypted copy
   with a fresh vault ID at revision 1. The existing password and emergency
   sheet still work because the copy retains both slots and their seed.
3. For KCV1, use the [JSON migration workflow](MIGRATION.md) to create a KCV4
   vault with fresh key material, a new password and a new emergency sheet.
   Treat the export as plaintext. The same fresh-key migration is available
   from KCV2 or KCV3 when a separate key is required.
4. Open the new copy and check the expected records. Test emergency access
   on a disposable copy, then back up the new active vault. Keep the source
   and old backups as dated snapshots with the credentials that open them.

The encrypted format copy retains the seed. If it may have been exposed,
rotate it explicitly or use the fresh-key migration. Carry forward one active
file and one revision history. Existing backups stay separate from the active
file. A KCV3-to-KCV4 copy starts a new history and does not inherit the old
file's revision floor. [Local revision checks](EPOCHS.md)

## Compatibility and deprecation

| Profile | Current writer policy | Revision policy |
| --- | --- | --- |
| KCV1 | Legacy opens and edits retain KCV1. The legacy CLI `init` can still create it. Enabling recovery on an existing KCV1 file uses the KCV2 compatibility path. | No authenticated revision. |
| KCV2 | Maintain existing files. Version-unspecified worker requests and legacy format-library entry points can still create it. Use a new KCV4 copy to migrate. | No authenticated revision. |
| KCV3 | Maintain existing files. The legacy worker `enable_epoch` command can still create a KCV3 copy of KCV2. The current desktop uses its KCV4 copy action. | An authenticated ID and counter with a local observed revision floor. |
| KCV4 | Current desktop creation, JSON import and format-copy destination. Ordinary edits and key operations retain KCV4. | Same revision mechanism as KCV3, with a new ID when a new file is created. |

The supported desktop flows converge on KCV4. Treat legacy creation as
deprecated compatibility behavior. Retire those creation entry points before
considering changes to legacy editing. Announce each writer retirement in the
release notes before it takes effect, with a verified migration route and exact
compatible Rescue version. Keep read-only recovery and versioned fixtures for
KCV1–KCV3. An existing-format save or key operation preserves its profile except
for the explicit KCV1 recovery setup described above.

Use KCV4 for new work. A new format marker requires a documented need for an
incompatible on-disk change, pinned fixtures, a tested migration/recovery plan,
and security review of the version boundary. Keep application versions
independent of file-format versions.

## Key lifecycle by format

This describes current source and builds identified as containing the recovery
hardening in the compatibility table.

| Profile | Change password | Explicit re-key in the password dialog | Reset with emergency sheet | Enable or renew emergency sheet |
| --- | --- | --- | --- | --- |
| KCV1 | Derives a fresh payload key from the new password and a new salt. | Same operation. | Unavailable. | Creates a KCV2 file with a random seed and two fresh slots. |
| KCV2 | Rewraps the same seed for the new password. The existing sheet stays valid. | Fresh seed, new password and new sheet. | Fresh seed and new password. The existing sheet stays valid. | Fresh seed and new sheet. The password stays valid. |
| KCV3 | Same KCV2 key behavior. | Same KCV2 key behavior. | Same KCV2 key behavior. | Same KCV2 key behavior. |
| KCV4 | Same slot behavior. The seed is the direct payload key. | Fresh direct payload key, new password and new sheet. | Fresh direct payload key and new password. The existing sheet stays valid. | Fresh direct payload key and new sheet. The password stays valid. |

KCV2 and KCV3 derive the payload key from the random slot seed through their
original Argon2id profile. KCV4 uses the random 32-byte slot plaintext directly
as the payload key. KCV2–KCV4 ordinary saves retain that seed and refresh the
payload nonce. Successful KCV3/KCV4 updates to an existing file retain its ID
and advance its revision. [Payload key details](../../modules/vault-format/KCV4.md)

Every old snapshot remains readable with its matching credentials. A recovered
old seed can decrypt later payloads that reuse it, including after a
password-only change. After rotation, that seed alone cannot decrypt the new
payload. A credential that remains valid for the active file, such as the sheet
retained by a reset, can still open it and recover the new seed. Renew an exposed
sheet. Change exposed account passwords at their respective services.

The [historical recovery review](RECOVERY-HARDENING.md) records the original
reset regression. The [Vault threat model](THREAT_MODEL.md) covers trust
boundaries, session memory and local rollback limits.
