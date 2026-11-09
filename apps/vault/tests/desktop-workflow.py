from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import os
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[3]
if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
    Path(output).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / 'apps/vault/desktop'))
if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
    import vault_ui as ui
else:
    loader = SourceFileLoader('vault_recovery_test', str(root / 'apps/vault/desktop/vault.pyw'))
    spec = spec_from_loader(loader.name, loader)
    ui = module_from_spec(spec)
    loader.exec_module(ui)

# CI builds the native worker into an isolated target directory. Keep this
# override in the test; production worker discovery is unchanged.
if os.environ.get('CARGO_TARGET_DIR'):
    original_backend = ui.backend

    def test_backend(program='kryptocore-vault'):
        candidate = Path(os.environ['CARGO_TARGET_DIR']) / 'release' / (program + ('.exe' if os.name == 'nt' else ''))
        return candidate if candidate.is_file() else original_backend(program)

    ui.backend = test_backend

(root / 'dist').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='vault-recovery-menu-', dir=root / 'dist') as work:
    folder = Path(work)
    os.environ['LOCALAPPDATA'] = str(folder)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    app = ui.W.QApplication([])
    app.setStyleSheet(ui.desktop_style())
    app.setQuitOnLastWindowClosed(False)
    for filename in ('segoeui.ttf', 'consola.ttf'):
        font = Path('C:/Windows/Fonts') / filename
        if font.is_file():
            ui.G.QFontDatabase.addApplicationFont(str(font))

    class TestVault(ui.Vault):
        def setup_firefox(self):
            if os.name == 'nt':
                self.update_firefox_status()
            else:
                super().setup_firefox()

    vault = TestVault()
    vault.show()
    heading = vault.findChild(ui.W.QLabel, 'welcomeTitle')
    print('Native UI font:', ui.G.QFontInfo(heading.font()).family())
    errors = []
    selections = []
    synthetic_key = []
    ui.W.QFileDialog.getSaveFileName = staticmethod(lambda *_, **__: (str(selections.pop(0)), ''))
    ui.W.QFileDialog.getOpenFileName = staticmethod(lambda *_: (str(selections.pop(0)), ''))

    def later(callback):
        def checked():
            try:
                callback()
            except Exception as error:
                errors.append(error)
                panel = ui.W.QApplication.activeModalWidget()
                if panel is not None:
                    panel.reject()
                if vault.dialog is not None:
                    vault.dialog.reject()
        ui.C.QTimer.singleShot(0, checked)

    def click(panel, text):
        control = next(button for button in panel.findChildren(ui.W.QPushButton) if button.text() == text)
        assert control.isEnabled(), text
        control.click()

    def check():
        if errors:
            raise errors[0]

    def locked_settings():
        controls = {button.text(): button for button in vault.dialog.findChildren(ui.W.QPushButton)}
        assert not controls['Notfallblatt einrichten oder erneuern'].isEnabled()
        assert not controls['Sicherung erstellen'].isEnabled()
        assert not controls['Tresor-Status'].isEnabled()
        assert not controls['Logins als JSON exportieren'].isEnabled()
        assert not controls['Tresorpasswort ändern'].isEnabled()
        assert not controls['Datei-Prüfwert (SHA-256)'].isEnabled()
        later(check_usage)
        click(vault.dialog, 'Hinweise zur Nutzung')

    def check_usage():
        assert vault.dialog.windowTitle() == 'Hinweise zur Nutzung'
        assert any('Testdaten' in label.text() for label in vault.dialog.findChildren(ui.W.QLabel))
        click(vault.dialog, 'Schließen')

    later(locked_settings)
    vault.settings()
    check()
    assert not any(button.text() == 'Notfallblatt einrichten oder erneuern'
                   for button in vault.pages.widget(1).findChildren(ui.W.QPushButton))

    passphrase = 'Synthetic initial vault password'
    vault_path = folder / 'synthetic.kcv'
    pdf_path = folder / 'synthetic-emergency.pdf'

    def enter_new_vault(preview):
        panel = vault.dialog
        click(panel, 'Auswählen')
        for field in panel.findChildren(ui.W.QLineEdit):
            if field.accessibleName().startswith('Tresorpasswort'):
                field.setText(passphrase)
        later(preview)
        click(panel, 'Weiter zum Notfallblatt')

    def go_back():
        sheet = ui.W.QApplication.activeModalWidget()
        assert sheet.windowTitle() == 'Dein Notfallblatt'
        assert not vault_path.exists()
        click(sheet, 'Zurück')
        later(lambda: click(vault.dialog, 'Abbrechen'))

    selections.append(vault_path)
    later(lambda: enter_new_vault(go_back))
    vault.open(True)
    check()
    assert not vault_path.exists() and not pdf_path.exists()

    def show_and_save():
        sheet = ui.W.QApplication.activeModalWidget()
        parent = vault.dialog
        assert sheet.windowTitle() == 'Dein Notfallblatt'
        assert any('getrennt vom Tresor' in label.text() for label in sheet.findChildren(ui.W.QLabel))
        preview = sheet.findChild(ui.W.QLabel, 'recoveryCode')
        assert preview.isHidden() and preview.text() == ''
        click(sheet, 'Schlüssel anzeigen')
        synthetic_key.append(''.join(preview.text().split()))
        assert len(synthetic_key[0]) == 64
        click(sheet, 'Schlüssel verbergen')
        assert preview.isHidden() and preview.text() == ''
        def fail_if_creation_stalled():
            if vault.dialog is parent:
                errors.append(AssertionError(parent.error.text() or 'Vault creation did not finish'))
                parent.reject()
        ui.C.QTimer.singleShot(30000, fail_if_creation_stalled)
        click(sheet, 'PDF speichern und fortfahren')

    selections.extend((vault_path, pdf_path))
    later(lambda: enter_new_vault(show_and_save))
    vault.open(True)
    check()
    assert vault.process is not None and vault_path.is_file()
    assert vault_path.read_bytes().startswith(b'KCV4\0')
    assert vault.active_revision['epoch'] == 1
    assert pdf_path.read_bytes().startswith(b'%PDF')
    assert vault.dialog is None and not selections

    def empty_health():
        assert vault.dialog.findChild(ui.W.QLabel, 'healthEntryCount').text() == '0'
        assert vault.dialog.findChild(ui.W.QLabel, 'healthRecovery').text() == 'Eingerichtet'
        assert 'keine Sicherung' in vault.dialog.findChild(ui.W.QLabel, 'healthBackup').text()
        click(vault.dialog, 'Schließen')

    later(empty_health)
    vault.health()
    check()

    def open_recovery_from_settings():
        later(check_recovery_panel)
        click(vault.dialog, 'Notfallblatt einrichten oder erneuern')

    def check_recovery_panel():
        assert vault.dialog.windowTitle() == 'Notfallblatt'
        click(vault.dialog, 'Abbrechen')

    later(open_recovery_from_settings)
    vault.settings()
    check()

    site = 'https://example.invalid'
    username = 'Synthetic user'
    secret = 'Synthetic login password'
    vault.entries = vault.request(action='put', site=site, username=username, password=secret)['entries']
    original = vault_path.read_bytes()

    def check_delete_dialog():
        panel = vault.dialog
        assert panel.windowTitle() == 'Login löschen?'
        assert panel.findChild(ui.W.QFrame, 'card') is None
        assert panel.error.isHidden()
        assert any(button.text() == 'Login löschen' and not button.isDefault()
                   for button in panel.findChildren(ui.W.QPushButton))
        click(panel, 'Abbrechen')

    later(check_delete_dialog)
    vault.remove(vault.entries[0])
    check()
    assert vault.entries[0]['origin'] == site and vault_path.read_bytes() == original
    print('Delete dialog: flat action row, cancel preserves the login.')

    backup_path = folder / 'backup.kcv'
    selections.extend((vault_path, backup_path))

    def open_backup_from_settings():
        later(save_backup)
        click(vault.dialog, 'Sicherung erstellen')

    def save_backup():
        panel = vault.dialog
        assert panel.windowTitle() == 'Sicherung erstellen'
        assert any('jetziges Passwort' in label.text() for label in panel.findChildren(ui.W.QLabel))
        click(panel, 'Sicherungsdatei speichern')
        assert 'existiert bereits' in panel.error.text(), panel.error.text()
        assert vault_path.read_bytes() == original
        assert vault.last_backup_at(vault_path) is None, 'Rejected backup was recorded as successful'
        click(panel, 'Sicherungsdatei speichern')
        assert not panel.isVisible(), panel.error.text()

    later(open_backup_from_settings)
    vault.settings()
    check()
    assert backup_path.read_bytes() == original == vault_path.read_bytes()
    receipt = vault.last_backup_at(vault_path)
    assert receipt is not None and 0 <= time.time() - receipt < 60
    original_date = vault_path.stat().st_mtime
    old_date = time.time() - 200 * 86400
    os.utime(vault_path, (old_date, old_date))

    def backed_up_health():
        panel = vault.dialog
        assert panel.windowTitle() == 'Tresor-Status'
        assert panel.findChild(ui.W.QLabel, 'healthEntryCount').text() == '1'
        assert 'keine Sicherung' not in panel.findChild(ui.W.QLabel, 'healthBackup').text()
        assert panel.findChild(ui.W.QLabel, 'healthAgeHint') is not None
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            panel.grab().save(str(Path(output) / 'vault-health.png'))
        click(panel, 'Schließen')

    later(backed_up_health)
    vault.health()
    check()
    assert vault_path.read_bytes() == original
    os.utime(vault_path, (original_date, original_date))
    vault.lock()

    disposable = folder / 'restore-test.kcv'
    disposable.write_bytes(backup_path.read_bytes())
    selections.append(disposable)
    cancelled_fields = []

    def cancel_recovery():
        panel = vault.dialog
        for field in panel.findChildren(ui.W.QLineEdit):
            cancelled_fields.append(field)
            field.setText('Synthetic cancelled recovery input')
        click(panel, 'Abbrechen')

    later(cancel_recovery)
    vault.recover()
    check()
    assert cancelled_fields and all(field.text() == '' for field in cancelled_fields)
    assert vault.process is None and disposable.read_bytes() == original
    selections.append(disposable)
    recovery_fields = []

    def recover_copy():
        panel = vault.dialog
        assert any('zusätzliche Kopie' in label.text() for label in panel.findChildren(ui.W.QLabel))
        assert any('Alte Tresorkopien bleiben' in label.text() and 'Datenschlüssel' in label.text()
                   for label in panel.findChildren(ui.W.QLabel))
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            Path(output).mkdir(parents=True, exist_ok=True)
            panel.grab().save(str(Path(output) / 'vault-recovery-warning.png'))
        for field in panel.findChildren(ui.W.QLineEdit):
            recovery_fields.append(field)
            value = synthetic_key[0] if field.accessibleName().startswith('Schlüssel') else 'Synthetic replacement vault password'
            field.setText(value)
        click(panel, 'Passwort zurücksetzen')
        assert not panel.isVisible(), panel.error.text()

    later(recover_copy)
    vault.recover()
    check()
    assert recovery_fields and all(field.text() == '' for field in recovery_fields)
    assert vault.active_vault_path == str(disposable)
    assert vault.request(action='reveal', site=site)['password'] == secret
    assert backup_path.read_bytes() == original == vault_path.read_bytes()
    # The unchanged recovery secret is rewrapped rather than copying its old slot.
    assert disposable.read_bytes()[117:205] != original[117:205]
    protected = disposable
    start_epoch = vault.active_revision['epoch']
    stale = protected.read_bytes()
    vault.entries = vault.request(action='put', previous=site, site=site, username=username, password=secret)['entries']
    assert vault.active_revision['epoch'] == start_epoch + 1
    current = protected.read_bytes()
    vault.lock()
    protected.write_bytes(stale)

    def reject_older_epoch():
        panel = vault.dialog
        for field in panel.findChildren(ui.W.QLineEdit):
            if field.accessibleName().startswith('Tresorpasswort'):
                field.setText('Synthetic replacement vault password')
        click(panel, 'Entsperren')
        assert panel.isVisible(), 'Rollback rejection closed the explanation dialog'
        assert 'Älterer oder anderer Tresorstand' in panel.error.text(), panel.error.text()
        click(panel, 'Abbrechen')

    later(reject_older_epoch)
    vault.open(False, str(protected))
    check()
    assert vault.process is None and protected.read_bytes() == stale
    protected.write_bytes(current)

    def open_current_epoch():
        panel = vault.dialog
        for field in panel.findChildren(ui.W.QLineEdit):
            if field.accessibleName().startswith('Tresorpasswort'):
                field.setText('Synthetic replacement vault password')
        click(panel, 'Entsperren')

    later(open_current_epoch)
    vault.open(False, str(protected))
    check()
    assert vault.active_revision['epoch'] == start_epoch + 1 and vault.process is not None
    protected.write_bytes(stale)
    try:
        vault.request(action='reveal', site=site)
        raise AssertionError('Live rollback released a password')
    except ui.VaultError:
        pass
    assert vault.process is None and vault.active_revision is None
    protected.write_bytes(current)
    later(open_current_epoch)
    vault.open(False, str(protected))
    check()
    # A plaintext export is deliberate; failures/cancel never overwrite source.
    migration_json = folder / 'migration.json'
    occupied_json = folder / 'occupied.json'
    occupied_json.write_bytes(b'Preserve this existing file')
    selections.extend((occupied_json, migration_json))

    def export_migration():
        panel = vault.dialog
        save = next(b for b in panel.findChildren(ui.W.QPushButton) if b.text() == 'JSON-Datei speichern')
        assert not save.isEnabled() and not migration_json.exists()
        assert any('unverschlüsselt' in item.text() for item in panel.findChildren(ui.W.QLabel))
        panel.findChild(ui.W.QCheckBox).setChecked(True)
        click(panel, 'JSON-Datei speichern')
        assert 'existiert bereits' in panel.error.text()
        assert occupied_json.read_bytes() == b'Preserve this existing file'
        assert protected.read_bytes() == current
        click(panel, 'JSON-Datei speichern')
        assert not panel.isVisible(), panel.error.text()

    later(export_migration)
    vault.export_json()
    check()
    exported = json.loads(migration_json.read_text(encoding='utf-8'))
    assert exported['schema_version'] == 1 and exported['entries'][0]['password'] == secret
    assert protected.read_bytes() == current
    original_process = vault.process
    selections.append(migration_json)
    later(lambda: click(vault.dialog, 'Abbrechen'))
    vault.import_json()
    check()
    assert vault.process is original_process and protected.read_bytes() == current

    # Actual import follows the existing password/strength/emergency-sheet wizard.
    imported_path = folder/'migrated.kcv'
    imported_pdf = folder/'migrated-emergency.pdf'
    selections.extend((migration_json, imported_path, imported_pdf))

    def migration_preview():
        assert vault.dialog.windowTitle() == 'Aus Export umziehen'
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            vault.dialog.grab().save(str(Path(output) / 'vault-import-preview.png'))
        later(migration_setup)
        click(vault.dialog, 'Neuen Tresor einrichten')

    def migration_setup():
        assert vault.dialog.windowTitle() == 'Tresor aus Export'
        enter_new_vault(show_and_save)

    later(migration_preview)
    vault.import_json()
    check()
    assert imported_path.read_bytes().startswith(b'KCV4\0')
    assert imported_pdf.read_bytes().startswith(b'%PDF')
    assert vault.active_vault_path == str(imported_path) and vault.process is not None
    assert vault.request(action='reveal', site=site)['password'] == secret
    assert vault.last_backup_at(imported_path) is None
    assert protected.read_bytes() == current and json.loads(migration_json.read_bytes()) == exported

    # Password changes are separately authorized, cancellation clears inputs,
    # and explicit key rotation produces a genuinely usable replacement sheet.
    before_change = imported_path.read_bytes()
    original_emergency = synthetic_key[-1]
    cancelled_password_fields = []

    def cancel_password_change():
        panel = vault.dialog
        assert panel.windowTitle() == 'Tresorpasswort ändern'
        assert not panel.findChild(ui.W.QCheckBox).isChecked()
        for field in panel.findChildren(ui.W.QLineEdit):
            field.setText('Synthetic cancelled password')
            cancelled_password_fields.append(field)
        click(panel, 'Abbrechen')

    later(cancel_password_change)
    vault.change_password()
    check()
    assert all(field.text() == '' for field in cancelled_password_fields)
    assert imported_path.read_bytes() == before_change
    quick_password = 'Synthetic ordinary GUI password'
    rotated_password = 'Synthetic rotated GUI password'
    previous_browser_session = vault.firefox_epoch

    def enter_password_change(current_password, next_password):
        for field in vault.dialog.findChildren(ui.W.QLineEdit):
            field.setText(current_password if field.accessibleName() == 'Aktuelles Tresorpasswort' else next_password)

    def ordinary_password_change():
        panel = vault.dialog
        assert not panel.findChild(ui.W.QCheckBox).isChecked()
        assert 'Datenschlüssel und Notfallblatt bleiben gleich' in panel.findChild(ui.W.QLabel, 'passwordChangeExplanation').text()
        assert any('Alte Dateikopien bleiben' in item.text() for item in panel.findChildren(ui.W.QLabel))
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            panel.grab().save(str(Path(output)/'vault-password-change.png'))
        enter_password_change('wrong current password', quick_password)
        click(panel, 'Passwort ändern')
        assert 'aktuelle Tresorpasswort' in panel.error.text()
        assert imported_path.read_bytes() == before_change
        enter_password_change(passphrase, quick_password)
        click(panel, 'Passwort ändern')
        assert not panel.isVisible(), panel.error.text()

    later(ordinary_password_change)
    vault.change_password()
    check()
    assert vault.firefox_epoch != previous_browser_session
    assert vault.request(action='reveal', site=site)['password'] == secret
    quick_bytes = imported_path.read_bytes()
    assert quick_bytes != before_change
    digest_path = folder/'vault.sha256'
    occupied_digest = folder/'occupied.sha256'
    occupied_digest.write_bytes(b'Preserve existing reference')
    selections.extend((occupied_digest, digest_path))

    def check_digest():
        panel = vault.dialog
        digest = hashlib.sha256(quick_bytes).hexdigest()
        assert ''.join(panel.findChild(ui.W.QLabel, 'fileDigestValue').text().split()) == digest
        field = next(field for field in panel.findChildren(ui.W.QLineEdit) if field.accessibleName().startswith('Mit notiertem'))
        result = panel.findChild(ui.W.QLabel, 'fileDigestComparison')
        field.setText('bad format')
        click(panel, 'Vergleichen')
        assert '64 Hex-Zeichen' in result.text()
        field.setText(hashlib.sha256(before_change).hexdigest())
        click(panel, 'Vergleichen')
        assert 'unterscheiden' in result.text()
        field.setText(digest.upper())
        click(panel, 'Vergleichen')
        assert 'entspricht' in result.text()
        click(panel, 'Prüfwert kopieren')
        assert ui.W.QApplication.clipboard().text() == digest
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            panel.grab().save(str(Path(output)/'vault-file-digest.png'))
        click(panel, 'Prüfwert separat speichern')
        assert 'existiert bereits' in panel.error.text()
        assert occupied_digest.read_bytes() == b'Preserve existing reference'
        click(panel, 'Prüfwert separat speichern')
        assert 'gespeichert' in result.text()
        click(panel, 'Schließen')

    later(check_digest)
    vault.file_digest()
    check()
    assert digest_path.read_text(encoding='ascii') == hashlib.sha256(quick_bytes).hexdigest()+'\n'
    new_sheet = folder/'rekey-emergency.pdf'
    selections.append(new_sheet)

    def explicit_key_rotation():
        panel = vault.dialog
        panel.findChild(ui.W.QCheckBox).setChecked(True)
        assert 'neues Notfallblatt' in panel.findChild(ui.W.QLabel, 'passwordChangeExplanation').text()
        if output := os.environ.get('KCV_TEST_SCREENSHOTS'):
            panel.grab().save(str(Path(output)/'vault-password-rekey.png'))
        enter_password_change(quick_password, rotated_password)
        later(show_and_save)
        click(panel, 'Passwort ändern')
        assert not panel.isVisible(), panel.error.text()

    later(explicit_key_rotation)
    vault.change_password()
    check()
    final_bytes = imported_path.read_bytes()
    assert final_bytes != quick_bytes and synthetic_key[-1] != original_emergency
    assert new_sheet.read_bytes().startswith(b'%PDF')
    assert vault.request(action='reveal', site=site)['password'] == secret
    # Exercise the actual key from that PDF on a copy, not the active original.
    recovery_copy = folder/'new-sheet-recovery-test.kcv'
    recovery_copy.write_bytes(final_bytes)
    vault.lock()
    selections.append(recovery_copy)

    def recover_with_new_sheet():
        panel = vault.dialog
        for field in panel.findChildren(ui.W.QLineEdit):
            field.setText(synthetic_key[-1] if field.accessibleName().startswith('Schlüssel') else 'Synthetic new sheet restore password')
        click(panel, 'Passwort zurücksetzen')
        assert not panel.isVisible(), panel.error.text()

    later(recover_with_new_sheet)
    vault.recover()
    check()
    assert vault.request(action='reveal', site=site)['password'] == secret
    assert imported_path.read_bytes() == final_bytes and protected.read_bytes() == current

    class FixtureChannel:
        # Exercise decrypted requests and replies. Separate tests cover Noise framing.
        def step(self, _operation, data):
            return data

    vault.firefox_key = bytes(range(32))

    def browser_reply(action, target, data=None, key=None):
        request = json.dumps({'action': action, 'site': target, 'data': data,
                              'session': vault.firefox_epoch}).encode()
        frame = vault.firefox_secure_reply(FixtureChannel(), False, key if key is not None else vault.firefox_key, request)
        return json.loads(bytes.fromhex(frame['m']))

    def decide_fill(site, *, allow=True):
        if os.name != 'nt':
            access = vault.active_firefox_fill()
            assert access.site == site and not access.approved
            vault.firefox_fill_access = ui.replace(access, approved=True) if allow else None
            return

        def decide():
            panel = app.activeModalWidget()
            assert any(item.isVisible() and item.text() == site and item.textFormat() == ui.C.Qt.PlainText
                       for item in panel.findChildren(ui.W.QLabel))
            click(panel, 'Einmal freigeben' if allow else 'Anfrage ablehnen')
            if allow:
                assert any('erneut' in item.text() for item in panel.findChildren(ui.W.QLabel))
            click(panel, 'Schließen')

        later(decide)
        vault.firefox_panel()
        check()

    host = 'bare.example.invalid:8443'
    target = f'https://{host}'
    vault.entries = vault.request(action='put', site='Bare.Example.Invalid:8443/login',
                                  username=username, password=secret)['entries']
    assert any(entry['origin'] == host for entry in vault.entries)
    assert browser_reply('lookup', target) == {'code': 'login_found'}
    expected_fill = {'origin': target, 'username': username, 'password': secret,
                     'session': vault.firefox_epoch}
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    assert vault.dialog is None
    first = vault.firefox_fill_access
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    assert vault.firefox_fill_access is first
    vault.firefox_fill_access = ui.replace(first, expires_at=time.monotonic() - 1)
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    assert vault.firefox_fill_access is not first
    assert browser_reply('fill_page', target) == {'code': 'approval_busy'}
    assert browser_reply('fill', target, key=bytes(32)) == {'code': 'pair_required'}
    other = 'https://other.example.invalid'
    vault.entries = vault.request(action='put', site=other, username=username, password=secret)['entries']
    decide_fill(target)
    assert browser_reply('fill_page', target) == {'code': 'approval_busy'}
    assert browser_reply('fill', other) == {'code': 'approval_busy'}
    assert browser_reply('fill', target) == expected_fill
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target, allow=False)
    assert vault.firefox_fill_access is None
    assert browser_reply('fill_page', target) == {'code': 'approval_required'}
    decide_fill(target)
    assert browser_reply('fill_page', target) == expected_fill
    assert browser_reply('new_login', target) == {'code': 'exists'}
    assert browser_reply('save', target, {'username': username, 'password': secret}) == {'code': 'exists'}

    vault.entries = vault.request(action='put', site='http://legacy.example.invalid',
                                  username=username, password=secret)['entries']
    for other_origin in ('https://bare.example.invalid', 'https://bare.example.invalid:8444',
                         'https://bare.example.invalid.attacker.invalid:8443',
                         'https://sub.bare.example.invalid:8443', 'https://legacy.example.invalid'):
        assert browser_reply('fill', other_origin) == {'code': 'no_login'}
    for invalid_origin in (f'http://{host}', f'{target}/path', 'https://http://legacy.example.invalid',
                           'https://user@bare.example.invalid:8443', f'{target}#fragment'):
        try:
            browser_reply('fill', invalid_origin)
        except ui.ChannelError:
            pass
        else:
            raise AssertionError(f'Invalid browser origin accepted: {invalid_origin}')

    explicit_secret = 'Synthetic explicit HTTPS password'
    vault.entries = vault.request(action='put', site=target, username=username, password=explicit_secret)['entries']
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target)
    vault.firefox_fill_access = ui.replace(vault.firefox_fill_access, expires_at=time.monotonic() - 1)
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target)
    assert browser_reply('fill', target) == {**expected_fill, 'password': explicit_secret}
    assert vault.request(action='reveal', site=host)['password'] == secret
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target)
    vault.set_vault_mode('strict')
    assert vault.firefox_fill_access is None
    assert browser_reply('fill_page', target) == {'code': 'direct_fill_disabled'}
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target)
    old_key = vault.firefox_key
    vault.firefox_key = bytes(reversed(range(32)))
    vault.cancel_firefox_requests()
    assert browser_reply('fill', target, key=old_key) == {'code': 'pair_required'}
    assert browser_reply('fill', target) == {'code': 'approval_required'}
    decide_fill(target)
    old_epoch = vault.firefox_epoch
    if os.name != 'nt':
        vault.application_state_changed(ui.C.Qt.ApplicationInactive)
    else:
        vault.deadline = time.monotonic() - 1
        assert vault.eventFilter(vault, ui.C.QEvent(ui.C.QEvent.KeyPress))
    assert vault.firefox_fill_access is None and vault.firefox_epoch != old_epoch
    assert browser_reply('fill', target) == {'code': 'locked'}
    print('Firefox bridge: exact origin, explicit one-use approval, denial, expiry, key change and lock passed.')

    if os.name != 'nt':
        assert vault.process is None and not vault.entries
        assert vault.firefox_indicator.isHidden()
        assert folder.joinpath('KryptoCoreLabs/Vault').stat().st_mode & 0o777 == 0o700
    else:
        server = ui.N.QLocalServer()
        server.setSocketOptions(ui.N.QLocalServer.UserAccessOption)
        name = 'kcv-test-session-' + folder.name
        assert server.listen(name), server.errorString()
        client = ui.N.QLocalSocket()
        client.connectToServer(name)
        assert client.waitForConnected(2000), client.errorString()
        assert server.hasPendingConnections() or server.waitForNewConnection(2000)
        peer = server.nextPendingConnection()
        assert ui.firefox_pipe_client_in_session(peer.socketDescriptor())
        assert not ui.firefox_pipe_client_in_session(-1)
        client.abort()
        server.close()
    vault.close()
    print('PASS: recovery/epochs, migration/health, password/key rotation, real replacement sheet, file digests and no-clobber references; originals preserved.')
