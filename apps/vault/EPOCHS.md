# Local rollback warnings

The desktop development build creates KCV4 files with local revision checks.
With an unlocked KCV2 or KCV3 vault, choose **Einstellungen → Neue KCV4-Kopie
anlegen**. The copy starts at revision 1 with a fresh vault ID, retains password
and emergency-sheet access, and becomes the active file. Use a new destination.
The source stays available as a separate copy. Configure a recovery slot first
if the source uses KCV1.

**Use KCV4-capable Vault and Rescue builds for that copy.** The currently
published Rescue preview.3 predates KCV4. Use the newer source for evaluation.
Keep the original and a tested backup. Browser pairings are unchanged; pending
browser requests are invalidated when the active file switches to the new copy.

## What gets checked

The complete header, including the 128-bit ID and unsigned 64-bit epoch, is
authenticated with the encrypted payload. Successful saves, password resets
and emergency-sheet renewals increment the epoch. Backups retain the exact
bytes and epoch. Failed operations do not deliberately advance it; counter
overflow rejects writes. Password reset still rotates the payload seed.

After authentication, the GUI records the highest observed epoch per ID, the
SHA-256 fingerprint of that exact encrypted snapshot and a binding to the
selected path in `epoch-observations.json` beside local settings.
The worker receives that minimum when opening/recovering and keeps a minimum
throughout its session. A lower epoch, replaced identity at a known path or
downgrade to an older format is rejected before data is exposed or overwritten.
A different valid file at an already observed epoch is also rejected. An exact
copy remains usable. The first authenticated observation after upgrading fills
in fingerprints for existing entries as they are opened. Older builds cannot read
the upgraded local history.
Discovery during an active session locks Vault and invalidates browser requests.
Cache updates are serialized with a local lock and written using QSaveFile.

Header peeking only selects a previously known policy; it never advances the
cache. Cache errors fail closed. If an encrypted write succeeded but the later
local cache update fails, the file may already contain the new state; preserve
it and correct the local storage problem rather than overwriting it.

## Deliberate recovery and limits

For an intentionally older backup, use a working copy in a compatible version of
Rescue and export to a fresh protected destination. Rescue is read-only with
respect to the source and deliberately does not enforce Vault's local floor or
claim that a backup is the newest. See [rescue-first workflow](https://github.com/kryptocorelabs/kryptocore/blob/main/RESCUE-FIRST.md).

This is **not complete rollback protection**. A new device without history,
deleting/restoring the cache together with the vault, an unknown legacy file at
a new path, unseen forks at a higher epoch, path aliases, key compromise or a
hostile OS can defeat or fall outside these checks. It is not trusted monotonic
hardware, server synchronization or an authoritative revision service.
The public header exposes an ID and revision count; copies can be correlated.
Activation retains the existing seed and is not a credential-revocation operation.

See the [KCV3 byte contract](../../modules/vault-format/KCV3.md) and
[KCV4 profile](../../modules/vault-format/KCV4.md). Maintainer tests and native
CI are still awaiting independent security review.
