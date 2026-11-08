# Third-party notices

Reviewed 2026-11-04. This file covers the MIT-licensed KryptoCore library,
the Vault Windows x64 Desktop Preview 7 and 8 review archives, and the
Firefox extension 0.1.10.

[Dependency inventory](third-party/DEPENDENCIES.tsv) lists resolved direct and
transitive dependencies by scope. Rust versions and checksums come from the
locked Cargo graphs. The final column points to the original copyright,
license and attribution files in [third-party/licenses](third-party/licenses/).
Keep the files referenced by the applicable inventory with a redistribution.
The [Firefox lint dependency snapshot](third-party/FIREFOX-LINT-TOOLING.tsv)
covers the local web-ext 10.8.0 tool and its npm dependencies. That toolchain
is separate from the extension ZIP. CI runner images, toolchain channels,
GitHub Action major tags, cargo-audit and cargo-fuzz are floating references
in the workflow and have no single exact historical version in the source.

## KryptoCore

The project source is covered by the [KryptoCore MIT license](LICENSE),
Copyright (c) 2026 KryptoCore contributors. The resolved Rust graph uses
permissive license terms, including a permissive option for dual- or
triple-licensed crates. Retain the upstream license and copyright notices.
Where an expression uses **AND**, preserve both sets of notices. The lockfile
includes target-specific entries and test dependencies. The fuzz graph is
separate and includes the libFuzzer build dependencies.

The Python reference imports argon2-cffi and PyNaCl. Its wheel contains the
KryptoCore Python code. pip installs those dependencies separately. The
inventory records the versions verified in the local Windows CPython 3.9
environment, including the transitive packages and identified native components.
The ranges in `pyproject.toml` and the GitHub Actions workflow permit different
resolutions. The snapshot does not pin future installs or identify every
previous runner image. Record the installer report and native component
attribution again before distributing a Python dependency bundle.

## Vault Windows desktop

The Windows archive includes the KryptoCore library in the Rust application.
It carries a copy of the [KryptoCore MIT license](third-party/licenses/KryptoCore-0.1.0/LICENSE)
and the original Rust crate notices. The Windows inventory includes Cargo build dependencies and
procedural macros for traceability, as well as the runtime dependencies.
The Rust toolchain's copyright and license notices are included for the linked
standard library and runtime. The Microsoft C/C++ runtime DLLs and CPython
are loaded from the installed system or Python environment. The archive
does not contain the Visual C++ Redistributable or a Python installer.

### Qt for Python

**Vault uses Qt 6.10.3, PySide6-Essentials 6.10.3 and Shiboken6 6.10.3
under LGPLv3 for the libraries Vault uses.** Qt is copyright The Qt Company
Ltd. and other contributors. Read the
[LGPLv3](third-party/licenses/Qt-6.10.3/LGPL-3.0-only.txt) and the
[GPLv3](third-party/licenses/Qt-6.10.3/GPL-3.0-only.txt) it incorporates.
For additional upstream notices see
[Qt third-party code](https://doc.qt.io/qt-6.10/licenses-used-in-qt.html)
and [Qt for Python third-party code](https://doc.qt.io/qtforpython-6.10/licenses.html).

`Setup.cmd` installs the unmodified Qt wheels and zxcvbn 4.5.0 from the configured
Python package index into `.venv313`. The Windows archive has no Qt or zxcvbn
wheels, DLLs or source copies. The compiled desktop module imports the
bindings dynamically. The build environment also had Qt for Python 6.12.0
installed. The runtime versions above are the ones specified in the archive
and exercised with the preview.
The [Windows wheel binary inventory](third-party/QT-WINDOWS-WHEEL-BINARIES.tsv)
records all installed Qt and Shiboken DLLs and Python extensions in the
tested environment, with PE versions where available and SHA-256 hashes.
This includes the Microsoft runtime files delivered by those wheels. The
binary inventory does not map every statically incorporated Qt component
to its exact source revision. That mapping remains part of any future
review of a Vault package that conveys the wheels itself.

The library source is available from the versioned Qt repositories. See the
[Qt 6.10.3 source instructions](https://doc.qt.io/qtforpython-6.10/overviews/qtdoc-getting-sources-from-git.html)
and [PySide build instructions for Windows](https://doc.qt.io/qtforpython-6/building_from_source/windows.html).

To use a compatible modified Qt library, replace the PySide6-Essentials and
Shiboken6 wheels in the local environment, then start Vault. For example,
run the following from the extracted folder with the paths to your compatible
Windows x64 wheels. Running `Setup.cmd` again can restore the pinned packages.

```bat
.venv313\Scripts\python.exe -m pip install --force-reinstall --no-deps <PySide6-wheel> <Shiboken6-wheel>
```

The library terms permit modifying the LGPL libraries and reverse engineering
the combined work to debug those modifications. Any Vault distribution terms
must preserve those permissions. If KryptoCoreLabs starts conveying the Qt
wheels or copies of the libraries itself, provide the complete corresponding
library source and build material for the exact binaries under an applicable
LGPL/GPL source-delivery method. A third-party upstream link alone is not the
publisher's own source offer. Treat a new Qt module, statically linked Qt,
or a bundled installer as a separate review. [Qt open-source obligations](https://www.qt.io/development/open-source-lgpl-obligations)

### Nuitka

The Vault `.pyd` was built with Nuitka 4.3.4. Its embedded runtime code uses
the [Nuitka Runtime Library Exception 1.0](third-party/licenses/Nuitka-4.3.4/LICENSE-RUNTIME.txt)
with [AGPLv3](third-party/licenses/Nuitka-4.3.4/LICENSE.txt). The exception
allows the generated combination with an independent application to be
conveyed on terms of the publisher's choice. The compiler itself retains
its original terms. The archive contains the compiled output and
[Nuitka's copyright notice](third-party/licenses/Nuitka-4.3.4/NOTICE.txt).
The [matching upstream compiler source](https://pypi.org/project/Nuitka/4.3.4/#files)
is identified separately. If the compiler or a modified compiler is
redistributed separately, review the AGPL corresponding-source obligations
for that distribution. [Exact upstream exception](https://github.com/Nuitka/Nuitka/blob/4.3.4/LICENSE-RUNTIME.txt)

## Firefox extension

Version 0.1.10 contains project-owned JavaScript, HTML, an SVG icon and
the manifest. There is no third-party package in the ZIP. Firefox provides
the WebExtensions and Web Crypto APIs. The Windows companion is distributed
separately. The signing ZIP already contains the readable extension source
required for review. A reviewable source package and an open-source license
are separate decisions. [Mozilla add-on policies](https://www.mozilla.org/en-US/about/legal/amo-policies/)

## Distribution decisions

| Component | Source-code consequence for the reviewed distribution |
| --- | --- |
| Core and linked Rust dependencies | Core remains available under MIT. Retain notices for the resolved dependencies. The selected permissive options do not require disclosure of Vault application source. |
| zxcvbn | The unmodified separately installed package is MIT. Retain its notices if it is conveyed with a later release. |
| Qt in the separate-install desktop | Keep the libraries replaceable and the LGPL/GPL texts and notices with the desktop. If the libraries are conveyed by the project, arrange matching library source delivery and verify the full contents of those wheels. |
| Nuitka 4.3.4 generated runtime | The Runtime Library Exception covers independent application output for the marked files. Compiler redistribution is a separate AGPL case. |
| Firefox 0.1.10 | Deliver the readable extension files to Mozilla for review. This package contains no library requiring publication of Vault desktop source. |

The reviewed desktop archive is a test preview. Trademark findings and the
release hold are recorded in [TRADEMARK_REVIEW.md](TRADEMARK_REVIEW.md).

## Vault migration fingerprint

Development Vault builds directly use RustCrypto `sha2` 0.10.9 (MIT OR Apache-2.0) to bind an import preview to the selected file bytes. This is not a new vault encryption or KDF profile. The resolved checksum is recorded in Cargo.lock and the dependency inventory. Original license texts: [MIT](third-party/licenses/sha2-0.10.9/LICENSE-MIT) and [Apache-2.0](third-party/licenses/sha2-0.10.9/LICENSE-APACHE).
