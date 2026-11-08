"""Exercise actual, independently built Vault and Rescue workers; synthetic data only."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--vault', type=Path, required=True)
parser.add_argument('--rescue', type=Path, required=True)
args = parser.parse_args()
def native(path):
    if os.name == 'nt' and path.suffix != '.exe':
        path = path.with_name(path.name + '.exe')
    return path.resolve()
vault_exe, rescue_exe = native(args.vault), native(args.rescue)
password = 'Synthetic vault interop password'
replacement = 'Synthetic replacement vault password'
recovery = '0123456789abcdef' * 4
new_recovery = 'abcdef0123456789' * 4
site = 'https://example.invalid'
username = 'Synthetic Grüße 🗝️'
login_secret = 'Synthetic secret with \\ and " and newline\n終'


class Vault:
    def __init__(self):
        self.process = subprocess.Popen([str(vault_exe), 'desktop-session'], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

    def call(self, expect=True, **request):
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        reply = json.loads(self.process.stdout.readline())
        assert ('error' not in reply) == expect, 'Unexpected Vault success/failure'
        return reply

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=20)
        assert self.process.returncode == 0
        self.process.stdout.close()
        self.process.stderr.close()


def export(source, target, secret, route='password', expect=True):
    before = source.read_bytes()
    request = json.dumps(dict(action='recover', input=str(source), output=str(target),
                              credential=route, confirm_plaintext=True)).encode()
    parts = (request, secret.encode(), b'')
    frame = b''.join(struct.pack('<I', len(part)) + part for part in parts)
    result = subprocess.run([str(rescue_exe)], input=frame, capture_output=True, timeout=45, check=True)
    reply = json.loads(result.stdout)
    assert reply['ok'] == expect, f'Unexpected Rescue result: {source.name}, {route}, expected success={expect}'
    assert source.read_bytes() == before, 'Rescue modified its source'
    if expect:
        records = json.loads(target.read_text(encoding='utf-8'))
        assert records == [dict(origin=site, username=username, password=login_secret)]
    else:
        assert not target.exists(), 'Rejected export published output'


with tempfile.TemporaryDirectory(prefix='vault-rescue-interop-') as folder:
    # macOS's default temporary directory can include /var -> /private/var.
    # Use the actual path; Rescue deliberately rejects linked output ancestors.
    folder = Path(folder).resolve()
    for label, key in [('KCV1', None), ('KCV2', recovery)]:
        file = folder / (label + '.kcv')
        client = Vault()
        client.call(action='open', path=str(file), password=password, create=True, recovery=key)
        client.call(action='put', site=site, username=username, password=login_secret)
        snapshot = folder / (label + '-backup.kcv')
        client.call(action='backup', destination=str(snapshot))
        assert file.read_bytes() == snapshot.read_bytes()
        export(file, folder/(label+'-password.json'), password)
        if label == 'KCV1' and os.name == 'posix':
            alias = folder/'linked-output'
            alias.symlink_to(folder, target_is_directory=True)
            export(file, alias/'rejected-linked-output.json', password, expect=False)
            assert not (folder/'rejected-linked-output.json').exists()
        if key:
            export(snapshot, folder/'KCV2-recovery.json', recovery, 'recovery_key')
        client.close()

    source = folder/'KCV2.kcv'
    source_bytes = source.read_bytes()
    epoch_file = folder/'KCV3.kcv'
    client = Vault()
    client.call(action='open', path=str(source), password=password, create=False)
    first = client.call(action='enable_epoch', destination=str(epoch_file))['revision']
    assert first['epoch'] == 1 and source.read_bytes() == source_bytes
    old_epoch = epoch_file.read_bytes()
    second = client.call(action='put', previous=site, site=site, username=username, password=login_secret)['revision']
    assert second['epoch'] == 2 and second['vault_id'] == first['vault_id']
    export(epoch_file, folder/'KCV3-password.json', password)
    export(epoch_file, folder/'KCV3-recovery.json', recovery, 'recovery_key')
    client.close()

    client = Vault()
    third = client.call(action='recover', path=str(epoch_file), recovery=recovery, password=replacement,
                        minimum_revision=second)['revision']
    assert third['epoch'] == 3 and third['vault_id'] == first['vault_id']
    export(epoch_file, folder/'KCV3-reset-password.json', replacement)
    export(epoch_file, folder/'KCV3-reset-recovery.json', recovery, 'recovery_key')
    export(epoch_file, folder/'rejected-old-password.json', password, expect=False)
    fourth = client.call(action='enable_recovery', recovery=new_recovery)['revision']
    assert fourth['epoch'] == 4 and fourth['vault_id'] == first['vault_id']
    export(epoch_file, folder/'KCV3-new-recovery.json', new_recovery, 'recovery_key')
    export(epoch_file, folder/'rejected-old-recovery.json', recovery, 'recovery_key', expect=False)
    latest = epoch_file.read_bytes()

    # In-session rollback: no reveal, overwrite, or backup of the stale file.
    epoch_file.write_bytes(old_epoch)
    client.call(action='reveal', site=site, expect=False)
    client.call(action='put', site='https://other.invalid', username='Synthetic', password='Synthetic', expect=False)
    rejected_backup = folder/'rejected-backup.kcv'
    client.call(action='backup', destination=str(rejected_backup), expect=False)
    assert not rejected_backup.exists() and epoch_file.read_bytes() == old_epoch
    client.close()
    # Rescue intentionally permits old backups, without a freshness claim.
    export(epoch_file, folder/'old-backup.json', password)

    for replaced in (old_epoch, source_bytes):
        epoch_file.write_bytes(replaced)
        client = Vault()
        client.call(action='open', path=str(epoch_file), password=password, create=False, minimum_revision=fourth, expect=False)
        client.call(action='recover', path=str(epoch_file), recovery=recovery, password=replacement,
                    minimum_revision=fourth, expect=False)
        assert epoch_file.read_bytes() == replaced
        client.close()

    damaged = bytearray(latest)
    damaged[28] ^= 1
    epoch_file.write_bytes(damaged)
    export(epoch_file, folder/'tampered-epoch.json', replacement, expect=False)

print('PASS: real Vault/Rescue KCV1/KCV2/KCV3 exports, Unicode, backups, re-key, recovery renewal, rollback/downgrade and tamper rejection; sources preserved.')
