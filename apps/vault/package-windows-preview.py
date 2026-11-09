"""Package and exercise the Windows preview with separately installed Qt."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = Path("apps/vault/desktop")
BINARIES = ("kryptocore-vault.exe", "vault-firefox-host.exe", "vault_firefox_channel.dll")
WHEEL_NAMES = {"pyside6-essentials", "shiboken6", "zxcvbn"}


def output(*command):
    return subprocess.check_output(command, cwd=ROOT, encoding="utf-8").strip()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def rust_notices():
    metadata = json.loads(output(
        "cargo", "metadata", "--locked", "--format-version", "1",
        "--filter-platform", "x86_64-pc-windows-msvc",
    ))
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    packages = {package["id"]: package for package in metadata["packages"]}
    pending = [package["id"] for package in packages.values()
               if package["name"] in {"kryptocore-vault", "vault-firefox-channel"}]
    visited, files, inventory = set(), {}, []
    while pending:
        package_id = pending.pop()
        if package_id in visited:
            continue
        visited.add(package_id)
        package = packages[package_id]
        pending.extend(dep["pkg"] for dep in nodes[package_id]["deps"]
                       if any(kind["kind"] != "dev" for kind in dep["dep_kinds"]))
        if package["source"] is None:
            continue
        directory = Path(package["manifest_path"]).parent
        notices = {file for file in directory.iterdir() if file.is_file()
                   and file.name.upper().startswith(("LICENSE", "COPYING", "COPYRIGHT", "NOTICE"))}
        if package["license_file"]:
            notices.add(directory / package["license_file"])
        if not notices or not package["license"]:
            raise SystemExit(f"Missing license information for {package['name']}")
        prefix = f"third-party/rust/{package['name']}-{package['version']}"
        for file in notices:
            files[f"{prefix}/{file.name}"] = file.read_bytes()
        inventory.append("\t".join((package["name"], package["version"], package["license"], prefix)))
    files["third-party/RUST-DEPENDENCIES.tsv"] = (
        "name\tversion\tlicense\tnotices\n" + "\n".join(sorted(inventory)) + "\n"
    ).encode()
    runtime = Path(output("rustc", "--print", "sysroot")) / "share/doc/rust"
    for file in [runtime / "COPYRIGHT-library.html", *sorted((runtime / "licenses").glob("*"))]:
        if file.is_file():
            files[f"third-party/rust-runtime/{file.relative_to(runtime).as_posix()}"] = file.read_bytes()
    if "third-party/rust-runtime/COPYRIGHT-library.html" not in files:
        raise SystemExit("Missing Rust standard library copyright information.")
    return files


def package(output_directory, version):
    worker_dir = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "release"
    files = rust_notices()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    for name in ("Setup.cmd", "Start-Vault.cmd"):
        files[name] = (ROOT / DESKTOP / name).read_bytes()
    for name in ("vault.pyw", "vault_epochs.py", "firefox_channel.py",
                 "emblem.png", "vault-emblem.png", "core-emblem.png"):
        files[f"{DESKTOP.as_posix()}/{name}"] = (ROOT / DESKTOP / name).read_bytes()
    lock = (ROOT / DESKTOP / "requirements-onefile-windows.lock").read_text(encoding="utf-8")
    wheels = [line for line in lock.splitlines() if line.split("==")[0].lower() in WHEEL_NAMES]
    if len(wheels) != len(WHEEL_NAMES):
        raise SystemExit("The Windows dependency lock is incomplete.")
    files["requirements.txt"] = ("\n".join(wheels) + "\n").encode()
    for name in ("GPL-3.0-only.txt", "LGPL-3.0-only.txt"):
        files[f"third-party/qt/{name}"] = (
            ROOT / "third-party/licenses/Qt-6.10.3" / name
        ).read_bytes()
    files["THIRD_PARTY_NOTICES.txt"] = (
        "See third-party/RUST-DEPENDENCIES.tsv for the linked Rust dependencies.\n"
        "The archive includes no Python or Qt runtime. Setup downloads unmodified wheels.\n"
        "Qt, PySide6 Essentials and Shiboken are used under LGPLv3. They can be replaced\n"
        "in .venv313 with compatible builds. The LGPL and GPL texts are in third-party/qt.\n"
        "Qt sources and instructions are at https://doc.qt.io/qtforpython-6/building_from_source/windows.html\n"
        "zxcvbn is separately installed under MIT.\n"
    ).encode()
    files["START.txt"] = (
        f"KryptoCore Vault {version} for Windows x64\n"
        "Install Python 3.13 x64, run Setup.cmd, then open Start-Vault.cmd.\n"
        "Use sample data and keep an independent backup and the recovery sheet.\n"
        "Recovery reset rotates the encryption seed. Earlier backups retain their original access.\n"
    ).encode()
    files["FORMAT-LIFECYCLE.md"] = (ROOT / "apps/vault/FORMAT-LIFECYCLE.md").read_bytes()
    source = os.environ.get("GITHUB_SHA")
    if source and source != output("git", "rev-parse", "HEAD"):
        raise SystemExit("Source commit does not match the build request.")
    binary_digests = {}
    for name in BINARIES:
        content = (worker_dir / name).read_bytes()
        files[f"{DESKTOP.as_posix()}/{name}"] = content
        binary_digests[name] = sha256(content)
    files["RELEASE_MANIFEST.json"] = (json.dumps(dict(
        product="vault", version=version, target="windows-x86_64", source_commit=source,
        binaries_sha256=binary_digests, recovery_reset_rotates_seed=True, new_vault_format="KCV4",
    ), indent=2, sort_keys=True) + "\n").encode()
    archive = output_directory / f"KryptoCore-Vault-{version}-windows-x64-desktop.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in sorted(files.items()):
            bundle.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_DEFLATED)
    return archive


def verify(archive, work):
    with tempfile.TemporaryDirectory(prefix="vault-preview-", dir=work) as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
        test = extracted / "apps/vault/tests/desktop-workflow.py"
        test.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "apps/vault/tests/desktop-workflow.py", test)
        env = {key: value for key, value in os.environ.items()
               if key not in {"CARGO_TARGET_DIR", "KCV_TEST_SCREENSHOTS", "PYTHONPATH"}}
        subprocess.run([sys.executable, str(test)], cwd=extracted, env=env, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    if sysconfig.get_platform() != "win-amd64" or sys.version_info[:2] != (3, 13):
        parser.error("Run on Windows x64 with Python 3.13 and the locked desktop dependencies.")
    if not re.fullmatch(r"\d+\.\d+\.\d+-preview\.\d+", args.version):
        parser.error("Expected a version like 0.1.0-preview.4.")
    args.output.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    archive = package(args.output, args.version)
    verify(archive, args.work)
    print(f"Validated extracted preview {archive.name} ({sha256(archive.read_bytes())}).")


if __name__ == "__main__":
    main()
