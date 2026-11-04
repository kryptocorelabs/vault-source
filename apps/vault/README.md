# KryptoCore Vault 0.1.0-rc.2

Lokaler Passwortmanager mit Desktop- und Terminaloberfläche sowie Browser-Popup.
Verwende für diese Entwicklungsvorschau ausschließlich Testdaten. Die Formate
`KCV1` und `KCV2` können sich noch ändern.

Vault verschlüsselt gespeicherte Logins lokal. Softwarefehler, Geräteausfall
und verlorene Zugänge können trotzdem zu Datenverlust führen. Gesetzliche
Rechte und die gesetzlich vorgesehene Haftung bleiben unberührt.
Die [Nutzungshinweise](USAGE.md) und der [Meldeweg für Sicherheitslücken](SECURITY.md)
erklären, wie du Sicherungen prüfst und Probleme vertraulich meldest.

Die [Lizenzhinweise und Abhängigkeitsliste](../../THIRD_PARTY_NOTICES.md)
beschreiben die Bestandteile der Desktop- und Firefox-Pakete.

## Tresor ausprobieren

Unter Windows kannst du [Vault öffnen](desktop/vault.pyw), wenn Python, Qt für
Python und das gebaute Rust-Backend vorhanden sind. Installiere die Abhängigkeiten
mit `python -m pip install -r apps/vault/desktop/requirements.txt`. Im Projektordner
startest du die Oberfläche mit `python apps/vault/desktop/vault.pyw`. Zum Bauen des Backends dient
`cargo build --locked --release -p kryptocore-vault -p vault-firefox-channel`.

In der Oberfläche kannst du einen Tresor anlegen oder öffnen, Einträge suchen,
bearbeiten und löschen und Passwörter erzeugen. Mit **Sperren**, `Strg+L` oder
nach der Sperrfrist endet die Sitzung. Firefox kann erst nach dem Entsperren
wieder Logins abrufen.

Beim Anlegen eines Tresors wählst du ein Tresorpasswort oder eine Passphrase.
Die lokale Stärkeschätzung mit zxcvbn ist eine Orientierung.
Passphrasen mit mehr als 72 Zeichen werden akzeptiert und liegen außerhalb des
Schätzbereichs. Über **Anzeigen** kannst du auch neu erzeugte Passwörter vor dem
Speichern prüfen.

In den **Einstellungen** wählst du den Sicherheitsmodus. **Alltag** merkt
sich die letzte Tresordatei, fragt beim Start direkt nach dem Passwort und
sperrt nach fünf Minuten ohne Eingabe in Vault. **Streng** merkt sich keinen
Dateipfad, sperrt nach einer Minute und lässt neue Logins nur in der
Desktop-App speichern. Beide Modi verwenden dieselbe Tresorverschlüsselung
und dieselbe Wiederherstellung.

Unter **Darstellung** lässt sich der leichte Glas-Effekt für den
Fensterhintergrund unter Windows ein- und ausschalten.

### Terminal

Aus dem Repository-Stamm mit einer aktuellen Rust-Toolchain ausführen.

```sh
cargo run --locked --release -p kryptocore-vault -- init demo.kcv
cargo run --locked --release -p kryptocore-vault -- add demo.kcv https://example.com
cargo run --locked --release -p kryptocore-vault -- list demo.kcv
```

Das Terminal fragt Passwörter verdeckt ab. `list` zeigt die Website und den
Benutzernamen. `remove demo.kcv https://example.com` löscht den Eintrag. Pro
HTTPS-Origin ist in dieser Vorschau ein Login vorgesehen. Jeder Befehl öffnet
den Tresor neu. Beim Beenden werden die gehaltenen Einträge verworfen.

## Login im Browser abrufen

### Firefox unter Windows

1. Das Firefox-Add-on ab Version 0.1.15 installieren und den Tresor in Vault
   ab 0.1.0-rc.2 entsperren.
2. Bei der ersten Kopplung in Vault unter **Firefox → Verbindungscode erstellen**
   einen Code erzeugen und im Add-on eingeben. Der Code ist zwei Minuten
   gültig und wird bei erfolgreicher Kopplung verbraucht.

Beim Öffnen prüft das Add-on das Anmeldeformular im aktiven HTTPS-Tab.
Ein gespeicherter Eintrag wird dort angeboten. Über **Login ausfüllen**
kannst du ihn einsetzen. Bei getrennten
Anmeldeschritten denselben Button auf dem Passwortschritt erneut wählen. Prüfe
die Felder und melde dich selbst an. Wenn das Add-on kein eindeutiges Formular
erkennt, kannst du den passenden Login im Add-on manuell übernehmen. Über
**Website für Vault kopieren** kannst du die Adresse des Tabs beim Anlegen
eines Eintrags übernehmen.

Ab Version 0.1.8 erkennt das Add-on auch JavaScript-Formulare wie im
Brunata-Portal. Formulare, die Zugangsdaten per GET oder an eine andere
Website senden könnten, bleiben vom automatischen Ausfüllen ausgeschlossen.

Ab Version 0.1.9 bewertet Vault Anmeldeformulare getrennt. Stehen mehrere
plausible Formulare zur Auswahl, klicke zuerst in das gewünschte Anmeldefeld
und öffne das Add-on. Eingebettete Formulare werden berücksichtigt, wenn
ihre HTTPS-Origin mit der des Tabs übereinstimmt.

Im Modus **Alltag** kannst du ein ausgefülltes Anmeldeformular über **Login in
Vault speichern** als neuen Eintrag übernehmen. Die Felder werden erst bei
dieser Aktion für das Speichern ausgelesen. Bearbeite vorhandene Einträge in
Vault. Das Add-on speichert nur für die Adresse des aktuellen HTTPS-Tabs.

Ab Version 0.1.11 kannst du im Firefox-Popup die Formularerkennung für alle
HTTPS-Websites einschalten. Firefox fragt einmal nach der Berechtigung. In
diesem Modus prüft das Add-on die Formularstruktur und zeigt bei einem Treffer
einen Hinweis. Ein Klick darauf öffnet das Firefox-Popup.

Schalte den **Website-Assistenten** für eine einzelne Website ein, um die
Kurzaktionen direkt auf der Seite zu nutzen. Bei einem gespeicherten Login
füllt **Ausfüllen** die passenden Felder. Ohne passenden Eintrag öffnet
**Login anlegen** den Editor in Vault mit vorausgefüllter Website. Nach dem
Absenden eines unterstützten Formulars kannst du im Modus **Alltag** einen
neuen Login im Firefox-Popup speichern. Dort kannst du die Freigaben auch
wieder ausschalten. **Alt+Umschalt+K** öffnet das Add-on.

Firefox 0.1.14 und Vault 0.1.0-rc.2 binden das Speichern an die aktive
Tresorsitzung. Bestehende v5-Kopplungen aus RC.1 bleiben gültig.
Über **Firefox trennen** kannst du die Kopplung widerrufen.

Vault und Firefox authentifizieren und verschlüsseln jede Anfrage mit einer
frischen Noise-Sitzung. Der Helfer leitet verschlüsselte Nachrichten weiter.
Vault schützt seinen Verbindungsschlüssel mit Windows DPAPI. Firefox hält
seinen dauerhaften Schlüssel als nicht exportierbaren Web-Crypto-Schlüssel.
Abrufe sind an die exakte HTTPS-Origin einschließlich Port gebunden. Im Modus
**Streng** erfolgt das Ausfüllen über das Firefox-Popup.

Vault sperrt sich bei Inaktivität, beim Sperren oder Trennen der
Windows-Sitzung sowie beim Ruhezustand. Browser und Windows-Konto gehören
zur Vertrauensgrenze. Nach dem Ausfüllen kann die passende Website die
eingefügten Zugangsdaten lesen.
Die [Firefox-Release-Notizen](FIREFOX_RELEASE.md) beschreiben den Weg zur
dauerhaft installierbaren, signierten Version.

### Chrome und Edge

Im Entwicklermodus `apps/vault/extension` als entpackte Erweiterung laden.
Den Login für die passende HTTPS-Seite über das Terminal einmalig freigeben
und den angezeigten Code im Add-on eingeben.

```sh
cargo run --locked --release -p kryptocore-vault -- share demo.kcv https://example.com
```

## Sicherung und Wiederherstellung

Wähle im entsperrten Tresor **Einstellungen → Sicherung erstellen**. Vault
prüft die Tresordatei und speichert eine verschlüsselte Kopie. Vorhandene
Dateien werden dabei geschützt. Lege regelmäßig datierte Kopien auf einem
getrennten Datenträger ab. Zum Testen öffnest du eine zusätzliche Kopie
oder setzt dort mit **Wiederherstellen** das Tresorpasswort zurück.

Beim Anlegen eines Tresors zeigt Vault das Notfallblatt in einem eigenen
Schritt. Speichere es als PDF und bewahre es geschützt und getrennt von der
Tresordatei auf. Wer Datei und Blatt besitzt, kann ein neues Tresorpasswort
setzen. Bei einem entsperrten Tresor kannst du das Blatt unter
**Einstellungen → Notfallblatt einrichten oder erneuern** verwalten. Alte Dateikopien behalten
ihre alten Zugänge. Frühere Vault-Versionen unterstützen `KCV2` nicht.

YubiKey und Passwort-Sperrliste folgen separat.
