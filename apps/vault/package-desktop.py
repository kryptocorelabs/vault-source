"""Build on the target OS. Produces evaluation artifacts, not a signed release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
output, work = args.output.resolve(), args.work.resolve()
output.mkdir(parents=True, exist_ok=True)
work.mkdir(parents=True, exist_ok=True)
system = {'win32': 'windows', 'linux': 'linux', 'darwin': 'macos'}.get(sys.platform)
machine = {'AMD64': 'x86_64', 'x86_64': 'x86_64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(platform.machine())
if system is None or machine is None or sys.version_info[:2] != (3, 13):
    raise SystemExit('Build on supported native Windows/Linux/macOS with Python 3.13 x64/arm64.')
target = system + '-' + machine
suffix = '.exe' if system == 'windows' else ''
packages = ['-p', 'kryptocore-vault']
if system == 'windows':
    packages += ['-p', 'vault-firefox-channel']
subprocess.run(['cargo', 'build', '--locked', '--release', *packages], cwd=root, check=True)
native = Path(os.environ.get('CARGO_TARGET_DIR', root / 'target')).resolve() / 'release'
desktop = root / 'apps/vault/desktop'
build_output = work / 'dist'
options = [sys.executable, '-m', 'PyInstaller', '--windowed', '--noupx', '--noconfirm', '--clean',
           '--name', 'KryptoCore-Vault', '--distpath', str(build_output), '--workpath', str(work / 'build'),
           '--specpath', str(work), '--onedir' if system == 'macos' else '--onefile']
for name in ('emblem.png', 'vault-emblem.png'):
    options += ['--add-data', str(desktop / name) + os.pathsep + '.']
binaries = ['kryptocore-vault' + suffix]
if system == 'windows':
    binaries += ['vault-firefox-host.exe', 'vault_firefox_channel.dll']
for name in binaries:
    options += ['--add-binary', str(native / name) + os.pathsep + '.']
if system == 'macos':
    options += ['--osx-bundle-identifier', 'org.kryptocorelabs.vault']
build_env = dict(os.environ)
for name in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH'):
    build_env.pop(name, None)
build_env['PYINSTALLER_CONFIG_DIR'] = str(work / 'pyinstaller-cache')
build_env['PATH'] = os.pathsep.join([str(Path(sys.executable).parent), str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot']]) if system == 'windows' else '/usr/bin:/bin:/usr/sbin:/sbin'
subprocess.run([*options, str(desktop / 'vault.pyw')], cwd=root, env=build_env, check=True)
application = build_output / ('KryptoCore-Vault.app' if system == 'macos' else 'KryptoCore-Vault' + suffix)
executable = application / 'Contents/MacOS/KryptoCore-Vault' if system == 'macos' else application
with tempfile.TemporaryDirectory(prefix='vault-portable-check-') as isolated:
    env = dict(os.environ)
    for name in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        env.pop(name, None)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PATH'] = os.pathsep.join([str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot']]) if system == 'windows' else '/usr/bin:/bin'
    subprocess.run([str(executable), '--verify-bundle'], cwd=isolated, env=env, check=True, timeout=120)
stage = work / 'package'
stage.mkdir(exist_ok=True)
destination = stage / application.name
if destination.exists():
    raise SystemExit('Choose a fresh work directory; previous package exists.')
if application.is_dir():
    shutil.copytree(application, destination, symlinks=True)
else:
    shutil.copy2(application, destination)
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
    shutil.copy2(root / name, stage / name)
shutil.copytree(root / 'third-party', stage / 'third-party')
(stage / 'BUILD-NOTES.txt').write_text(
    'Unreleased native evaluation build. No publisher signing/notarization or independent audit.\n'
    'Firefox pairing is Windows-only. Linux/macOS lock on focus loss and unexpected timer gaps.\n'
    'Linux needs a compatible glibc/desktop; macOS packaging is native to the build architecture.\n'
    'Historical third-party notices are not a new Qt/LGPL compliance certification;\n'
    'platform-specific attribution and matching-source/relinking review remain release gates.\n', encoding='utf-8')
archive = output / ('KryptoCore-Vault-' + target + ('.tar.gz' if system == 'linux' else '.zip'))
if system == 'macos':
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(stage), str(archive)], check=True)
elif system == 'linux':
    with tarfile.open(archive, 'w:gz') as package:
        package.add(stage, arcname='KryptoCore-Vault')
else:
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, strict_timestamps=False) as package:
        for file in stage.rglob('*'):
            if file.is_file():
                package.write(file, 'KryptoCore-Vault/' + file.relative_to(stage).as_posix())
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
(output / ('BUILD-' + target + '.json')).write_text(json.dumps(dict(
    target=target, source_commit=os.environ.get('GITHUB_SHA', 'local-working-tree'),
    python=platform.python_version(), archive=archive.name, sha256=digest,
    executable_only_smoke_passed=True, publisher_signed=False,
    firefox_pairing=system == 'windows', clean_machine_tested=False), indent=2) + '\n', encoding='utf-8')
print('Built and smoke-tested:', archive)
