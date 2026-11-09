# KryptoCore Vault and Firefox source

Vault is an open-source password manager for people who want to keep their
logins on their own device. The desktop app stores them in an encrypted file
and works offline without an account or cloud service.

**Development preview.** Try it with test data. An independent security audit
is pending.

[Try the Windows preview](https://github.com/kryptocorelabs/vault#try-the-desktop-preview) · [Build from source](#build-and-test) · [Give feedback](https://github.com/kryptocorelabs/vault/issues)

[Security in 30 seconds](SECURITY-IN-BRIEF.md) · [Recover without the main app](RESCUE-FIRST.md) · [Check a download](VERIFY-DOWNLOADS.md)

[![Vault CI](https://github.com/kryptocorelabs/vault-source/actions/workflows/vault-ci.yml/badge.svg)](https://github.com/kryptocorelabs/vault-source/actions/workflows/vault-ci.yml)
[MIT](LICENSE) · [Contribute](CONTRIBUTING.md) · [Security](SECURITY.md) · [Project charter](https://github.com/kryptocorelabs/kryptocore/blob/main/PROJECT_CHARTER.md)

This repository contains the Qt desktop app, Firefox extension and their
shared native channel. First-party code is MIT licensed. Dependencies,
including Qt, retain their own licenses and distribution requirements. See
[third-party notices](THIRD_PARTY_NOTICES.md).

This workspace uses the public [KryptoCore crate](https://github.com/kryptocorelabs/kryptocore)
at a [reviewed Git revision](apps/vault/CI.md#pinned-core-source). The shared
Vault format crate lives here and Rescue consumes it from an exact Git revision.
MSG, Container and Rescue are in
[apps-source](https://github.com/kryptocorelabs/apps-source).

Testing to date has been carried out by the KryptoCoreLabs maintainers, locally
and through automated CI. We welcome community testing, code reviews and
scrutiny of our security assumptions. Report suspected vulnerabilities privately
through the project's [security-reporting channel](SECURITY.md).

See the [unreleased recovery hardening](apps/vault/RECOVERY-HARDENING.md) and
[Vault threat model](apps/vault/THREAT_MODEL.md) for seed rotation, old-file access,
rollback and Python/Qt memory limits. Existing published binaries are unchanged.

The local desktop has [native Linux/macOS build paths](apps/vault/PLATFORMS.md),
with Intel and Apple Silicon CI packages. Firefox pairing is Windows-only.
CI packages are unsigned evaluation artifacts, not replacements for current releases.

Development builds include [JSON migration and Vault status](apps/vault/MIGRATION.md):
create a new vault with fresh key material from a deliberate plaintext export,
and review entry/recovery facts alongside local backup and file-age hints.

[Password changes and encrypted-file checksums](apps/vault/ACCESS-AND-INTEGRITY.md)
add optional seed/recovery renewal and separately recorded SHA-256 references.
Old snapshots remain readable; checksums do not establish a trusted publisher.

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

The published Firefox 0.1.16 add-on carries a Mozilla signature for browser
installation. Use the [Vault threat model](apps/vault/THREAT_MODEL.md) to assess
the application's security boundaries. Keep actual vaults, emergency sheets,
pairing data and signing credentials out of source control and public issue
attachments.
