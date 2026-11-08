# KryptoCore Vault and Firefox source

[Security in 30 seconds](SECURITY-IN-BRIEF.md) · [Recover without the main app](RESCUE-FIRST.md) · [Check a download](VERIFY-DOWNLOADS.md)

[![Vault CI](https://github.com/kryptocorelabs/vault-source/actions/workflows/vault-ci.yml/badge.svg)](https://github.com/kryptocorelabs/vault-source/actions/workflows/vault-ci.yml)
[MIT](LICENSE) · [Contribute](CONTRIBUTING.md) · [Security](SECURITY.md) · [Project charter](https://github.com/kryptocorelabs/kryptocore/blob/main/PROJECT_CHARTER.md)

Open-source Qt Vault application, Firefox extension and their shared native
channel. First-party code is MIT licensed. Dependencies, including Qt, retain
their own licenses and distribution requirements. See
[third-party notices](THIRD_PARTY_NOTICES.md).

[Downloads and user guide](https://github.com/kryptocorelabs/vault) remain in the
separate Vault repository. The Core's canonical upstream is
[kryptocore](https://github.com/kryptocorelabs/kryptocore); this workspace includes
its MIT-licensed implementation and the shared Vault format reader so contributors
can build and test the complete application. MSG, Container and Rescue are in
[apps-source](https://github.com/kryptocorelabs/apps-source).

Testing to date has been carried out by the KryptoCoreLabs maintainers, locally
and through automated CI. No independent security audit has been completed.
We welcome community testing, code reviews and scrutiny of our security
assumptions. Please use synthetic data and report suspected vulnerabilities
privately through the project's security-reporting channel.

See the [unreleased recovery hardening](apps/vault/RECOVERY-HARDENING.md) and
[Vault threat model](apps/vault/THREAT_MODEL.md) for seed rotation, old-file access,
rollback and Python/Qt memory limits. Existing published binaries are unchanged.

The local desktop has [native Linux/macOS build paths](apps/vault/PLATFORMS.md),
with Intel and Apple Silicon CI packages. Firefox pairing is Windows-only.
CI packages are unsigned evaluation artifacts, not replacements for current releases.

## Build and test

```sh
git clone https://github.com/kryptocorelabs/vault-source.git
cd vault-source
cargo test --workspace --locked --release
node --test apps/vault/tests/firefox-security.test.cjs
```

Install the Rust toolchain and Node.js first. Windows MSVC also needs C++ build
tools and the Windows SDK. CI pins Rust 1.99.1. The GUI development environment
uses Python 3.13 x64 and the pinned [Qt requirements](apps/vault/desktop/requirements.txt).
End users of the single-file application do not install these development tools.

- [Vault development and usage](apps/vault/README.md)
- [CI and build consistency](apps/vault/CI.md)
- [Single-file packaging](apps/vault/WINDOWS-ONEFILE.md)
- [Browser support and roadmap](apps/vault/BROWSERS.md)
- [Firefox signing and verification](apps/vault/FIREFOX_RELEASE.md)

Vault remains a preview without an independent audit. Firefox 0.1.16 is Mozilla-
signed; that does not certify Vault or replace an audit. Use synthetic data in
tests. Keep actual vaults, emergency sheets, pairing data and signing credentials
out of source control and public issue attachments.
