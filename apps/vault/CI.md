# Vault CI

Vault source is maintained in the public `kryptocorelabs/vault-source`
repository. Use `publishing/vault-source/` as the local checkout for Vault
changes and CI runs. The public `kryptocorelabs/vault` repository hosts
release notes and downloads.

## Pinned Core source

Vault and `modules/vault-format` inherit the Core Git dependency from the
workspace manifest. The full revision and lockfile are checked in. This
workspace owns the [versioned Vault format](../../modules/vault-format/README.md)
that Rescue pins by revision. To update, review the new Core revision, refresh
the dependency and lockfile, and run the Vault, format and Rescue tests.

## Test coverage

The Vault workflow runs on pushes, pull requests, manual dispatches and a
weekly schedule. It checks KCV2 through KCV4 tampering, write failures,
recovery seed rotation, rejection of keys recovered from old snapshots,
ordinary-save seed stability and repeated recovery resets,
the native channel, browser session invalidation, Rust advisories and licenses,
and Python advisories. The Firefox session tests run in a mocked WebExtension
environment. The real Firefox and Windows integration test is a separate
[release check](FIREFOX-RELEASE-TEST.md).

Windows, Linux and macOS jobs also build Vault and a separately checked-out
Rescue worker pinned to apps-source commit
`65f28e4cfd35020616d62bcf764b2025c10c49ab`. The real stdio protocols exercise
KCV1/KCV2/KCV3 password and recovery exports, Unicode records, backup identity,
re-key/renewal, rollback/downgrade rejection and unchanged inputs. POSIX runs
also verify that exports through linked destination folders are rejected;
temporary fixtures use resolved paths so macOS system aliases do not bypass
or accidentally trigger that guard. This is
interoperability testing between apps sharing the format implementation, not
an independent cryptographic implementation. Local cache tests and Qt workflow
tests cover first observation, remembered minima, failed opens and active-session
locking. Update the reviewed peer pin deliberately when its reader changes.

The same real-worker driver covers versioned JSON exports and Rescue-array
imports into newly seeded KCV2 vaults, health metadata, rejected duplicates,
unknown versions/fields, oversized/malformed input, changed preview bytes,
locked/unconfirmed exports and no-clobber destinations. Format tests compare
fresh seeds and reject old-seed decryption of a newly created payload. Qt tests
exercise the import/password/emergency-sheet flow, cancellation, explicit
plaintext confirmation and successful-only per-path backup timestamps.

Password-change tests prove both boundaries directly: quick wrapping retains the
seed (an extracted old key still works), while explicit re-keying replaces it and
rejects the old key. They cover KCV1 compatibility, KCV3 floors/overflow and intact
files on error. Real-worker tests read changed files with the pinned older Rescue,
check old/new recovery paths and retained old copies, and compare SHA-256 against
Python hashlib. Receipt tests cover stale expected digests, occupied destinations,
malformed references and linked folders. Qt tests exercise both password modes,
cancelled/wrong credentials, clearing inputs, the actual replacement PDF credential,
digest copy/compare/save and no-clobber output. Screenshots use synthetic data.

Two Windows jobs build the unsigned Firefox ZIP independently. The package
uses stable entry order, fixed timestamps and stored entries. After the tests
pass, the Windows build job compares the complete ZIP SHA-256 values, checks
the contents and builds the native backend, helper and channel DLL. Main
branch pushes and manual runs then attest the verified ZIP in a separate job.
This verification covers the unsigned Firefox package. The signed XPI and
Windows desktop executable follow separate distribution checks.

```powershell
cargo +1.99.1 test --locked --release -p kryptocore-vault -p kryptocore-vault-format -p vault-firefox-channel -- --test-threads=1
node --test apps/vault/tests/firefox-security.test.cjs
rustup target add --toolchain 1.99.1 wasm32-unknown-unknown
$env:RUSTUP_TOOLCHAIN = '1.99.1'
./apps/vault/tests/verify-build.ps1 -OutputDirectory ./dist/vault-check
```

Keep live vault files, local settings and credentials out of commits and CI
artifacts. The tests create synthetic fixtures in temporary directories.
