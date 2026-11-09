# Vault one-file Windows preview

`KryptoCore-Vault-Portable.exe` bundles the Vault GUI, Python, Qt, and the
Rust backend. Double-click it on Windows x64. Vault files (`.kcv`) remain
separate and work with the existing desktop build. The app unpacks its
runtime into a temporary directory while it runs.

When Firefox integration is initialized, Vault stores the native host in
the user's existing Vault settings directory under `native-host`. This
gives Firefox a stable path between launches. Firefox still needs its own
extension. The Vault file, recovery sheet, and application are independent.

To build locally, use a Windows x64 Python 3.13 virtual environment, install
`apps/vault/desktop/requirements-onefile.txt`, and run the build script from
the repository root with the path to that environment's Python executable.

```powershell
./apps/vault/package-windows-onefile.ps1 -PythonExe <path-to-venv-python.exe>
```

The EXE and checksum are written to `dist/vault-onefile`. Run the EXE
with `--verify-bundle` to check the bundled Qt assets, password estimator,
Firefox host files, and creation and reopening of a synthetic vault.
The verification path does not open the normal Vault session or change the
current Firefox native-host registration. Packaging also runs the shared
executable-only check with isolated runtime paths and records its results
under the output directory's `verification` folder.

Use `-OutputDirectory` and `-WorkDirectory` for an isolated design build so
an existing versioned package is preserved.

The [Windows build workflow](../../.github/workflows/windows-provenance.yml)
builds the full portable EXE on two separate Windows runners from the same
source commit. It pins Rust and Python versions and checks the SHA-256 of
each packaging wheel. Each job smoke-tests its EXE and records the compiler,
runner image, input lockfiles and output digest. The final job compares the
EXEs byte for byte and attests the matched artifact. A mismatch leaves the
individual build records available for diagnosis.

For the exact EXE from a successful run, check its digest against the two
build records and verify its GitHub attestation with
`gh attestation verify KryptoCore-Vault-Portable.exe -R kryptocorelabs/vault-source`.
Existing preview ZIPs have their own release evidence.

This is a local packaging preview. Before distributing a build publicly,
review the bundled dependencies and their notices, Qt library replacement
and matching source delivery, and Windows code signing. See the existing
[third-party notices](../../THIRD_PARTY_NOTICES.md) and
[Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations).
