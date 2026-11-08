# Vault desktop platforms

The development source supports the local Qt desktop on Windows x64, Linux x64,
macOS Intel and Apple Silicon. Native CI builds and smoke tests identify the
actual checked platform and source commit. These are evaluation artifacts,
not an independently audited or publisher-signed consumer release.

| Capability | Windows | Linux / macOS |
| --- | --- | --- |
| Create/open KCV1/KCV2, edit logins | Yes | Same Rust worker and Qt UI |
| Backups, emergency sheet/PDF, recovery re-key | Yes | Same format and workflow |
| Idle timeout and manual lock | Yes | Yes; additionally locks on focus loss and unexpected timer/clock gaps |
| Native Windows lock/suspend notifications | Yes | Not applicable; native OS-specific integration remains future work |
| Firefox v5 pairing/native host | Yes | Disabled; no weaker IPC or plaintext-key fallback |
| Glass/Mica | Optional on compatible Windows | Solid themed fallback |
| Publisher signing / notarization | Pending | Pending |

Builds are native: PyInstaller is not a cross-compiler. Linux produces a
single executable in a `.tar.gz`; a compatible glibc-based desktop and system
graphics libraries are required. macOS produces a normal `.app` in a ZIP, built
separately for Intel and Apple Silicon. A `.app` is a directory bundle even if
Finder presents it as one application. No universal-binary claim is made.
Windows continues to offer its existing portable EXE workflow.

## Source use

Install stable Rust and Python 3.13 for the target architecture, then:

```sh
cargo build --locked --release -p kryptocore-vault
python -m pip install -r apps/vault/desktop/requirements.txt
python apps/vault/desktop/vault.pyw
```

To build an evaluation package:

```sh
python -m pip install -r apps/vault/desktop/requirements-onefile.txt
python apps/vault/package-desktop.py --output dist/vault-native --work dist/vault-native-work
```

Use a fresh work directory. The build invokes `--verify-bundle` before packaging,
records its source/architecture and produces SHA-256 metadata. CI artifacts
retain those records. This does not certify publisher identity or reproducibility.
Qt/LGPL matching-source/library replacement requirements and platform-specific
notices must be reviewed before public consumer distribution; historical notice
inventories do not certify a new platform package. Gatekeeper, SmartScreen and
clean-machine validation remain release gates; do not globally disable OS checks.

On Linux/macOS, the conservative focus-loss lock also applies when switching to
another app. This is intentional until native desktop session events have been
implemented and tested. Vault files remain interoperable across platforms;
Windows Firefox pairing/DPAPI files are device-specific and are not migrated.
