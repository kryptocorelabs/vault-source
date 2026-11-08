from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
import vault_epochs as epochs


class CacheTests(unittest.TestCase):
    def test_high_water_never_decreases_and_follows_copies(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'main.kcv'
            backup = Path(folder) / 'backup.kcv'
            cache = Path(folder) / 'cache.json'
            state = epochs.load(cache)
            rev = {'vault_id': list(range(16)), 'epoch': 7}
            self.assertIsNone(epochs.minimum(state, path))
            epochs.observe(state, path, rev)
            cache.write_text(json.dumps(state), encoding='utf-8')
            state = epochs.load(cache)
            # An unauthenticated header is a lookup hint, never an observation.
            backup.write_bytes(b'KCV3\0' + bytes(range(16)) + (999).to_bytes(8, 'big'))
            self.assertEqual(epochs.minimum(state, backup), rev)
            with self.assertRaises(ValueError):
                epochs.observe(state, backup, {**rev, 'epoch': 6})
            self.assertEqual(state['vaults'][bytes(range(16)).hex()], 7)
            with self.assertRaises(ValueError):
                epochs.observe(state, path, None)
            with self.assertRaises(ValueError):
                epochs.observe(state, path, {'vault_id': [9]*16, 'epoch': 20})
            self.assertEqual(epochs.minimum(state, path), rev)

    def test_invalid_cache_and_invalid_authenticated_revision_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cache.json'
            for data in ('[]', '{}', '{"schema":2,"vaults":{},"paths":{}}',
                         json.dumps({'schema': 1, 'vaults': {}, 'paths': {'a'*64: []}}),
                         '['*2000 + '0' + ']'*2000):
                path.write_text(data, encoding='utf-8')
                with self.assertRaises(ValueError):
                    epochs.load(path)
            for value in (None, {}, {'vault_id': [0]*16, 'epoch': True},
                          {'vault_id': [0]*15, 'epoch': 1}, {'vault_id': [0]*16, 'epoch': 2**64}):
                with self.assertRaises(ValueError):
                    epochs.checked_revision(value)


unittest.main()
