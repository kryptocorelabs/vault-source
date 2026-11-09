"""Best-effort local high-water marks. No trusted hardware/server counter."""
import hashlib
import json
import os
from pathlib import Path

MAX_CACHE = 256 * 1024


def path_key(path):
    normalized = os.path.normcase(str(Path(path).resolve()))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def checked_revision(value):
    if not isinstance(value, dict) or set(value) not in (
            {'vault_id', 'epoch'}, {'vault_id', 'epoch', 'fingerprint'}):
        raise ValueError('Ungültige Tresorversion.')
    identity, epoch = value['vault_id'], value['epoch']
    if (not isinstance(identity, list) or len(identity) != 16 or
            any(type(n) is not int or not 0 <= n <= 255 for n in identity) or
            type(epoch) is not int or not 1 <= epoch <= 2**64 - 1):
        raise ValueError('Ungültige Tresorversion.')
    fingerprint = value.get('fingerprint')
    if 'fingerprint' in value and (
            not isinstance(fingerprint, list) or len(fingerprint) != 32 or
            any(type(n) is not int or not 0 <= n <= 255 for n in fingerprint)):
        raise ValueError('Ungültiger Fingerabdruck für die Tresorversion.')
    return bytes(identity).hex(), epoch, fingerprint


def load(path):
    if not path.exists():
        return {'schema': 2, 'vaults': {}, 'paths': {}}
    with path.open('rb') as file:
        raw = file.read(MAX_CACHE + 1)
    if len(raw) > MAX_CACHE:
        raise ValueError('Der lokale Versionsspeicher ist zu groß.')
    try:
        state = json.loads(raw)
    except RecursionError as error:
        raise ValueError('Ungültiger lokaler Versionsspeicher.') from error
    if not isinstance(state, dict) or set(state) != {'schema', 'vaults', 'paths'} or type(state['schema']) is not int or state['schema'] not in (1, 2):
        raise ValueError('Ungültiger lokaler Versionsspeicher.')
    if not isinstance(state['vaults'], dict) or not isinstance(state['paths'], dict):
        raise ValueError('Ungültiger lokaler Versionsspeicher.')
    if state['schema'] == 1:
        state['vaults'] = {identity: {'epoch': epoch} for identity, epoch in state['vaults'].items()}
        state['schema'] = 2
    for identity, observation in state['vaults'].items():
        if identity != identity.lower() or len(identity) != 32:
            raise ValueError('Ungültige Tresorkennung.')
        if not isinstance(observation, dict) or set(observation) not in ({'epoch'}, {'epoch', 'fingerprint'}):
            raise ValueError('Ungültiger gespeicherter Tresorstand.')
        checked_revision({'vault_id': list(bytes.fromhex(identity)), **observation})
    for key, identity in state['paths'].items():
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or not isinstance(identity, str) or identity not in state['vaults']:
            raise ValueError('Ungültiger gespeicherter Dateibezug.')
    return state


def minimum(state, path):
    identity = state['paths'].get(path_key(path))
    if identity is None and Path(path).is_file():
        # Untrusted peek selects a policy only; it never advances the cache.
        with Path(path).open('rb') as file:
            prefix = file.read(29)
        if len(prefix) == 29 and prefix[:5] == b'KCV3\0':
            identity = prefix[5:21].hex()
    if identity in state['vaults']:
        return {'vault_id': list(bytes.fromhex(identity)), **state['vaults'][identity]}
    return None


def observe(state, path, revision):
    key = path_key(path)
    if revision is None:
        if key in state['paths']:
            raise ValueError('Ein bereits geschützter Speicherort enthält ein älteres Format. Nutze eine Kopie in Rescue.')
        return False
    identity, epoch, fingerprint = checked_revision(revision)
    if key in state['paths'] and state['paths'][key] != identity:
        raise ValueError('An diesem Speicherort wurde eine andere Tresordatei erkannt.')
    previous = state['vaults'].get(identity, {})
    if epoch < previous.get('epoch', 0):
        raise ValueError('Ein älterer Tresorstand wurde erkannt. Nutze für die bewusste Rettung eine Kopie in Rescue.')
    if epoch == previous.get('epoch') and 'fingerprint' in previous and previous['fingerprint'] != fingerprint:
        raise ValueError('Zwei verschiedene Tresordateien haben dieselbe Versionsnummer. Bewahre beide Kopien auf und prüfe sie in Rescue.')
    observation = {'epoch': epoch}
    if fingerprint is not None:
        observation['fingerprint'] = fingerprint
    state['vaults'][identity] = observation
    state['paths'][key] = identity
    if len(json.dumps(state).encode()) > MAX_CACHE:
        raise ValueError('Der lokale Versionsspeicher ist voll; die Beobachtung wurde nicht gespeichert.')
    return True
