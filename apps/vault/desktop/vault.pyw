"""Frameless Qt desktop for the local Rust Vault session."""

from html import escape
import ctypes
from ctypes import wintypes
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys
import time

from PySide6 import QtCore as C, QtGui as G, QtNetwork as N, QtWidgets as W
from firefox_channel import Channel, ChannelError, ChannelLibrary

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VAULT_IDLE_SECONDS = {'standard': 300, 'strict': 60}
FIREFOX_PIPE = 'kryptocorelabs-vault-firefox-v5'
FIREFOX_PAIR_SECONDS = 120
FIREFOX_KEY_CONTEXT = b'KryptoCore Vault Firefox v5 channel key'
FIREFOX_REQUEST_LIMIT = 12 * 1024
FIREFOX_LOGIN_LIMIT = 4096
FIREFOX_HOST = 'com.kryptocorelabs.vault'
FIREFOX_ID = 'vault@kryptocorelabs'
WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218
SESSION_END_EVENTS = (0x2, 0x4, 0x6, 0x7)  # Console disconnect, remote disconnect, logoff, lock.
SUSPEND_EVENTS = (0x4, 0x12)  # Suspend and automatic resume.
local_deps = ROOT / 'dist/desktop-deps'
if local_deps.is_dir():
    sys.path.append(str(local_deps))
try:
    from zxcvbn import zxcvbn
except ImportError:
    zxcvbn = None

STYLE = '''
QWidget { color: #e5eef5; font: 13px "Segoe UI"; }
QFrame#shell, QDialog#panel, QWidget#panelBody {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #172736, stop:.55 #121d2a, stop:1 #101822);
}
QFrame#shell { border: 1px solid #304354; border-radius: 18px; }
QFrame#shell[glass="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(23, 39, 54, 239), stop:.55 rgba(18, 29, 42, 246), stop:1 rgba(16, 24, 34, 249));
}
QDialog#panel { border: 1px solid #304354; }
QFrame#titlebar { background: #172533; border-top-left-radius: 17px; border-top-right-radius: 17px; }
QFrame#card, QFrame#details {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1c2b39, stop:1 #17222f);
    border: 1px solid #314556; border-radius: 15px;
}
QLabel#eyebrow { color: #81e8d3; font-size: 11px; font-weight: 650; }
QLabel#heading { font-size: 28px; font-weight: 650; }
QLabel#section { font-size: 21px; font-weight: 650; }
QLabel#muted { color: #a9bdcc; }
QLabel#error { color: #ff9ea8; }
QPushButton { background: #1e2c38; border: 1px solid #324552; border-radius: 8px; padding: 7px 11px; }
QPushButton:hover { background: #293c48; }
QPushButton:focus, QLineEdit:focus { border: 1px solid #81e8d3; }
QPushButton:disabled { color: #92a6b4; background: #192530; }
QPushButton#primary { background: #203b3d; color: #a4f4e1; border-color: #38665f; font-weight: 650; }
QPushButton#primary:hover { background: #2b4f4e; }
QPushButton#chrome { background: transparent; border-color: transparent; padding: 2px 8px; }
QPushButton#chrome:hover, QPushButton#chrome:focus { background: #273946; border-color: #3b5966; }
QFrame#welcomeRule { background: #293b4a; max-height: 1px; }
QLabel#welcomeTitle { font-size: 34px; font-weight: 650; color: #f3f8fc; }
QLabel#welcomeIntro { color: #b4c7d6; font-size: 14px; }
QLabel#welcomeMark { background: #101a27; border: 1px solid #304355; border-radius: 18px; }
QLabel#tileTitle { color: #f1f7fb; font-size: 15px; font-weight: 650; }
QLabel#tileDetail { color: #abc2d2; font-size: 12px; }
QLabel#tileIcon { background: #25394a; color: #b9dbef; border-radius: 9px; font-size: 19px; font-weight: 650; }
QLabel#tileIconPrimary { background: #315957; color: #baf6e7; border-radius: 9px; font-size: 19px; font-weight: 650; }
QLabel#tileArrow { color: #a9c9d7; font-size: 22px; }
QLabel#previewBadge { background: #202d3b; color: #a9c0d0; border-radius: 7px; padding: 4px 8px; font-size: 11px; }
QPushButton#startTile, QPushButton#startTilePrimary { border-radius: 15px; padding: 0; }
QPushButton#startTile { background: #1a2937; border: 1px solid #324658; }
QPushButton#startTile:hover { background: #23384a; border-color: #4b677b; }
QPushButton#startTilePrimary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #234947, stop:1 #20323e);
    border: 1px solid #487971;
}
QPushButton#startTilePrimary:hover { background: #305652; border-color: #70a99c; }
QPushButton#startTile:focus, QPushButton#startTilePrimary:focus { border: 2px solid #82e7d0; }
QPushButton#firefoxBadge { background: #1e2d39; border-color: #2e4352; border-radius: 9px; padding: 3px 8px; }
QPushButton#firefoxBadge[active="true"] { color: #a4f4e1; background: #213c3d; border-color: #38665f; }
QPushButton#firefoxBadge:hover, QPushButton#firefoxBadge:focus { border-color: #81e8d3; }
QLabel#pairCode { background: #0f1924; color: #a4f4e1; border: 1px solid #385451;
    border-radius: 11px; padding: 12px; font: 21px "Consolas"; }
QLabel#recoveryCode { background: #0f1924; color: #a4f4e1; border: 1px solid #385451;
    border-radius: 11px; padding: 12px; font: 14px "Consolas"; }
QLineEdit, QComboBox { background: #111b26; border: 1px solid #344652; border-radius: 9px; padding: 7px; selection-background-color: #31545e; }
QComboBox:focus { border-color: #81e8d3; }
QListWidget { background: transparent; border: 1px solid transparent; border-radius: 10px; outline: 0; }
QListWidget:focus { border-color: #588d88; }
QListWidget::item { background: #16222f; border: 1px solid #304455; padding: 9px 12px; border-radius: 9px; }
QListWidget::item:hover { background: #243646; border-color: #496477; }
QListWidget::item:selected { background: #294348; border-color: #4d7d79; color: #f3fcfa; }
QScrollBar:vertical { background: #16212c; width: 8px; border-radius: 4px; margin: 1px 0; }
QScrollBar::handle:vertical { background: #527083; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #73a395; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QProgressBar { background: #2c3c48; border: 0; border-radius: 3px; height: 6px; }
QProgressBar::chunk { background: #81e8d3; border-radius: 3px; }
'''


class VaultError(Exception):
    pass


def backend(program='kryptocore-vault'):
    name = program + ('.exe' if os.name == 'nt' else '')
    for directory in (HERE, ROOT / 'target/release', ROOT / 'target/x86_64-pc-windows-msvc/release'):
        path = directory / name
        if path.is_file():
            return path
    raise VaultError('Vault-Backend fehlt. Baue es nach der Kurzanleitung.')


def firefox_key_dpapi(data, *, protect):
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.c_void_p)]

    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = Blob(len(source), ctypes.addressof(source))
    output_blob = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    operation = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    operation.argtypes = (ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob))
    operation.restype = wintypes.BOOL
    free = ctypes.WinDLL('kernel32').LocalFree
    free.argtypes = (ctypes.c_void_p,)
    free.restype = ctypes.c_void_p
    try:
        if not operation(ctypes.byref(input_blob), None, None, None, None, 1, ctypes.byref(output_blob)):
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(output_blob.data, output_blob.size)
    finally:
        ctypes.memset(source, 0, len(source))
        if output_blob.data:
            ctypes.memset(output_blob.data, 0, output_blob.size)
            free(output_blob.data)


def write_local_file(path, data):
    output = C.QSaveFile(str(path))
    if not output.open(C.QIODevice.WriteOnly) or output.write(data) != len(data) or not output.commit():
        raise VaultError(output.errorString())


def label(text, style=''):
    widget = W.QLabel(text)
    widget.setTextFormat(C.Qt.PlainText)
    widget.setObjectName(style)
    return widget


def button(text, action, style=''):
    widget = W.QPushButton(text)
    widget.setObjectName(style)
    widget.clicked.connect(action)
    return widget


def row(*widgets):
    layout = W.QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def tile(parent_layout, title=''):
    frame = W.QFrame()
    frame.setObjectName('card')
    layout = W.QVBoxLayout(frame)
    layout.setContentsMargins(13, 12, 13, 12)
    layout.setSpacing(7)
    if title:
        layout.addWidget(label(title, 'eyebrow'))
    parent_layout.addWidget(frame)
    return layout


class StartTile(W.QPushButton):
    def __init__(self, title, detail, symbol, action, primary=False):
        super().__init__(title)
        self.setObjectName('startTilePrimary' if primary else 'startTile')
        self.setCursor(C.Qt.PointingHandCursor)
        self.setSizePolicy(W.QSizePolicy.Expanding, W.QSizePolicy.Fixed)
        self.setMinimumHeight(86 if primary else 121)
        self.clicked.connect(action)
        icon = label(symbol, 'tileIconPrimary' if primary else 'tileIcon')
        icon.setAlignment(C.Qt.AlignCenter)
        icon.setFixedSize(34, 34)
        self.title = label(title, 'tileTitle')
        self.detail = label('', 'tileDetail')
        self.detail.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Preferred)
        self.detail.setWordWrap(not primary)
        self.set_detail(detail)
        arrow = label('›', 'tileArrow')
        if primary:
            layout = row(icon)
            text = W.QVBoxLayout()
            text.setSpacing(3)
            text.addStretch()
            text.addWidget(self.title)
            text.addWidget(self.detail)
            text.addStretch()
            layout.addLayout(text, 1)
            layout.addWidget(arrow)
        else:
            layout = W.QVBoxLayout()
            icons = row(icon)
            icons.addStretch()
            icons.addWidget(arrow)
            layout.addLayout(icons)
            layout.addStretch()
            layout.addWidget(self.title)
            layout.addWidget(self.detail)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9 if primary else 3)
        self.setLayout(layout)
        for child in self.findChildren(W.QLabel):
            child.setAttribute(C.Qt.WA_TransparentForMouseEvents)

    def setText(self, title):
        super().setText(title)
        self.title.setText(title)

    def set_detail(self, detail):
        self.detail.setText(detail)
        self.setAccessibleDescription(detail)
        self.setToolTip(detail)

    def paintEvent(self, event):
        painter = W.QStylePainter(self)
        option = W.QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ''
        painter.drawControl(W.QStyle.CE_PushButton, option)

    def keyPressEvent(self, event):
        if event.key() in (C.Qt.Key_Return, C.Qt.Key_Enter):
            if not event.isAutoRepeat():
                self.click()
            return
        super().keyPressEvent(event)


def write_recovery_pdf(path, vault_name, recovery):
    output = C.QSaveFile(path)
    if not output.open(C.QIODevice.WriteOnly):
        raise VaultError('Das Notfallblatt konnte nicht gespeichert werden.')
    writer = G.QPdfWriter(output)
    writer.setTitle('KryptoCore Vault · Notfallblatt')
    writer.setPageSize(G.QPageSize(G.QPageSize.A4))
    writer.setPageMargins(C.QMarginsF(21, 23, 21, 23))
    document = G.QTextDocument()
    document.setHtml(f'''<h1>KryptoCore Vault</h1><h2>Notfallblatt</h2>
        <p>Tresor: <b>{escape(vault_name)}</b></p><p>Wiederherstellungsschlüssel</p>
        <p style="font-family:monospace; font-size:14pt">{recovery[:32]}<br>{recovery[32:]}</p>
        <p>Öffne Vault, wähle „Tresor wiederherstellen“ und dann die passende Tresordatei.
        Gib beide Zeilen des Schlüssels ein und lege ein neues Tresorpasswort fest.</p>
        <p><b>Wer dieses Blatt und die Tresordatei hat, kann den Tresor öffnen.</b>
        Bewahre das Blatt geschützt vor Dritten und getrennt vom Tresor und seinen
        Backups an einem Ort auf, den du im Notfall wiederfindest.</p>''')
    document.print_(writer)
    del writer
    if not output.commit():
        raise VaultError('Das Notfallblatt konnte nicht gespeichert werden.')


class TitleBar(W.QFrame):
    def __init__(self, window, controls=False):
        super().__init__()
        self.window = window
        self.setObjectName('titlebar')
        layout = W.QHBoxLayout(self)
        layout.setContentsMargins(15, 7, 9, 7)
        layout.addWidget(label('◉  VAULT', 'eyebrow'))
        layout.addStretch()
        if controls:
            layout.addWidget(window.firefox_indicator)
            settings = button('⚙', window.settings, 'chrome')
            settings.setAccessibleName('Einstellungen')
            settings.setToolTip('Einstellungen')
            layout.addWidget(settings)
            for text, name, action in [('−', 'Minimieren', window.showMinimized), ('□', 'Maximieren oder wiederherstellen', window.toggle_maximize)]:
                control = button(text, action, 'chrome')
                control.setAccessibleName(name)
                control.setToolTip(name)
                layout.addWidget(control)
        close = button('×', window.close, 'chrome')
        close.setAccessibleName('Schließen')
        close.setToolTip('Schließen')
        layout.addWidget(close)

    def mousePressEvent(self, event):
        if event.button() == C.Qt.LeftButton:
            self.window.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event):
        if event.button() == C.Qt.LeftButton and hasattr(self.window, 'toggle_maximize'):
            self.window.toggle_maximize()


class Panel(W.QDialog):
    def __init__(self, parent, title, hint='', *, framed=True):
        super().__init__(parent, C.Qt.Dialog | C.Qt.FramelessWindowHint)
        self.setObjectName('panel')
        self.setWindowTitle(title)
        self.setMinimumWidth(395)
        outer = W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))
        body = W.QWidget()
        body.setObjectName('panelBody')
        outer.addWidget(body)
        content = W.QVBoxLayout(body)
        content.setContentsMargins(19, 17, 19, 19)
        content.setSpacing(12)
        content.addWidget(label(title, 'heading'))
        if hint:
            description = label(hint, 'muted')
            description.setWordWrap(True)
            content.addWidget(description)
        self.layout = tile(content) if framed else content
        self.error = label('', 'error')
        self.error.setWordWrap(True)

    def field(self, name, value=''):
        widget = W.QLineEdit(value)
        caption = label(name)
        caption.setBuddy(widget)
        widget.setAccessibleName(name)
        self.layout.addWidget(caption)
        return widget

    def secret(self, name, generate=False):
        field = self.field(name)
        field.setEchoMode(W.QLineEdit.Password)
        toggle = button('Anzeigen', lambda: self.toggle(field, toggle))
        toggle.setAccessibleName(f'{name} anzeigen oder verbergen')
        controls = row(field, toggle)
        controls.setStretch(0, 1)
        if generate:
            controls.addWidget(button('Erzeugen', lambda: field.setText(''.join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(28)
            ))))
        self.layout.addLayout(controls)
        return field

    @staticmethod
    def toggle(field, toggle):
        show = field.echoMode() == W.QLineEdit.Password
        field.setEchoMode(W.QLineEdit.Normal if show else W.QLineEdit.Password)
        toggle.setText('Verbergen' if show else 'Anzeigen')

    def finish(self, text, action):
        self.layout.addWidget(self.error)
        submit = button(text, action, 'primary')
        submit.setDefault(True)
        self.layout.addLayout(row(button('Abbrechen', self.reject), submit))
        return submit


class Vault(W.QWidget):
    def __init__(self):
        super().__init__(None, C.Qt.Window | C.Qt.FramelessWindowHint)
        self.setWindowTitle('KryptoCoreLabs Vault')
        self.setWindowIcon(G.QIcon(str(HERE / 'vault-emblem.png')))
        self.resize(455, 705)
        self.setMinimumSize(395, 570)
        self.process = None
        self.session_window = None
        self.dialog = None
        self.entries = []
        local_data = os.environ.get('LOCALAPPDATA') or C.QStandardPaths.writableLocation(C.QStandardPaths.GenericDataLocation)
        self.settings_folder = Path(local_data) / 'KryptoCoreLabs' / 'Vault'
        self.preferences = C.QSettings(str(self.settings_folder / 'preferences.ini'), C.QSettings.IniFormat)
        self.glass_supported = sys.platform == 'win32' and C.QCoreApplication.instance().platformName() == 'windows'
        self.setAttribute(C.Qt.WA_TranslucentBackground, self.glass_supported)
        self.surface = W.QFrame()
        self.surface.setObjectName('shell')
        self.surface.setProperty('glass', self.glass_supported and self.preferences.value('appearance/glass', True, bool))
        self.vault_mode = 'strict' if self.preferences.value('vault/mode') == 'strict' else 'standard'
        self.active_vault_path = ''
        self.last_vault_path = self.preferences.value('vault/recent', '', str) if self.vault_mode == 'standard' else ''
        self.deadline = 0
        self.firefox_server = N.QLocalServer(self)
        self.firefox_server.setSocketOptions(N.QLocalServer.UserAccessOption)
        self.firefox_server.setMaxPendingConnections(4)
        self.firefox_server.newConnection.connect(self.accept_firefox)
        self.firefox_clients = set()
        self.firefox_channels = {}
        self.firefox_library = None
        self.firefox_key = None
        self.firefox_pair_until = 0
        self.firefox_candidate = None
        self.firefox_epoch = secrets.token_hex(16)
        self.firefox_seen = 0
        self.firefox_error = ''
        self.firefox_lock = None
        self.firefox_key_path = None
        self.firefox_indicator = button('Firefox', self.firefox_panel, 'firefoxBadge')
        outer = W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)
        layout = W.QVBoxLayout(self.surface)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(TitleBar(self, controls=True))
        self.pages = W.QStackedWidget()
        layout.addWidget(self.pages, 1)
        grip_row = W.QHBoxLayout()
        grip_row.addStretch()
        grip_row.addWidget(W.QSizeGrip(self))
        layout.addLayout(grip_row)
        self.pages.addWidget(self.welcome())
        self.pages.addWidget(self.library())
        self.update_open_button()
        lock_shortcut = G.QShortcut(G.QKeySequence('Ctrl+L'), self)
        lock_shortcut.activated.connect(self.lock)
        W.QApplication.instance().installEventFilter(self)
        self.timer = C.QTimer(self, interval=1000)
        self.timer.timeout.connect(self.check_idle)
        self.timer.start()
        self.setup_firefox()
        if self.glass_supported:
            window = int(self.winId())
            if ctypes.windll.wtsapi32.WTSRegisterSessionNotification(wintypes.HWND(window), 0):
                self.session_window = window

    def nativeEvent(self, event_type, message):
        if event_type == b'windows_generic_MSG':
            event = wintypes.MSG.from_address(int(message))
            if ((event.message == WM_WTSSESSION_CHANGE and event.wParam in SESSION_END_EVENTS) or
                    (event.message == WM_POWERBROADCAST and event.wParam in SUSPEND_EVENTS)):
                self.lock()
        return super().nativeEvent(event_type, message)

    def toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def settings(self):
        dialog = Panel(self, 'Einstellungen')
        dialog.layout.addWidget(label('SICHERHEITSMODUS', 'eyebrow'))
        mode = W.QComboBox()
        mode.setAccessibleName('Sicherheitsmodus')
        mode.addItem('Alltag', 'standard')
        mode.addItem('Streng', 'strict')
        mode.setCurrentIndex(mode.findData(self.vault_mode))
        mode_hint = label('', 'muted')
        mode_hint.setWordWrap(True)

        def describe_mode():
            if mode.currentData() == 'strict':
                mode_hint.setText('Datei jedes Mal wählen · nach 1 Minute sperren · neue Logins in Vault speichern.')
            else:
                mode_hint.setText('Letzte Datei merken · nach 5 Minuten sperren · neue Logins aus Firefox speichern.')

        def change_mode():
            self.set_vault_mode(mode.currentData())
            describe_mode()
            if self.preferences.status() != C.QSettings.NoError:
                dialog.error.setText('Die Einstellung konnte nicht dauerhaft gespeichert werden.')

        describe_mode()
        mode.currentIndexChanged.connect(change_mode)
        dialog.layout.addWidget(mode)
        dialog.layout.addWidget(mode_hint)
        dialog.layout.addSpacing(7)
        dialog.layout.addWidget(label('SICHERUNG UND NOTFALLBLATT', 'eyebrow'))
        recovery_hint = label(
            'Die Sicherung enthält deine verschlüsselten Logins. Das Notfallblatt hilft bei einem vergessenen Tresorpasswort.'
            if self.process else 'Entsperre den Tresor, um eine Sicherung zu erstellen oder das Notfallblatt zu verwalten.',
            'muted',
        )
        recovery_hint.setWordWrap(True)
        dialog.layout.addWidget(recovery_hint)
        recovery_action = button('Notfallblatt einrichten oder erneuern', lambda: dialog.done(3))
        recovery_action.setEnabled(self.process is not None)
        backup_action = button('Sicherung erstellen', lambda: dialog.done(4))
        backup_action.setEnabled(self.process is not None)
        dialog.layout.addWidget(backup_action)
        dialog.layout.addWidget(recovery_action)
        if self.glass_supported:
            dialog.layout.addSpacing(7)
            dialog.layout.addWidget(label('DARSTELLUNG', 'eyebrow'))
            glass = W.QCheckBox('Leichter Glas-Effekt')
            glass.setChecked(self.surface.property('glass'))
            glass.toggled.connect(self.set_glass)
            dialog.layout.addWidget(glass)
        dialog.layout.addSpacing(7)
        dialog.layout.addWidget(button('Firefox-Verbindung öffnen', lambda: dialog.done(2)))
        dialog.layout.addWidget(button('Hinweise zur Nutzung', lambda: dialog.done(5)))
        dialog.layout.addWidget(dialog.error)
        dialog.layout.addWidget(button('Schließen', dialog.accept))
        result = self.show_panel(dialog)
        dialog.deleteLater()
        if result == 2:
            self.firefox_panel()
        elif result == 3 and self.process is not None:
            self.enable_recovery()
        elif result == 4 and self.process is not None:
            self.backup()
        elif result == 5:
            self.usage_panel()

    def usage_panel(self):
        dialog = Panel(self, 'Hinweise zur Nutzung')
        for title, message in (
            ('VERSCHLÜSSELUNG', 'Vault verschlüsselt gespeicherte Logins lokal. Fehler, Geräteausfall oder ein kompromittiertes System können trotzdem zu Verlust oder Offenlegung führen. Nutze die Vorschau mit Testdaten.'),
            ('SICHERUNG', 'Lege regelmäßig verschlüsselte Kopien auf einem getrennten Datenträger ab. Bewahre das passende Notfallblatt geschützt und getrennt auf. Prüfe den Zugang an einer zusätzlichen Kopie.'),
        ):
            dialog.layout.addWidget(label(title, 'eyebrow'))
            detail = label(message, 'muted')
            detail.setWordWrap(True)
            dialog.layout.addWidget(detail)
        dialog.layout.addWidget(button('Schließen', dialog.accept))
        self.show_panel(dialog)
        dialog.deleteLater()

    def backup(self):
        dialog = Panel(self, 'Sicherung erstellen',
                       'Speichere die verschlüsselte Kopie möglichst auf einem anderen Datenträger. '
                       'Teste den Zugang später an einer zusätzlichen Kopie.')

        def save_backup():
            stamp = time.strftime('%Y-%m-%d-%H%M%S')
            suggestion = f'{Path(self.active_vault_path).stem}-Sicherung-{stamp}.kcv'
            path, _ = W.QFileDialog.getSaveFileName(
                dialog, 'Sicherungsdatei speichern', suggestion, 'KryptoCore-Tresor (*.kcv)',
                options=W.QFileDialog.DontConfirmOverwrite,
            )
            if not path or self.process is None:
                return
            if not path.lower().endswith('.kcv'):
                path += '.kcv'
            try:
                self.request(action='backup', destination=path)
            except VaultError as error:
                dialog.error.setText(str(error))
                return
            self.status.setText('Verschlüsselte Sicherung gespeichert.')
            dialog.accept()

        dialog.finish('Sicherungsdatei speichern', save_backup)
        self.show_panel(dialog)
        dialog.deleteLater()

    def set_glass(self, enabled):
        self.preferences.setValue('appearance/glass', enabled)
        self.surface.setProperty('glass', enabled)
        self.surface.style().unpolish(self.surface)
        self.surface.style().polish(self.surface)
        self.surface.update()

    def firefox_panel(self):
        dialog = Panel(self, 'Firefox')
        intro = label('', 'welcomeIntro')
        intro.setWordWrap(True)
        pairing_code = W.QLineEdit()
        pairing_code.setReadOnly(True)
        pairing_code.setAccessibleName('Firefox-Verbindungscode')
        dialog.layout.addWidget(intro)
        dialog.layout.addWidget(pairing_code)

        def refresh_view():
            pending = self.firefox_candidate is not None and time.monotonic() < self.firefox_pair_until
            pairing_code.setVisible(pending)
            if not pending:
                pairing_code.clear()
            generate.setVisible(not pending and self.process is not None and not self.firefox_error)
            disconnect.setVisible(self.firefox_key is not None)
            retry.setVisible(bool(self.firefox_error))
            if pending:
                intro.setText('Kopiere den Code ins Vault-Add-on in Firefox. Er gilt zwei Minuten und nur einmal.')
            elif self.firefox_error:
                intro.setText('Die Verbindung braucht einen neuen Versuch.')
            elif self.process is None:
                intro.setText('Entsperre deinen Tresor, um Firefox zu nutzen.')
            elif self.firefox_key is None:
                intro.setText('Erstelle einen Verbindungscode und füge ihn im Vault-Add-on in Firefox ein.')
            else:
                intro.setText('Firefox ist eingerichtet. Auf einer Login-Seite kannst du direkt aus dem Add-on ausfüllen.')

        def retry_firefox():
            self.setup_firefox()
            dialog.error.setText(self.firefox_error)
            refresh_view()

        def generate_code():
            if self.process is None or time.monotonic() >= self.deadline:
                return
            self.firefox_candidate = secrets.token_bytes(32)
            self.firefox_pair_until = time.monotonic() + FIREFOX_PAIR_SECONDS
            pairing_code.setText(self.firefox_candidate.hex())
            self.update_firefox_status()
            refresh_view()
            pairing_code.setFocus()
            pairing_code.selectAll()

        def disconnect_firefox():
            try:
                self.firefox_key_path.unlink(missing_ok=True)
            except OSError as error:
                dialog.error.setText(str(error))
                return
            self.firefox_key = None
            self.cancel_firefox_requests()
            self.update_firefox_status()
            dialog.error.clear()
            refresh_view()

        generate = button('Verbindungscode erstellen', generate_code, 'primary')
        disconnect = button('Firefox trennen', disconnect_firefox)
        retry = button('Erneut versuchen', retry_firefox)
        dialog.layout.addWidget(generate)
        dialog.layout.addWidget(disconnect)
        dialog.layout.addWidget(retry)
        dialog.layout.addWidget(dialog.error)
        dialog.layout.addWidget(button('Schließen', dialog.accept))
        dialog.error.setText(self.firefox_error)
        refresh_view()
        timer = C.QTimer(dialog, interval=500)
        timer.timeout.connect(refresh_view)
        timer.start()
        self.show_panel(dialog)
        dialog.deleteLater()

    def setup_firefox(self):
        if os.name != 'nt':
            self.firefox_indicator.hide()
            return
        if self.firefox_server.isListening():
            return
        try:
            folder = self.settings_folder
            folder.mkdir(parents=True, exist_ok=True)
            self.firefox_key_path = folder / 'firefox-pair-v5.dat'
            self.firefox_lock = C.QLockFile(str(folder / 'firefox-bridge.lock'))
            self.firefox_lock.setStaleLockTime(0)
            if not self.firefox_lock.tryLock(0):
                raise VaultError('Firefox wird bereits von einem anderen Vault-Fenster verwendet.')
            library = HERE / 'vault_firefox_channel.dll'
            if not library.is_file():
                library = ROOT / 'target/release/vault_firefox_channel.dll'
            self.firefox_library = ChannelLibrary(library)
            if not self.firefox_server.listen(FIREFOX_PIPE):
                raise VaultError('Der lokale Firefox-Kanal konnte nicht geöffnet werden.')
            self.register_firefox()
            (folder / 'firefox-pair.dat').unlink(missing_ok=True)
            self.firefox_error = ''
            if self.firefox_key_path.is_file():
                try:
                    key = firefox_key_dpapi(self.firefox_key_path.read_bytes(), protect=False)
                    if len(key) == 32:
                        self.firefox_key = key
                except OSError:
                    self.firefox_key = None
        except (KeyError, OSError, VaultError) as error:
            self.firefox_server.close()
            if self.firefox_lock is not None and self.firefox_lock.isLocked():
                self.firefox_lock.unlock()
            self.firefox_error = str(error)
        self.update_firefox_status()

    def update_firefox_status(self):
        now = time.monotonic()
        if self.firefox_candidate is not None and now >= self.firefox_pair_until:
            self.firefox_candidate = None
        if self.firefox_error:
            state = 'Fehler'
        elif self.process is None:
            state = 'Gesperrt'
        elif self.firefox_candidate is not None:
            state = 'Code bereit'
        elif self.firefox_key is None:
            state = 'Einrichten'
        elif self.firefox_seen and now - self.firefox_seen < 10:
            state = 'Verbunden'
        else:
            state = 'Bereit'
        self.firefox_indicator.setText(f'Firefox · {state}')
        self.firefox_indicator.setToolTip(self.firefox_error or 'Firefox-Verbindung verwalten')
        active = state in ('Bereit', 'Verbunden')
        if self.firefox_indicator.property('active') != active:
            self.firefox_indicator.setProperty('active', active)
            self.firefox_indicator.style().unpolish(self.firefox_indicator)
            self.firefox_indicator.style().polish(self.firefox_indicator)

    def register_firefox(self):
        import winreg

        manifest = HERE / f'{FIREFOX_HOST}.json'
        config = {
            'name': FIREFOX_HOST, 'description': 'KryptoCore Vault local connection',
            'path': str(backend('vault-firefox-host')), 'type': 'stdio',
            'allowed_extensions': [FIREFOX_ID],
        }
        data = json.dumps(config).encode('utf-8')
        if not manifest.is_file() or manifest.read_bytes() != data:
            write_local_file(manifest, data)
        registry = rf'Software\Mozilla\NativeMessagingHosts\{FIREFOX_HOST}'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry) as key:
                if winreg.QueryValueEx(key, '') == (str(manifest), winreg.REG_SZ):
                    return
        except FileNotFoundError:
            pass
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))

    def welcome(self):
        page = W.QWidget()
        page.setObjectName('welcomePage')
        outer = W.QVBoxLayout(page)
        outer.setContentsMargins(23, 22, 23, 16)
        outer.setSpacing(10)
        outer.addStretch(1)
        hero = W.QHBoxLayout()
        hero.setSpacing(14)
        intro = W.QVBoxLayout()
        intro.setSpacing(4)
        intro.addWidget(label('KRYPTOCORE VAULT', 'eyebrow'))
        intro.addWidget(label('Dein Tresor', 'welcomeTitle'))
        subtitle = label('Deine Logins bleiben lokal und verschlüsselt.', 'welcomeIntro')
        subtitle.setWordWrap(True)
        intro.addWidget(subtitle)
        hero.addLayout(intro, 1)
        emblem = label('', 'welcomeMark')
        emblem.setAlignment(C.Qt.AlignCenter)
        emblem.setFixedSize(78, 78)
        emblem.setPixmap(G.QPixmap(str(HERE / 'vault-emblem.png')).scaled(63, 63, C.Qt.KeepAspectRatio, C.Qt.SmoothTransformation))
        hero.addWidget(emblem)
        outer.addLayout(hero)
        outer.addSpacing(14)
        self.open_button = StartTile('Tresor öffnen', 'Eine Tresordatei auswählen', '↗',
                                     lambda: self.open(False, self.recent_vault()), primary=True)
        outer.addWidget(self.open_button)
        secondary = row(
            StartTile('Neuer Tresor', 'Einen Tresor anlegen', '+', lambda: self.open(True)),
            StartTile('Wiederherstellen', 'Mit dem Notfallblatt', '↺', self.recover),
        )
        secondary.setSpacing(10)
        outer.addLayout(secondary)
        self.other_vault = button('Anderen Tresor öffnen', lambda: self.open(False), 'chrome')
        self.other_vault.hide()
        outer.addWidget(self.other_vault, alignment=C.Qt.AlignLeft)
        outer.addStretch(2)
        divider = W.QFrame()
        divider.setObjectName('welcomeRule')
        divider.setFixedHeight(1)
        outer.addWidget(divider)
        footer = W.QHBoxLayout()
        icon = label('')
        icon.setPixmap(G.QPixmap(str(HERE / 'emblem.png')).scaled(20, 20, C.Qt.KeepAspectRatio, C.Qt.SmoothTransformation))
        footer.addWidget(icon)
        footer.addWidget(label('KryptoCoreLabs', 'muted'))
        footer.addStretch()
        footer.addWidget(label('Vorschau · Nur Testdaten', 'previewBadge'))
        outer.addLayout(footer)
        return page

    def recent_vault(self):
        if self.last_vault_path and Path(self.last_vault_path).is_file():
            return self.last_vault_path
        return ''

    def open_recent_at_startup(self):
        path = self.recent_vault()
        if path:
            self.open(False, path)

    def update_open_button(self):
        path = self.recent_vault()
        self.open_button.setText('Tresor entsperren' if path else 'Tresor öffnen')
        self.open_button.set_detail(Path(path).name if path else 'Eine Tresordatei auswählen')
        self.other_vault.setVisible(bool(path))

    def set_vault_mode(self, mode):
        self.vault_mode = mode
        self.firefox_epoch = secrets.token_hex(16)
        self.preferences.setValue('vault/mode', mode)
        if mode == 'strict':
            self.last_vault_path = ''
            self.preferences.remove('vault/recent')
        elif self.active_vault_path:
            self.last_vault_path = self.active_vault_path
            self.preferences.setValue('vault/recent', self.last_vault_path)
        self.preferences.sync()
        self.deadline = time.monotonic() + VAULT_IDLE_SECONDS[mode]
        self.update_open_button()

    def library(self):
        page = W.QWidget()
        layout = W.QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 8)
        layout.setSpacing(10)
        self.vault_name = label('', 'muted')
        self.vault_name.setWordWrap(True)
        intro = W.QVBoxLayout()
        intro.setSpacing(2)
        intro.addWidget(label('DEIN TRESOR', 'eyebrow'))
        intro.addWidget(label('Deine Logins', 'section'))
        intro.addWidget(self.vault_name)
        header = W.QHBoxLayout()
        header.addLayout(intro, 1)
        header.setStretch(0, 1)
        header.addWidget(button('Sperren', self.lock), alignment=C.Qt.AlignTop)
        layout.addLayout(header)
        new_login = StartTile('Neuer Login', 'Zugangsdaten speichern', '+', lambda: self.edit(), primary=True)
        new_login.setFixedHeight(65)
        layout.addWidget(new_login)
        library = tile(layout, 'GESPEICHERTE LOGINS')
        layout.setStretchFactor(library.parentWidget(), 1)
        self.search = W.QLineEdit(placeholderText='Website oder Benutzername suchen')
        self.search.setAccessibleName('Logins suchen')
        self.search.textChanged.connect(self.refresh)
        library.addWidget(self.search)
        self.logins = W.QListWidget()
        self.logins.setAccessibleName('Gespeicherte Logins')
        self.logins.setMinimumHeight(78)
        self.logins.setSpacing(3)
        self.logins.setTextElideMode(C.Qt.ElideRight)
        self.logins.itemDoubleClicked.connect(self.toggle_details)
        details_shortcut = G.QShortcut(G.QKeySequence('Return'), self.logins)
        details_shortcut.setContext(C.Qt.WidgetShortcut)
        details_shortcut.activated.connect(self.toggle_selected_details)
        library.addWidget(self.logins, 1)
        self.details = W.QFrame()
        self.details.setObjectName('details')
        card = W.QVBoxLayout(self.details)
        card.setContentsMargins(13, 11, 13, 11)
        card.setSpacing(5)
        self.detail_title = label('', 'section')
        self.detail_title.setWordWrap(True)
        detail_header = row(self.detail_title)
        detail_header.setStretch(0, 1)
        close_details = button('×', self.hide_details, 'chrome')
        close_details.setAccessibleName('Login-Details einklappen')
        close_details.setToolTip('Details einklappen')
        detail_header.addWidget(close_details)
        card.addLayout(detail_header)
        self.detail_site = label('', 'muted')
        self.detail_site.setWordWrap(True)
        card.addWidget(self.detail_site)
        card.addSpacing(3)
        self.detail_fields = W.QWidget()
        fields = W.QVBoxLayout(self.detail_fields)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(5)
        fields.addWidget(label('Benutzername', 'muted'))
        self.detail_user = W.QLineEdit(readOnly=True)
        self.detail_user.setAccessibleName('Benutzername')
        fields.addWidget(self.detail_user)
        fields.addWidget(label('Passwort', 'muted'))
        self.detail_password = W.QLineEdit(readOnly=True, placeholderText='Verborgen')
        self.detail_password.setAccessibleName('Passwort des ausgewählten Logins')
        self.reveal_button = button('Anzeigen', lambda: self.selected(self.reveal))
        self.reveal_button.setAccessibleName('Passwort anzeigen oder verbergen')
        password_row = row(self.detail_password, self.reveal_button)
        password_row.setStretch(0, 1)
        fields.addLayout(password_row)
        fields.addLayout(row(button('Bearbeiten', lambda: self.selected(self.edit)),
                             button('Löschen', lambda: self.selected(self.remove))))
        card.addWidget(self.detail_fields)
        layout.addWidget(self.details)
        self.reveal_timer = C.QTimer(self, interval=30000, singleShot=True)
        self.reveal_timer.timeout.connect(self.hide_detail_password)
        self.logins.currentItemChanged.connect(self.hide_details)
        self.status = label('', 'muted')
        layout.addWidget(self.status)
        self.hide_details()
        return page

    def eventFilter(self, watched, event):
        if event.type() in (C.QEvent.KeyPress, C.QEvent.MouseButtonPress):
            self.deadline = time.monotonic() + VAULT_IDLE_SECONDS[self.vault_mode]
        return super().eventFilter(watched, event)

    def check_idle(self):
        if self.process and time.monotonic() >= self.deadline:
            self.lock()
        self.update_firefox_status()

    def request(self, **payload):
        if self.process is None:
            raise VaultError('Der Tresor ist gesperrt.')
        try:
            self.process.stdin.write(json.dumps(payload) + '\n')
            self.process.stdin.flush()
            reply = json.loads(self.process.stdout.readline())
        except (OSError, ValueError) as error:
            self.lock()
            raise VaultError('Vault-Verbindung wurde beendet.') from error
        if 'error' in reply:
            raise VaultError(reply['error'])
        return reply

    def stop_session(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()
        finally:
            process.stdout.close()

    def lock(self):
        self.firefox_epoch = secrets.token_hex(16)
        self.cancel_firefox_requests()
        for dialog in reversed(self.findChildren(W.QDialog)):
            if dialog.isVisible():
                dialog.reject()
        self.stop_session()
        self.entries = []
        self.active_vault_path = ''
        self.search.clear()
        self.refresh()
        self.pages.setCurrentIndex(0)
        self.update_open_button()
        self.open_button.setFocus()
        self.update_firefox_status()

    def closeEvent(self, event):
        self.lock()
        if self.session_window is not None:
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(wintypes.HWND(self.session_window))
            self.session_window = None
        self.firefox_server.close()
        if self.firefox_lock is not None and self.firefox_lock.isLocked():
            self.firefox_lock.unlock()
        super().closeEvent(event)

    def show_panel(self, dialog):
        self.dialog = dialog
        try:
            return dialog.exec()
        finally:
            self.dialog = None

    def open(self, create, path=''):
        epoch = self.firefox_epoch
        if not create and not path:
            path, _ = W.QFileDialog.getOpenFileName(self, 'Tresor öffnen', '', 'KryptoCore-Tresor (*.kcv)')
            if not path or self.firefox_epoch != epoch:
                return
        dialog = Panel(self, 'Neuer Tresor' if create else 'Tresor entsperren',
                       'Wähle, wo dein Tresor liegt und wie du ihn öffnest.' if create else Path(path).name)
        if create:
            destination = dialog.field('Speicherort')
            destination.setReadOnly(True)
            destination.setPlaceholderText('Ordner und Dateinamen wählen')

            def choose_location():
                nonlocal path, recovery
                chosen, _ = W.QFileDialog.getSaveFileName(dialog, 'Tresordatei speichern', 'Mein Tresor.kcv',
                                                         'KryptoCore-Tresor (*.kcv)')
                if chosen:
                    next_path = chosen if chosen.lower().endswith('.kcv') else chosen + '.kcv'
                    if path != next_path:
                        recovery = None
                    path = next_path
                    destination.setText(path)
                    destination.setToolTip(path)
                    dialog.error.clear()
                    password.setFocus()

            choose = button('Auswählen', choose_location)
            location_row = row(destination, choose)
            location_row.setStretch(0, 1)
            dialog.layout.addLayout(location_row)
        password = dialog.secret('Tresorpasswort')
        if create:
            strength = W.QProgressBar(minimum=0, maximum=5, textVisible=False)
            feedback = label('', 'muted')
            feedback.setWordWrap(True)
            dialog.layout.addWidget(strength)
            dialog.layout.addWidget(feedback)
            confirm = dialog.secret('Tresorpasswort bestätigen')
            hint = label('Verwende in dieser Vorschau nur Testdaten. Im nächsten Schritt speicherst du dein Notfallblatt.', 'muted')
            hint.setWordWrap(True)
            dialog.layout.addWidget(hint)
            estimate_timer = C.QTimer(dialog, interval=180, singleShot=True)

            def estimate():
                value = password.text()
                if not value:
                    score, text = 0, 'Mindestens 15 Zeichen. Eine lange Passphrase ist möglich.'
                elif len(value) < 15:
                    score, text = 1, f'Noch {15 - len(value)} Zeichen bis zur Mindestlänge.'
                elif zxcvbn is None or len(value) > 72:
                    score, text = 0, 'Mindestlänge erreicht · Stärkeschätzung nicht verfügbar.'
                else:
                    score = zxcvbn(value, user_inputs=['kryptocore', 'vault'])['score'] + 1
                    text = 'Stärkeschätzung: ' + ['sehr schwach', 'schwach', 'mittel', 'gut', 'stark'][score - 1]
                    if score <= 2:
                        text += ' · Versuche eine längere, ungewöhnliche Passphrase.'
                strength.setValue(score)
                feedback.setText(text)

            estimate_timer.timeout.connect(estimate)
            password.textChanged.connect(lambda _: estimate_timer.start())
            estimate()

        def unlock():
            nonlocal recovery
            if create and not path:
                dialog.error.setText('Wähle zuerst einen Speicherort für den Tresor.')
                choose.setFocus()
                return
            if create and Path(path).exists():
                dialog.error.setText('An diesem Speicherort gibt es schon eine Datei. Wähle einen neuen Namen.')
                return
            if create and len(password.text()) < 15:
                dialog.error.setText('Das Tresorpasswort braucht mindestens 15 Zeichen.')
                return
            if create and password.text() != confirm.text():
                dialog.error.setText('Die Passwörter stimmen noch nicht überein.')
                return
            try:
                if create and recovery is None:
                    recovery = self.show_new_recovery_sheet(dialog, Path(path).name)
                    if recovery is None or self.firefox_epoch != epoch:
                        return
                self.process = subprocess.Popen(
                    [str(backend()), 'desktop-session'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                self.entries = self.request(action='open', path=path, password=password.text(), create=create,
                                            recovery=recovery)['entries']
            except (OSError, VaultError) as error:
                self.stop_session()
                dialog.error.setText(str(error))
                return
            password.clear()
            if create:
                confirm.clear()
            self.deadline = time.monotonic() + VAULT_IDLE_SECONDS[self.vault_mode]
            dialog.accept()

        recovery = None
        dialog.finish('Weiter zum Notfallblatt' if create else 'Entsperren', unlock)
        (choose if create else password).setFocus()
        if self.show_panel(dialog):
            self.show_library(path)
        dialog.deleteLater()

    def show_new_recovery_sheet(self, parent, vault_name):
        recovery = secrets.token_hex(32)
        dialog = Panel(parent, 'Dein Notfallblatt',
                       'Mit diesem Blatt und deiner Tresordatei kannst du ein neues Tresorpasswort setzen.')
        warning = label(
            'Wer beides hat, kann deinen Tresor öffnen. Bewahre das Blatt getrennt vom Tresor '
            'an einem geschützten Ort auf. Bei einer verlorenen oder beschädigten Tresordatei brauchst du eine Sicherung.', 'muted',
        )
        warning.setWordWrap(True)
        dialog.layout.addWidget(warning)
        preview = label('', 'recoveryCode')
        preview.setAlignment(C.Qt.AlignCenter)
        preview.hide()
        dialog.layout.addWidget(preview)
        preview_timer = C.QTimer(dialog, interval=30000, singleShot=True)

        def set_preview(show):
            preview.setText(f'{recovery[:32]}\n{recovery[32:]}' if show else '')
            preview.setVisible(show)
            reveal.setText('Schlüssel verbergen' if show else 'Schlüssel anzeigen')
            if show:
                preview_timer.start()
            else:
                preview_timer.stop()

        def save():
            try:
                if self.save_recovery_sheet(dialog, vault_name, recovery):
                    dialog.accept()
            except (OSError, VaultError) as error:
                dialog.error.setText(str(error))

        reveal = button('Schlüssel anzeigen', lambda: set_preview(preview.isHidden()), 'chrome')
        preview_timer.timeout.connect(lambda: set_preview(False))
        dialog.layout.addWidget(reveal, alignment=C.Qt.AlignLeft)
        dialog.layout.addWidget(dialog.error)
        submit = button('PDF speichern und fortfahren', save, 'primary')
        submit.setDefault(True)
        dialog.layout.addLayout(row(button('Zurück', dialog.reject), submit))
        accepted = dialog.exec()
        preview.clear()
        dialog.deleteLater()
        return recovery if accepted else None

    def save_recovery_sheet(self, parent, vault_name, recovery):
        epoch = self.firefox_epoch
        path, _ = W.QFileDialog.getSaveFileName(parent, 'Notfallblatt speichern', 'Vault-Notfallblatt.pdf', 'PDF (*.pdf)')
        if not path or self.firefox_epoch != epoch:
            return False
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        if Path(path).exists():
            raise VaultError('Wähle einen neuen Dateinamen, damit ein vorhandenes Notfallblatt erhalten bleibt.')
        write_recovery_pdf(path, vault_name, recovery)
        return True

    def enable_recovery(self):
        dialog = Panel(self, 'Notfallblatt', 'Speichere das Blatt getrennt vom Tresor. Nach dem Erneuern gilt das neue Blatt für die aktuelle Tresordatei. Alte Kopien können noch mit dem alten Schlüssel geöffnet werden.')

        def save_sheet():
            try:
                recovery = secrets.token_hex(32)
                if not self.save_recovery_sheet(dialog, self.vault_name.text(), recovery):
                    return
                self.request(action='enable_recovery', recovery=recovery)
            except (OSError, VaultError) as error:
                dialog.error.setText(str(error))
                return
            dialog.accept()
            self.status.setText('Wiederherstellung eingerichtet. Bewahre das Notfallblatt sicher auf.')

        dialog.finish('Notfallblatt speichern', save_sheet)
        self.show_panel(dialog)
        dialog.deleteLater()

    def recover(self):
        epoch = self.firefox_epoch
        path, _ = W.QFileDialog.getOpenFileName(self, 'Tresordatei wählen', '', 'KryptoCore-Tresor (*.kcv)')
        if not path or self.firefox_epoch != epoch:
            return
        dialog = Panel(self, 'Tresor wiederherstellen',
                       f'{Path(path).name}\nDas Passwort wird in dieser Datei zurückgesetzt. '
                       'Für einen Test wähle eine zusätzliche Kopie.')
        recovery = dialog.secret('Schlüssel vom Notfallblatt')
        password = dialog.secret('Neues Tresorpasswort')
        confirm = dialog.secret('Neues Tresorpasswort bestätigen')

        def reset():
            if len(password.text()) < 15 or password.text() != confirm.text():
                dialog.error.setText('Wähle mindestens 15 Zeichen und bestätige das neue Passwort.')
                return
            key = ''.join(recovery.text().split()).lower()
            try:
                self.process = subprocess.Popen(
                    [str(backend()), 'desktop-session'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                self.entries = self.request(action='recover', path=path, recovery=key, password=password.text())['entries']
            except (OSError, VaultError) as error:
                self.stop_session()
                dialog.error.setText(str(error))
                return
            self.deadline = time.monotonic() + VAULT_IDLE_SECONDS[self.vault_mode]
            dialog.accept()

        dialog.finish('Passwort zurücksetzen', reset)
        recovery.setFocus()
        if self.show_panel(dialog):
            self.show_library(path)
        dialog.deleteLater()

    def show_library(self, path):
        self.active_vault_path = str(Path(path).resolve())
        if self.vault_mode == 'standard':
            self.last_vault_path = self.active_vault_path
            self.preferences.setValue('vault/recent', self.last_vault_path)
            self.preferences.sync()
        self.update_open_button()
        self.vault_name.setText(Path(path).name)
        self.refresh()
        self.pages.setCurrentIndex(1)
        self.search.setFocus()
        self.update_firefox_status()

    def refresh(self):
        query = self.search.text().casefold()
        entries = sorted(self.entries, key=lambda item: item['origin'])
        current = self.logins.currentItem()
        previous = current.data(C.Qt.UserRole)['origin'] if current is not None else None
        self.logins.clear()
        selected_row = 0
        for entry in entries:
            if query not in f"{entry['origin']} {entry['username']}".casefold():
                continue
            if entry['origin'] == previous:
                selected_row = self.logins.count()
            site = entry['origin'].split('://', 1)[-1]
            item = W.QListWidgetItem(f"{site}\n{entry['username'] or 'Ohne Benutzername'}")
            item.setData(C.Qt.UserRole, entry)
            self.logins.addItem(item)
        if self.logins.count():
            self.logins.setCurrentRow(selected_row)
        self.status.setText(
            f'{self.logins.count()} von {len(entries)} Logins · Doppelklick für Details'
            if self.logins.count() else 'Keine passenden Logins'
        )

    def hide_detail_password(self):
        self.reveal_timer.stop()
        self.detail_password.clear()
        self.reveal_button.setText('Anzeigen')

    def hide_details(self, *_):
        self.hide_detail_password()
        self.detail_user.clear()
        self.detail_title.clear()
        self.detail_site.clear()
        self.details.hide()

    def toggle_details(self, item):
        if not self.details.isHidden():
            self.hide_details()
            return
        entry = item.data(C.Qt.UserRole)
        self.detail_title.setText(entry['origin'].split('://', 1)[-1])
        self.detail_site.setText(entry['origin'])
        self.detail_user.setText(entry['username'])
        self.details.show()

    def toggle_selected_details(self):
        item = self.logins.currentItem()
        if item is not None:
            self.toggle_details(item)

    def selected(self, fn):
        item = self.logins.currentItem()
        if item is None:
            self.status.setText('Wähle zuerst einen Login aus.')
            return
        try:
            fn(item.data(C.Qt.UserRole))
        except VaultError as error:
            self.status.setText(str(error))

    def edit(self, entry=None, *, initial_site=''):
        dialog = Panel(self, 'Login bearbeiten' if entry else 'Neuer Login')
        site = dialog.field('Website', entry['origin'] if entry else initial_site)
        site.setPlaceholderText('z. B. www.otto.de')
        dialog.layout.addWidget(site)
        username = dialog.field('Benutzername', entry['username'] if entry else '')
        dialog.layout.addWidget(username)
        if entry:
            current = dialog.field('Aktuelles Passwort')
            current.setReadOnly(True)
            current.setPlaceholderText('Verborgen')
            timer = C.QTimer(dialog, interval=30000, singleShot=True)

            def hide_current():
                timer.stop()
                current.clear()
                toggle.setText('Anzeigen')

            def toggle_current():
                if current.text():
                    hide_current()
                    return
                try:
                    value = self.request(action='reveal', site=entry['origin'])['password']
                except VaultError as error:
                    dialog.error.setText(str(error))
                    return
                current.setText(value)
                toggle.setText('Verbergen')
                timer.start()

            toggle = button('Anzeigen', toggle_current)
            toggle.setAccessibleName('Aktuelles Passwort anzeigen oder verbergen')
            current_row = row(current, toggle)
            current_row.setStretch(0, 1)
            dialog.layout.addLayout(current_row)
            timer.timeout.connect(hide_current)
            dialog.finished.connect(hide_current)
        password = dialog.secret('Neues Passwort' if entry else 'Passwort', generate=True)
        if entry:
            password.setPlaceholderText('Leer lassen, um das aktuelle Passwort zu behalten')

        def save():
            try:
                self.entries = self.request(action='put', previous=entry['origin'] if entry else None,
                                            site=site.text(), username=username.text(), password=password.text())['entries']
            except VaultError as error:
                dialog.error.setText(str(error))
                return
            password.clear()
            dialog.accept()
            self.refresh()

        dialog.finish('Login speichern', save)
        (username if initial_site else site).setFocus()
        self.show_panel(dialog)
        dialog.deleteLater()

    def reveal(self, entry):
        if self.detail_password.text():
            self.hide_detail_password()
            return
        value = self.request(action='reveal', site=entry['origin'])['password']
        self.detail_password.setText(value)
        self.reveal_button.setText('Verbergen')
        self.reveal_timer.start()

    def cancel_firefox_requests(self):
        self.firefox_candidate = None
        self.firefox_pair_until = 0
        self.firefox_seen = 0
        for socket in tuple(self.firefox_clients):
            socket.abort()

    def accept_firefox(self):
        while self.firefox_server.hasPendingConnections():
            socket = self.firefox_server.nextPendingConnection()
            socket.setReadBufferSize(FIREFOX_REQUEST_LIMIT + 4)
            if len(self.firefox_clients) >= 4:
                socket.abort()
                socket.deleteLater()
                continue
            self.firefox_clients.add(socket)
            timeout = C.QTimer(socket, interval=5000, singleShot=True)
            timeout.timeout.connect(socket.abort)
            timeout.start()

            def forget(client=socket):
                self.firefox_clients.discard(client)
                active = self.firefox_channels.pop(client, None)
                if active is not None:
                    active[0].close()
                client.deleteLater()

            socket.disconnected.connect(forget)
            socket.readyRead.connect(lambda client=socket: self.receive_firefox(client))
            self.receive_firefox(socket)

    def receive_firefox(self, socket):
        if socket.property('replied') or socket.bytesAvailable() < 4:
            return
        length = int.from_bytes(bytes(socket.peek(4)), 'little')
        if not 0 < length <= FIREFOX_REQUEST_LIMIT:
            socket.abort()
            return
        if socket.bytesAvailable() < 4 + length:
            return
        socket.read(4)
        try:
            request = json.loads(bytes(socket.read(length)))
            if not isinstance(request, dict) or request.get('v') != 5:
                raise ChannelError('Unsupported protocol')
            message = request.get('m')
            if not isinstance(message, str) or re.fullmatch('[0-9a-f]+', message) is None:
                raise ChannelError('Invalid frame')
            frame = bytes.fromhex(message)
            if socket in self.firefox_channels:
                channel, pairing, key = self.firefox_channels.pop(socket)
                try:
                    reply = self.firefox_secure_reply(channel, pairing, key, frame)
                    socket.setProperty('replied', True)
                finally:
                    channel.close()
            else:
                reply = self.firefox_handshake(socket, request.get('enroll'), frame)
        except (ValueError, OSError, RecursionError):
            socket.abort()
            return
        body = json.dumps(reply).encode('utf-8')
        socket.write(len(body).to_bytes(4, 'little') + body)
        socket.flush()

    def firefox_handshake(self, socket, pairing, frame):
        if type(pairing) is not bool or len(frame) != 48:
            raise ChannelError('Invalid handshake')
        key = self.firefox_candidate if pairing else self.firefox_key
        if pairing and (self.process is None or time.monotonic() >= min(self.deadline, self.firefox_pair_until)):
            key = None
        if key is None:
            socket.setProperty('replied', True)
            return {'v': 5, 'code': 'pair_required'}
        channel = Channel(self.firefox_library)
        try:
            channel.start(key, pairing)
            response = channel.step(0, frame)
        except ChannelError:
            channel.close()
            socket.setProperty('replied', True)
            return {'v': 5, 'code': 'pair_required'}
        self.firefox_channels[socket] = (channel, pairing, key)
        return {'v': 5, 'm': response.hex()}

    def firefox_secure_reply(self, channel, pairing, key, frame):
        request = json.loads(channel.step(2, frame))
        if not isinstance(request, dict):
            raise ChannelError('Invalid request')
        now = time.monotonic()
        epoch = self.firefox_epoch
        locked = self.process is None or now >= self.deadline
        action = request.get('action')
        if pairing:
            if (action != 'pair' or locked or key is not self.firefox_candidate
                    or now >= self.firefox_pair_until):
                reply = {'code': 'pair_required'}
            else:
                browser_secret = secrets.token_bytes(32)
                session_key = hmac.digest(browser_secret, FIREFOX_KEY_CONTEXT, 'sha256')
                write_local_file(self.firefox_key_path, firefox_key_dpapi(session_key, protect=True))
                self.firefox_key = session_key
                self.firefox_candidate = None
                self.firefox_pair_until = 0
                self.firefox_epoch = secrets.token_hex(16)
                reply = {'code': 'paired', 'key': browser_secret.hex()}
        elif key is not self.firefox_key:
            reply = {'code': 'pair_required'}
        elif locked:
            reply = {'code': 'locked'}
        elif action == 'status':
            reply = {
                'code': 'ready', 'loginLookup': True, 'saveLogin': self.vault_mode == 'standard',
                'directFill': self.vault_mode == 'standard', 'newLogin': True, 'session': epoch,
                'boundSave': True,
            }
        elif action in ('lookup', 'fill', 'fill_page', 'save', 'new_login'):
            site = request.get('site')
            if (not isinstance(site, str) or not site.isascii() or not site.startswith('https://')
                    or len(site) > 512 or any(ord(char) <= 32 for char in site)):
                raise ChannelError('Invalid HTTPS origin')
            payload = request.get('data')
            if action == 'save' and request.get('session') != epoch:
                reply = {'code': 'stale_session'}
            else:
                if action == 'save' and (not isinstance(payload, dict)
                        or len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()) > FIREFOX_LOGIN_LIMIT):
                    raise ChannelError('Invalid login')
                reply = self.firefox_site_reply(action, site, payload)
                if action in ('fill', 'fill_page') and (
                        self.process is None or self.firefox_epoch != epoch or time.monotonic() >= self.deadline):
                    reply = {'code': 'locked'}
        else:
            raise ChannelError('Invalid action')
        if reply.get('code') not in ('locked', 'pair_required'):
            self.firefox_seen = now
            self.update_firefox_status()
        data = json.dumps(reply, ensure_ascii=False).encode('utf-8')
        if len(data) > FIREFOX_REQUEST_LIMIT - 32:
            data = b'{"code":"too_large"}'
        return {'v': 5, 'm': channel.step(1, data).hex()}

    def firefox_site_reply(self, action, site, payload):
        entry = next((entry for entry in self.entries if entry['origin'] == site), None)
        if action == 'lookup':
            return {'code': 'login_found', 'username': entry['username']} if entry else {'code': 'no_login'}
        if action in ('fill', 'fill_page'):
            if action == 'fill_page' and self.vault_mode == 'strict':
                return {'code': 'direct_fill_disabled'}
            if entry is None:
                return {'code': 'no_login'}
            return {**self.firefox_login(entry), 'session': self.firefox_epoch}
        if action == 'new_login':
            if entry is not None:
                return {'code': 'exists'}
            if self.dialog is not None:
                return {'code': 'busy'}
            session = self.process

            def open_editor():
                if self.process is session and self.dialog is None and time.monotonic() < self.deadline:
                    if self.isMinimized():
                        self.showNormal()
                    self.raise_()
                    self.activateWindow()
                    W.QApplication.alert(self)
                    self.edit(initial_site=site)

            C.QTimer.singleShot(0, open_editor)
            return {'code': 'opening'}
        if self.vault_mode == 'strict':
            return {'code': 'save_disabled'}
        if entry is not None:
            return {'code': 'exists'}
        username = payload.get('username')
        password = payload.get('password')
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return {'code': 'invalid'}
        try:
            self.entries = self.request(action='put', site=site, username=username, password=password)['entries']
            self.refresh()
        except VaultError:
            return {'code': 'save_failed'}
        return {'code': 'saved'}

    def firefox_login(self, entry):
        try:
            return self.request(action='reveal', site=entry['origin'])
        except VaultError as error:
            return {'error': str(error)}

    def remove(self, entry):
        dialog = Panel(self, 'Login löschen?', entry['origin'], framed=False)
        dialog.error.hide()

        def delete():
            try:
                self.entries = self.request(action='remove', site=entry['origin'])['entries']
            except VaultError as error:
                dialog.error.setText(str(error))
                dialog.error.show()
                return
            dialog.accept()
            self.refresh()

        submit = dialog.finish('Login löschen', delete)
        submit.setAutoDefault(False)
        submit.setDefault(False)
        self.show_panel(dialog)
        dialog.deleteLater()


def main():
    app = W.QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Vault()
    window.show()
    C.QTimer.singleShot(0, window.open_recent_at_startup)
    window.open_button.setFocus()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
