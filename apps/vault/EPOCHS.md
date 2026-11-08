# Optional local rollback warnings — unreleased

KCV1 and KCV2 remain supported and are not silently rewritten. New vaults still
use the existing format. With an unlocked KCV2 vault, choose **Einstellungen →
Versionsvergleich als neue Kopie aktivieren** (Settings → Enable version checks
as a new copy). This creates a **KCV3 copy** with a new random vault ID and epoch
1, preserves the original file, retains password/emergency-sheet access and
switches the active session to the copy. A KCV1 vault needs recovery configured
first. Existing destination files are never overwritten.

**Use current KCV3-capable Vault and Rescue builds for that copy.** Older apps
reject the new format. The currently published Rescue preview.3 download does
not support it; this change is in development source/local review builds only.
Keep the original and a tested backup. Browser pairings are unchanged; pending
browser requests are invalidated when the active file switches to the new copy.

## What gets checked

The complete header, including the 128-bit ID and unsigned 64-bit epoch, is
authenticated with the encrypted payload. Successful saves, password resets
and emergency-sheet renewals increment the epoch. Backups retain the exact
bytes and epoch. Failed operations do not deliberately advance it; counter
overflow rejects writes. Password reset still rotates the payload seed.

After authentication, the GUI records the highest observed epoch per ID and a
binding to the selected path in `epoch-observations.json` beside local settings.
The worker receives that minimum when opening/recovering and keeps a minimum
throughout its session. A lower epoch, replaced identity at a known path or
downgrade to an older format is rejected before data is exposed or overwritten.
Discovery during an active session locks Vault and invalidates browser requests.
Cache updates are serialized with a local lock and written using QSaveFile.

Header peeking only selects a previously known policy; it never advances the
cache. Cache errors fail closed. If an encrypted write succeeded but the later
local cache update fails, the file may already contain the new state; preserve
it and correct the local storage problem rather than overwriting it.

## Deliberate recovery and limits

For an intentionally older backup, use a working copy in the current KCV3-capable
Rescue and export to a fresh protected destination. Rescue is read-only with
respect to the source and deliberately does not enforce Vault's local floor or
claim that a backup is the newest. See [rescue-first workflow](https://github.com/kryptocorelabs/kryptocore/blob/main/RESCUE-FIRST.md).

This is **not complete rollback protection**. A new device without history,
deleting/restoring the cache together with the vault, an unknown legacy file at
a new path, equal-epoch conflicting copies, path aliases, key compromise or a
hostile OS can defeat or fall outside these checks. It is not trusted monotonic
hardware, server synchronization or an authoritative revision service.
The public header exposes an ID and revision count; copies can be correlated.
Activation retains the existing seed and is not a credential-revocation operation.

See the [KCV3 byte contract](../../modules/vault-format/KCV3.md). The encryption
Core, KDF parameters and browser channel have not been changed. Maintainer tests
and native CI are not an independent security audit.
