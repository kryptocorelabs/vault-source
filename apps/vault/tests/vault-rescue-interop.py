"""Exercise actual, independently built Vault and Rescue workers; synthetic data only."""
import argparse
import hashlib
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
    observed = epoch_file.read_bytes()
    assert bytes(second['fingerprint']).hex() == hashlib.sha256(observed).hexdigest()
    fork = folder/'KCV3-fork.kcv'
    fork.write_bytes(old_epoch)
    other = Vault()
    other.call(action='open', path=str(fork), password=password, create=False, minimum_revision=first)
    conflict = other.call(action='put', previous=site, site=site, username='Synthetic fork',
                          password='Synthetic fork password')['revision']
    other.close()
    assert conflict['epoch'] == second['epoch'] and conflict['fingerprint'] != second['fingerprint']
    fork_bytes = fork.read_bytes()
    epoch_file.write_bytes(fork_bytes)
    rejected = client.call(action='reveal', site=site, expect=False)
    assert rejected['code'] == 'revision_rejected' and 'password' not in rejected
    assert epoch_file.read_bytes() == fork_bytes
    epoch_file.write_bytes(observed)
    assert client.call(action='reveal', site=site)['password'] == login_secret
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
    client.call(action='health', expect=False)
    client.call(action='file_digest', expect=False)
    client.call(action='export', destination=str(folder/'rejected-stale.json'), confirm_plaintext=True, expect=False)
    assert not (folder/'rejected-stale.json').exists()
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

    # Migration uses the real Vault producer and an independently built old Rescue
    # reader: both versioned exports and existing Rescue arrays must round-trip.
    transfer = folder/'vault-export.json'
    client = Vault()
    client.call(action='health', expect=False)
    client.call(action='export', destination=str(transfer), confirm_plaintext=True, expect=False)
    client.call(action='open', path=str(source), password=password, create=False)
    health = client.call(action='health')
    assert health['entry_count'] == 1 and health['format_version'] == 2 and health['recovery_available']
    assert type(health['file_modified_unix']) is int
    client.call(action='export', destination=str(transfer), confirm_plaintext=False, expect=False)
    assert not transfer.exists()
    result = client.call(action='export', destination=str(transfer), confirm_plaintext=True)
    assert result['exported_entries'] == 1 and login_secret not in json.dumps(result)
    plain = transfer.read_bytes()
    assert json.loads(plain) == dict(format='kryptocore-vault-export', schema_version=1,
        entries=[dict(origin=site, username=username, password=login_secret)])
    client.call(action='export', destination=str(transfer), confirm_plaintext=True, expect=False)
    client.call(action='export', destination=str(source), confirm_plaintext=True, expect=False)
    assert source.read_bytes() == source_bytes and transfer.read_bytes() == plain
    if os.name == 'posix':
        client.call(action='export', destination=str(folder/'linked-output/rejected-desktop.json'), confirm_plaintext=True, expect=False)
        assert not (folder/'rejected-desktop.json').exists()
        assert transfer.stat().st_mode & 0o777 == 0o600
    client.close()

    client = Vault()
    client.call(action='open', path=str(folder/'KCV1.kcv'), password=password, create=False)
    health = client.call(action='health')
    assert health['format_version'] == 1 and not health['recovery_available']
    client.close()
    epoch_file.write_bytes(latest)
    client = Vault()
    client.call(action='open', path=str(epoch_file), password=replacement, create=False, minimum_revision=fourth)
    health = client.call(action='health')
    assert health['format_version'] == 3 and health['recovery_available'] and health['revision'] == fourth
    client.close()

    client = Vault()
    preview = client.call(action='inspect_import', source=str(transfer))
    assert preview['entry_count'] == 1 and len(preview['digest']) == 64 and login_secret not in json.dumps(preview)
    client.call(action='inspect_import', source=str(folder), expect=False)
    if os.name == 'posix':
        fifo = folder/'special.json'
        os.mkfifo(fifo)
        client.call(action='inspect_import', source=str(fifo), expect=False)
        input_alias = folder/'linked-input.json'
        input_alias.symlink_to(transfer)
        client.call(action='inspect_import', source=str(input_alias), expect=False)
    rejected = folder/'rejected-import.kcv'
    import_request = dict(action='import', source=str(transfer), expected_digest=preview['digest'],
        path=str(rejected), password=replacement, recovery=new_recovery)
    transfer.write_bytes(plain + b'\n')
    client.call(**import_request, expect=False)
    assert not rejected.exists()
    transfer.write_bytes(plain)
    for change in (dict(password='short'), dict(recovery='invalid'), dict(expected_digest='0'*64),
                   dict(minimum_revision=fourth)):
        client.call(**{**import_request, **change}, expect=False)
        assert not rejected.exists()
    client.call(**{**import_request, 'path': str(source)}, expect=False)
    assert source.read_bytes() == source_bytes

    invalid = folder/'invalid-export.json'
    record = dict(origin=site, username=username, password=login_secret)
    malformed = [b'not JSON', b'\xff', b'['*150+b']'*150,
        json.dumps({'format':'kryptocore-vault-export', 'schema_version':2, 'entries':[record]}).encode(),
        json.dumps({'format':'kryptocore-vault-export', 'schema_version':1, 'entries':[record], 'extra':True}).encode(),
        json.dumps([{'origin':site, 'username':username}]).encode(),
        json.dumps([{**record, 'password':''}]).encode(),
        json.dumps([{**record, 'origin':'https://user:secret@example.invalid'}]).encode(),
        json.dumps([record, {**record, 'origin':site+'/different-path'}]).encode(),
        json.dumps([{**record, 'password':'X'*(4*1024*1024)}]).encode(),
        b' '*(16*1024*1024+1)]
    for contents in malformed:
        invalid.write_bytes(contents)
        failure = client.call(action='inspect_import', source=str(invalid), expect=False)
        assert login_secret not in json.dumps(failure)
        client.call(**{**import_request, 'source': str(invalid)}, expect=False)
        assert not rejected.exists() and source.read_bytes() == source_bytes
    imported = folder/'imported-vault.kcv'
    client.call(**{**import_request, 'path': str(imported)})
    health = client.call(action='health')
    assert health['entry_count'] == 1 and health['format_version'] == 2 and health['recovery_available']
    assert imported.read_bytes().startswith(b'KCV2\0') and imported.read_bytes() != source_bytes
    assert transfer.read_bytes() == plain and source.read_bytes() == source_bytes
    export(imported, folder/'imported-password.json', replacement)
    export(imported, folder/'imported-recovery.json', new_recovery, 'recovery_key')
    export(imported, folder/'imported-old-password.json', password, expect=False)
    client.close()
    rescue_array = folder/'KCV2-recovery.json'
    rescue_bytes = rescue_array.read_bytes()
    client = Vault()
    preview = client.call(action='inspect_import', source=str(rescue_array))
    client.call(**{**import_request, 'source':str(rescue_array), 'expected_digest':preview['digest'],
                  'path':str(folder/'imported-rescue.kcv')})
    client.close()
    export(folder/'imported-rescue.kcv', folder/'rescue-array-roundtrip.json', replacement)
    assert rescue_array.read_bytes() == rescue_bytes

    # Verify the credential/key distinction, exact snapshot digests and old-reader
    # compatibility using the real workers for all three supported profiles.
    changed_password = 'Synthetic ordinary changed password'
    rotated_password = 'Synthetic explicitly rotated password'
    fresh_recovery = 'fedcba9876543210' * 4
    for profile, original_bytes, previous_password, previous_recovery in (
        (1, (folder/'KCV1.kcv').read_bytes(), password, None),
        (2, source_bytes, password, recovery),
        (3, latest, replacement, new_recovery),
    ):
        candidate = folder/f'password-v{profile}.kcv'
        candidate.write_bytes(original_bytes)
        old_copy = folder/f'password-v{profile}-old.kcv'
        old_copy.write_bytes(original_bytes)
        client = Vault()
        client.call(action='change_password', current_password=previous_password, password=changed_password,
                    rotate_key=False, expect=False)
        client.call(action='open', path=str(candidate), password=previous_password, create=False)
        initial = client.call(action='file_digest')
        assert initial['sha256'] == hashlib.sha256(original_bytes).hexdigest() and initial['bytes'] == len(original_bytes)
        receipt = folder/f'password-v{profile}.sha256'
        client.call(action='file_digest', destination=str(receipt), expect=False)
        assert not receipt.exists()
        client.call(action='file_digest', destination=str(receipt), expected_sha256=initial['sha256'].upper())
        assert receipt.read_text(encoding='ascii') == initial['sha256']+'\n'
        client.call(action='file_digest', destination=str(receipt), expected_sha256=initial['sha256'], expect=False)
        client.call(action='file_digest', destination=str(candidate), expected_sha256=initial['sha256'], expect=False)
        for expected in ('wrong-format', '0'*64):
            client.call(action='file_digest', destination=str(folder/f'rejected-hash-{profile}.sha256'),
                        expected_sha256=expected, expect=False)
        if os.name == 'posix':
            client.call(action='file_digest', destination=str(folder/f'linked-output/rejected-hash-{profile}.sha256'),
                        expected_sha256=initial['sha256'], expect=False)
            assert not (folder/f'rejected-hash-{profile}.sha256').exists()
        assert candidate.read_bytes() == original_bytes
        for change in (dict(current_password='wrong'), dict(password='short'), dict(password=previous_password)):
            client.call(**{**dict(action='change_password', current_password=previous_password,
                                  password=changed_password, rotate_key=False), **change}, expect=False)
            assert candidate.read_bytes() == original_bytes
        quick = client.call(action='change_password', current_password=previous_password,
                            password=changed_password, rotate_key=False)
        assert quick['password_changed'] and quick['key_rotated'] == (profile == 1)
        assert not quick['new_recovery'] and previous_password not in json.dumps(quick)
        export(candidate, folder/f'password-v{profile}-quick.json', changed_password)
        export(candidate, folder/f'password-v{profile}-old-password.json', previous_password, expect=False)
        if previous_recovery:
            export(candidate, folder/f'password-v{profile}-kept-recovery.json', previous_recovery, 'recovery_key')
        after_quick = candidate.read_bytes()
        current_hash = client.call(action='file_digest')['sha256']
        assert current_hash == hashlib.sha256(after_quick).hexdigest() and current_hash != initial['sha256']
        stale_receipt = folder/f'password-v{profile}-stale.sha256'
        client.call(action='file_digest', destination=str(stale_receipt), expected_sha256=initial['sha256'], expect=False)
        assert not stale_receipt.exists()
        if profile >= 2:
            client.call(action='change_password', current_password=changed_password, password=rotated_password,
                        rotate_key=True, expect=False)
            assert candidate.read_bytes() == after_quick
        rotated = client.call(action='change_password', current_password=changed_password, password=rotated_password,
                              rotate_key=True, new_recovery=fresh_recovery if profile >= 2 else None)
        assert rotated['key_rotated'] and rotated['new_recovery'] == (profile >= 2)
        if profile == 3:
            assert quick['revision']['epoch'] == 5 and rotated['revision']['epoch'] == 6
            assert quick['revision']['vault_id'] == rotated['revision']['vault_id'] == fourth['vault_id']
        assert client.call(action='health')['format_version'] == profile
        export(candidate, folder/f'password-v{profile}-rotated.json', rotated_password)
        export(candidate, folder/f'password-v{profile}-superseded.json', changed_password, expect=False)
        if previous_recovery:
            export(candidate, folder/f'password-v{profile}-revoked-recovery.json', previous_recovery, 'recovery_key', expect=False)
            export(candidate, folder/f'password-v{profile}-new-recovery.json', fresh_recovery, 'recovery_key')
        export(old_copy, folder/f'password-v{profile}-old-copy-readable.json', previous_password)
        assert old_copy.read_bytes() == original_bytes
        assert receipt.read_text(encoding='ascii') == initial['sha256']+'\n'
        assert not (folder/f'rejected-hash-{profile}.sha256').exists()
        client.close()

print('PASS: real Vault/Rescue profiles, migration/health, password/key rotation, exact file digests and protected receipts, old-copy readability and negative cases; sources preserved.')
