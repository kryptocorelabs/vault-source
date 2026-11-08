from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
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
    app.setStyleSheet(ui.STYLE)
    app.setQuitOnLastWindowClosed(False)
    for filename in ('segoeui.ttf', 'consola.ttf'):
        ui.G.QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts') / filename))

    class TestVault(ui.Vault):
        def setup_firefox(self):
            self.update_firefox_status()

    vault = TestVault()
    vault.show()
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
        ui.C.QTimer.singleShot(8000, fail_if_creation_stalled)
        click(sheet, 'PDF speichern und fortfahren')

    selections.extend((vault_path, pdf_path))
    later(lambda: enter_new_vault(show_and_save))
    vault.open(True)
    check()
    assert vault.process is not None and vault_path.is_file()
    assert pdf_path.read_bytes().startswith(b'%PDF')
    assert vault.dialog is None and not selections

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
        click(panel, 'Sicherungsdatei speichern')
        assert not panel.isVisible(), panel.error.text()

    later(open_backup_from_settings)
    vault.settings()
    check()
    assert backup_path.read_bytes() == original == vault_path.read_bytes()
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
    assert disposable.read_bytes()[93:181] != original[93:181]
    vault.close()
    print('Usage and recovery warnings verified. The backup refused overwrite and a disposable copy recovered the synthetic login.')
