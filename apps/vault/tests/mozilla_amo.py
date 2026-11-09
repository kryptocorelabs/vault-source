"""Check the package returned by Mozilla against the exact submission ZIP."""

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile


_AMO_METADATA = {
    'META-INF/cose.manifest',
    'META-INF/cose.sig',
    'META-INF/manifest.mf',
    'META-INF/mozilla.sf',
    'META-INF/mozilla.rsa',
}


def _payload_names(archive: ZipFile) -> set[str]:
    entries = archive.infolist()
    names = {entry.filename for entry in entries}
    if len(names) != len(entries):
        raise ValueError('Duplicate ZIP entries')
    if any(
        '\\' in name or '\x00' in name or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute()
        or '..' in PurePosixPath(name).parts
        for name in (entry.orig_filename for entry in entries)
    ):
        raise ValueError('Unsafe ZIP path')
    if sum(entry.file_size for entry in entries) >= 16 * 1024 * 1024:
        raise ValueError('Unexpected ZIP size')
    return {entry.filename for entry in entries if not entry.is_dir()}


def check_returned_payload(
    submission: Path, returned_xpi: Path, *, addon_id: str, version: str
) -> None:
    """Check the AMO hand-off. Release Firefox checks signature trust separately."""
    with ZipFile(submission) as original, ZipFile(returned_xpi) as signed:
        reference = _payload_names(original)
        actual = _payload_names(signed)
        if reference - actual:
            raise ValueError('Missing uploaded files')
        if reference & _AMO_METADATA or actual - reference != _AMO_METADATA:
            raise ValueError('Unexpected AMO signing metadata')
        if 'manifest.json' not in reference:
            raise ValueError('Missing add-on manifest')

        manifest = json.loads(signed.read('manifest.json'))
        if manifest != json.loads(original.read('manifest.json')):
            raise ValueError('Manifest content changed')
        if manifest['version'] != version or manifest['browser_specific_settings']['gecko']['id'] != addon_id:
            raise ValueError('Unexpected add-on ID or version')
        for name in reference - {'manifest.json'}:
            if signed.read(name) != original.read(name):
                raise ValueError('Changed payload: ' + name)
