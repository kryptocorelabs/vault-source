import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZipInfo

from mozilla_amo import check_returned_payload


ADDON_ID = 'vault@kryptocorelabs'
VERSION = '1.0.0'
METADATA = {
    name: b'synthetic metadata, no signature'
    for name in ('META-INF/cose.manifest', 'META-INF/cose.sig', 'META-INF/manifest.mf',
                 'META-INF/mozilla.sf', 'META-INF/mozilla.rsa')
}


class MozillaAmoPayloadTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.submission = Path(directory.name) / 'submission.zip'
        self.xpi = Path(directory.name) / 'returned.xpi'
        self.manifest = {'version': VERSION, 'browser_specific_settings': {'gecko': {'id': ADDON_ID}}}
        self.files = {'manifest.json': json.dumps(self.manifest).encode(), 'popup.js': b'// submission'}
        self.write(self.submission, self.files)

    @staticmethod
    def write(path, files):
        with ZipFile(path, 'w') as archive:
            for name, data in files.items():
                entry = ZipInfo('test-entry')
                entry.filename = name  # Retain malformed ZIP paths on Windows as well.
                archive.writestr(entry, data)

    def check(self, addon_id=ADDON_ID, version=VERSION):
        check_returned_payload(self.submission, self.xpi, addon_id=addon_id, version=version)

    def test_payload_matches_with_reformatted_manifest(self):
        signed = {**self.files, **METADATA, 'manifest.json': json.dumps(self.manifest, indent=2).encode()}
        self.write(self.xpi, signed)
        self.check()

    def test_modified_payload_and_manifest_are_rejected(self):
        for name, value in (('popup.js', b'// changed'), ('manifest.json', b'{}')):
            with self.subTest(name=name):
                self.write(self.xpi, {**self.files, **METADATA, name: value})
                with self.assertRaisesRegex(ValueError, 'changed|Changed'):
                    self.check()

    def test_expected_version_and_id_come_from_the_caller(self):
        self.write(self.xpi, {**self.files, **METADATA})
        for addon_id, version in ((ADDON_ID, '1.0.1'), ('other@example.test', VERSION)):
            with self.subTest(addon_id=addon_id, version=version):
                with self.assertRaisesRegex(ValueError, 'Unexpected add-on ID or version'):
                    self.check(addon_id, version)

    def test_missing_payload_and_wrong_signing_metadata_are_rejected(self):
        self.write(self.xpi, {'manifest.json': self.files['manifest.json'], **METADATA})
        with self.assertRaisesRegex(ValueError, 'Missing uploaded files'):
            self.check()
        for metadata in ({}, {**METADATA, 'META-INF/unexpected': b'added'}):
            with self.subTest(metadata=metadata):
                self.write(self.xpi, {**self.files, **metadata})
                with self.assertRaisesRegex(ValueError, 'Unexpected AMO signing metadata'):
                    self.check()

    def test_unsafe_or_duplicate_archive_paths_are_rejected(self):
        for name in ('../outside', '/outside', 'C:/outside', 'nested\\file'):
            with self.subTest(name=name):
                self.write(self.xpi, {**self.files, **METADATA, name: b'unsafe'})
                with self.assertRaisesRegex(ValueError, 'Unsafe ZIP path'):
                    self.check()
        self.write(self.xpi, {**self.files, **METADATA})
        with warnings.catch_warnings(), ZipFile(self.xpi, 'a') as archive:
            warnings.simplefilter('ignore', UserWarning)
            archive.writestr('popup.js', b'duplicate')
        with self.assertRaisesRegex(ValueError, 'Duplicate ZIP entries'):
            self.check()
