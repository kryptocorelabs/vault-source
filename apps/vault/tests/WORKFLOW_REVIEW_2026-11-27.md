# Vault workflow review — 2026-11-27

**Phase C: PARTIAL.** The source workflow has automated regression evidence;
clean-machine installation, recovery on another physical test system and an
independent novice completing the workflow have not been verified. This is a
maintainer review, not an independent security audit or a usability study.

## Source and test environment

- Source baseline: `3fd1fe9b2f612757cba0277fb920710b6869e6dc` on
  `codex/ecosystem-security-hardening-20261127`, plus the test and usage-guide
  changes accompanying this report.
- Windows x64; CPython 3.13.18, PySide6-Essentials/Qt 6.10.3, zxcvbn 4.5.0.
- Worker: `target/release/kryptocore-vault.exe`, SHA-256
  `5eaaad96ce51fdd8835183fe51f3d432430b5bc3476ee7aaca6de5e60aee32f7`.
- Command from the repository root, using the pinned GUI virtual environment:
  `python apps/vault/tests/desktop-workflow.py`.

The harness sets `QT_QPA_PLATFORM=offscreen`, redirects `LOCALAPPDATA` to a
temporary directory, substitutes file-picker results and suppresses normal
Windows Firefox registration. It uses the real Qt dialogs and Rust worker
with synthetic credentials and disposable files. Programmatic interaction is
not evidence of actual keyboard, screen-reader or inexperienced-user success.

## C1–C4 evidence and remaining gates

| Area | Evidence | Not verified |
| --- | --- | --- |
| C1: first use | New KCV4 creation, password/confirmation, separate emergency PDF, masked recovery preview, back/cancel without a vault file, first login through the actual editor. The usage guide now gives a short walkthrough with the displayed German labels. | Download and start of the exact distributed artifact on clean Windows; a novice independently following the walkthrough. |
| C2: daily use | Actual editor creation and update, generated password reveal/hide, retaining a password when the new-password field is empty, host/username searches, empty search result, cancel without file changes. Existing bridge tests cover exact origin, one-use approval, denial, expiry, changed pairing key and session lock. | Actual installed Firefox pairing/autofill against the exact release artifact; keyboard-only operation and interrupted desktop operations as user-visible end-to-end workflows. |
| C3: backup/recovery | No-clobber backup and receipt, recovery from a disposable copy, cancelled recovery field clearing, original preservation, stale-revision rejection, password rotation and a usable replacement emergency sheet. JSON migration uses fresh KCV4 material. | Restore on a second clean system; a novice distinguishing backup from emergency sheet; damaged backup and wrong-password messaging as complete GUI workflows. |
| C4: accessibility | Source provides named fields, labels with buddies, deliberate password reveal controls, visible focus styles, Enter activation for start tiles/login details, and scrollable dialogs. These are implementation observations. | Screen-reader announcements, keyboard focus order, contrast measurements, high-DPI/large-text layout and real novice comprehension. |

## Targeted changes

`desktop-workflow.py` previously inserted the first login directly through the
worker. It now creates and edits it through the actual login dialogs, checks
generated-password visibility, validates searching by host and username, and
ensures a cancelled edit leaves the vault bytes unchanged. These tests exercise
existing behavior; no application cryptography, format, pairing or approval
requirements changed.

`USAGE.md` now keeps the current German action labels in its English
instructions for JSON migration, status, password changes and file fingerprints.
It also explains first use, daily editing and the remembered-file unlock tile.

Two accessibility checks need actual assistive-technology testing: error labels
are updated without a dedicated announcement/focus action, and password-strength
feedback changes asynchronously. No screen-reader failure or conformance claim
is inferred from source inspection alone.

## Test result

The sandboxed run passed the editor/search, recovery/migration and browser
approval assertions, then failed at the final Windows same-session named-pipe
probe with `QLocalServerPrivate::addListener: Zugriff verweigert`. Its log is
`dist/ecosystem-hardening-20261127/vault-workflow-phase-c.log` in the maintainer
workspace. The proposed unrestricted retry was cancelled before execution; this
does not count as a completed test run.

The coordinating maintainer then ran the same harness with the existing Windows
permission: **PASS, exit code 0**. The full run includes the final same-session
named-pipe probe and the new editor/search assertions. Its log is
`dist/ecosystem-hardening-20261127/vault-workflow-phase-c-root.log`. The output
confirms login editor/search/cancel, delete cancellation, bridge origin/approval/
expiry/key-change/lock, recovery/epochs, migration/health, password/key rotation,
replacement PDF, file digests and original/no-clobber preservation. This is local
Windows source-workflow evidence only, not a clean Windows or cross-platform
product acceptance result.

## Next validation

Use a fresh Windows VM and the exact candidate download, with no Python, Rust or
development environment installed. Follow the usage guide from download through
first login, lock/unlock, backup and recovery on a second disposable system.
Record artifact hashes, Windows build, actions and outcomes. Separately run the
same paths keyboard-only at increased scaling with a screen reader, and ask an
available inexperienced participant to follow the guide without coaching. Keep
these results distinct from automated simulation and retain the original test
vault and backup during all recovery tests.
