# Vault CI

Vault source is maintained in the public `kryptocorelabs/vault-source`
repository. Use `publishing/vault-source/` as the local checkout for Vault
changes and CI runs. The public `kryptocorelabs/vault` repository hosts
release notes and downloads.

The Vault workflow runs on pushes, pull requests, manual dispatches and a
weekly schedule. It checks KCV2/KCV3 tampering and truncation, write failures,
recovery seed rotation, rejection of keys recovered from old snapshots,
ordinary-save seed stability and repeated recovery resets,
the native channel, browser session invalidation, Rust advisories and licenses,
and Python advisories. The Firefox session tests run in a mocked WebExtension
environment. Real Firefox and Windows integration testing remains a release
check.

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

The Windows build job runs after those checks pass. It builds the native
backend, helper, and channel DLL with the lockfile, then compares the contents
of two Firefox ZIPs from clean build directories. The comparison includes the
WASM, manifest, JavaScript and dependency notices. ZIP container timestamps
can differ. The job attaches checksums for the native outputs, WASM and one ZIP.
The checksums do not attest to reproducibility of the Windows GUI package or
replace Authenticode or Mozilla signing.

```powershell
cargo +1.99.1 test --locked --release -p kryptocore-vault -p kryptocore-vault-format -p vault-firefox-channel -- --test-threads=1
node --test apps/vault/tests/firefox-security.test.cjs
rustup target add --toolchain 1.99.1 wasm32-unknown-unknown
$env:RUSTUP_TOOLCHAIN = '1.99.1'
./apps/vault/tests/verify-build.ps1 -OutputDirectory ./dist/vault-check
```

Keep live vault files, local settings and credentials out of commits and CI
artifacts. The tests create synthetic fixtures in temporary directories.
