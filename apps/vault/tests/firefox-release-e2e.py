"""Exercise the unchanged portable Vault EXE and signed XPI with public demo data."""
import argparse
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
from threading import Thread
import winreg

from pywinauto import Desktop
import win32api
import win32con
import win32process
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


HOST_KEY = r"Software\Mozilla\NativeMessagingHosts\com.kryptocorelabs.vault"
PIPE = "kryptocorelabs-vault-firefox-v5"
EXTENSION_ID = "vault@kryptocorelabs"
SITE = "https://localhost:8443"
PASSWORD = "Northstar demo vault only"
LOGIN_USER = "alex.demo"
LOGIN_PASSWORD = "synthetic-browser-login-only"


class LoginFixture(BaseHTTPRequestHandler):
    def do_GET(self):
        page = b"""<!doctype html><meta charset="utf-8"><title>Vault release smoke test</title>
        <form method="post">
        <input id="user" name="username" autocomplete="username">
        <input id="pass" name="password" type="password" autocomplete="current-password">
        <button type="submit">Sign in</button>
        </form><script>document.forms[0].onsubmit = e => { e.preventDefault();
        document.body.dataset.submitted = 'yes'; };</script>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *_):
        pass


@contextmanager
def server(folder):
    cert, key = folder / "localhost.pem", folder / "localhost.key"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
         "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
         "-keyout", key, "-out", cert], capture_output=True, check=True, timeout=20,
    )
    with ThreadingHTTPServer(("127.0.0.1", 8443), LoginFixture) as http:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        http.socket = context.wrap_socket(http.socket, server_side=True)
        thread = Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            yield
        finally:
            http.shutdown()
            thread.join()


def registration():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, HOST_KEY) as key:
            return winreg.QueryValueEx(key, "")
    except FileNotFoundError:
        return None


@contextmanager
def portable(executable, fixture, work):
    if PIPE in {name.lower() for name in os.listdir(r"\\.\pipe\.")}:
        raise RuntimeError("Close the active Vault window before the release test.")
    local = work / "local"
    settings = local / "KryptoCoreLabs" / "Vault"
    settings.mkdir(parents=True)
    copy = work / "synthetic.kcv"
    copy.write_bytes(fixture.read_bytes())
    (settings / "preferences.ini").write_text(
        f"[vault]\nrecent={copy.as_posix()}\n", encoding="utf-8")
    previous = registration()
    env = {**os.environ, "LOCALAPPDATA": str(local)}
    with subprocess.Popen([executable], env=env, cwd=work) as app:
        try:
            desktop = Desktop(backend="uia")
            window = desktop.window(title="KryptoCoreLabs Vault")
            window.wait("visible", timeout=30)
            candidate = window.element_info.process_id
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, candidate)
            try:
                if Path(win32process.GetModuleFileNameEx(handle, 0)).resolve() != executable:
                    raise RuntimeError("The visible Vault belongs to another process.")
                process = candidate
            finally:
                handle.Close()
            active = registration()
            if not active or not Path(active[0]).is_relative_to(settings):
                raise RuntimeError("Firefox native host did not register in the disposable settings folder.")
            print("Exact portable Vault process opened.", flush=True)
            yield desktop, window, process
        finally:
            if app.poll() is None:
                if "process" in locals():
                    try:
                        for item in desktop.windows(process=process):
                            item.close()
                    except Exception:
                        pass
                try:
                    app.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if "process" in locals() and process != app.pid:
                        try:
                            handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, process)
                            try:
                                win32api.TerminateProcess(handle, 1)
                            finally:
                                handle.Close()
                        except OSError:
                            pass
                    app.terminate()
                    app.wait(timeout=10)
            current = registration()
            if current and Path(current[0]).is_relative_to(local):
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, HOST_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    if previous is None:
                        winreg.DeleteValue(key, "")
                    else:
                        winreg.SetValueEx(key, "", 0, previous[1], previous[0])


def test(driver, addon, desktop, window, pid):
    def control(title, kind):
        def find(_):
            for top in desktop.windows(process=pid):
                for item in top.descendants(control_type=kind):
                    if item.element_info.name == title and item.is_visible() and item.is_enabled():
                        return item
            return None

        try:
            return WebDriverWait(driver, 10).until(find)
        except Exception:
            for top in desktop.windows(process=pid):
                print(ascii([(item.friendly_class_name(), item.element_info.name)
                             for item in top.descendants() if item.is_visible()]), flush=True)
            raise

    def button(container, title):
        item = container.child_window(title=title, control_type="Button")
        item.wait("visible enabled", timeout=10)
        item.invoke()

    def unlock():
        button(window, "Tresor entsperren")
        control("Tresorpasswort", "Edit").set_edit_text(PASSWORD)
        control("Entsperren", "Button").invoke()
        window.child_window(title="Sperren", control_type="Button").wait("visible enabled", timeout=12)

    def popup(script, *args):
        with driver.context("chrome"):
            return driver.execute_script("""
                const doc = document.querySelector('browser.webextension-popup-browser')?.contentDocument;
            """ + script, *args)

    def open_popup():
        with driver.context("chrome"):
            driver.find_element(By.ID, "vault_kryptocorelabs-BAP").click()
        WebDriverWait(driver, 10).until(lambda _: popup("return !!doc?.querySelector('#site');"))

    def state(selector, value):
        read = "return doc?.querySelector(arguments[0])?.textContent;"
        try:
            WebDriverWait(driver, 8).until(lambda _: value in (popup(read, selector) or ""))
        except Exception as error:
            raise AssertionError(f"{selector}: expected {value!r}, got {popup(read, selector)!r}, "
                                 f"site={popup(read, '#site')!r}") from error

    def close_popup():
        popup("doc?.defaultView.close();")
        WebDriverWait(driver, 8).until(lambda _: popup("return !doc;"))

    def values():
        return [driver.find_element(By.ID, field).get_property("value") for field in ("user", "pass")]

    unlock()
    assert driver.install_addon(str(addon), temporary=False) == EXTENSION_ID
    with driver.context("chrome"):
        signed = driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const { AddonManager } = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
            AddonManager.getAddonByID(arguments[0]).then(a => done(
                Services.prefs.getBoolPref('xpinstall.signatures.required') &&
                a.isActive && !a.temporarilyInstalled && a.signedState >= AddonManager.SIGNEDSTATE_SIGNED));
        """, EXTENSION_ID)
        assert signed
        driver.execute_script(
            "CustomizableUI.addWidgetToArea('vault_kryptocorelabs-browser-action', CustomizableUI.AREA_NAVBAR);")
    driver.get(SITE)
    open_popup()
    button(window, "Firefox-Verbindung")
    control("Verbindungscode erstellen", "Button").invoke()
    code_field = control("Firefox-Verbindungscode", "Edit")
    code = code_field.get_value()
    assert len(code) == 64
    popup("doc.querySelector('#pairing-code').value=arguments[0]; "
          "doc.querySelector('#pair-firefox').requestSubmit();", code)
    state("#connection", "Mit Vault verbunden")
    control("Schließen", "Button").invoke()
    print("Mozilla-signed XPI installed permanently and paired with disposable Vault settings.", flush=True)

    popup("doc.querySelector('#request button').click();")
    WebDriverWait(driver, 12).until(lambda _: values() == [LOGIN_USER, LOGIN_PASSWORD])
    assert driver.execute_script("return document.body.dataset.submitted") is None
    print("Matching HTTPS origin filled on request; form did not submit.", flush=True)
    close_popup()

    driver.get("https://127.0.0.1:8443/")
    open_popup()
    state("#connection", "Mit Vault verbunden")
    state("#offer", "noch kein Login gespeichert")
    assert popup("return doc.querySelector('#request button').hidden;")
    assert values() == ["", ""]
    close_popup()

    driver.get(SITE)
    open_popup()
    state("#connection", "Mit Vault verbunden")
    state("#offer", "Gespeicherter Login")
    popup("""doc.querySelector('#request button').click();
        gBrowser.selectedBrowser.loadURI(Services.io.newURI(arguments[0]),
        {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});""", SITE + "/changed")
    WebDriverWait(driver, 10).until(lambda _: driver.current_url.endswith("/changed"))
    assert values() == ["", ""]
    close_popup()
    print("Different HTTPS origin and a new document left target fields empty.", flush=True)

    original = driver.current_window_handle
    driver.switch_to.new_window("tab")
    destination = driver.current_window_handle
    driver.get(SITE + "/other-tab")
    driver.switch_to.window(original)
    driver.get(SITE + "/tab-source")
    open_popup()
    state("#connection", "Mit Vault verbunden")
    state("#offer", "Gespeicherter Login")
    popup("""doc.querySelector('#request button').click();
        gBrowser.selectedTab = Array.from(gBrowser.tabs).find(tab =>
            tab.linkedBrowser.currentURI.spec.endsWith('/other-tab'));""")
    driver.switch_to.window(destination)
    assert values() == ["", ""]
    close_popup()
    print("Switching tabs left the other form empty.", flush=True)

    button(window, "Sperren")
    driver.refresh()
    open_popup()
    state("#connection", "Vault gesperrt")
    assert popup("return doc.querySelector('#request button').disabled;")
    assert values() == ["", ""]
    unlock()
    state("#connection", "Mit Vault verbunden")
    state("#offer", "Gespeicherter Login")
    popup("doc.querySelector('#request button').click();")
    WebDriverWait(driver, 12).until(lambda _: values() == [LOGIN_USER, LOGIN_PASSWORD])
    print("Lock blocked access, and unlock restored autofill with the same pairing.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("vault", "addon", "fixture", "firefox", "geckodriver"):
        parser.add_argument(f"--{name}", type=lambda p: Path(p).resolve(), required=True)
    args = parser.parse_args()
    print(f"Vault SHA-256 {sha256(args.vault.read_bytes()).hexdigest()}", flush=True)
    print(f"XPI SHA-256 {sha256(args.addon.read_bytes()).hexdigest()}", flush=True)
    with tempfile.TemporaryDirectory(prefix="kcv-release-test-") as folder:
        work = Path(folder)
        with server(work), portable(args.vault, args.fixture, work) as (desktop, window, pid):
            options = Options()
            options.binary_location = str(args.firefox)
            options.add_argument("-headless")
            options.accept_insecure_certs = True
            options.set_preference("xpinstall.signatures.required", True)
            options.set_preference("extensions.webextensions.remote", False)
            options.set_preference("signon.rememberSignons", False)
            with webdriver.Firefox(service=Service(str(args.geckodriver), service_args=["--allow-system-access"]),
                                   options=options) as driver:
                print(f"Firefox {driver.capabilities['browserVersion']}", flush=True)
                test(driver, args.addon, desktop, window, pid)


if __name__ == "__main__":
    main()
