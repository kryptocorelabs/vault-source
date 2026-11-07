#![forbid(unsafe_code)]

mod browser;
mod container;
mod desktop;

use std::{
    env,
    fs::{File, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
    process::ExitCode,
};

use kryptocore_vault_format::Login;
use url::Url;
use zeroize::Zeroizing;

fn origin(input: &str) -> Result<String, &'static str> {
    let input = input.trim();
    let with_scheme;
    let explicit_scheme = input.contains("://");
    let input = if explicit_scheme {
        input
    } else {
        if input.is_empty() || input.starts_with(['/', '\\']) {
            return Err("Website erwartet, zum Beispiel www.otto.de");
        }
        with_scheme = format!("https://{input}");
        &with_scheme
    };
    let url = Url::parse(input).map_err(|_| "HTTPS-Adresse erwartet")?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err("Website ohne eingebettete Zugangsdaten erwartet");
    }
    if explicit_scheme {
        Ok(url.origin().ascii_serialization())
    } else {
        Ok(url[url::Position::BeforeHost..url::Position::AfterPort].to_owned())
    }
}

fn secret(prompt: &str) -> Result<Zeroizing<String>, &'static str> {
    rpassword::prompt_password(prompt)
        .map(Zeroizing::new)
        .map_err(|_| "Passworteingabe fehlgeschlagen")
}

fn line(prompt: &str) -> Result<String, &'static str> {
    print!("{prompt}");
    io::stdout().flush().map_err(|_| "Ausgabefehler")?;
    let mut value = String::new();
    io::stdin()
        .read_line(&mut value)
        .map_err(|_| "Eingabefehler")?;
    Ok(value.trim_end_matches(['\r', '\n']).to_owned())
}

fn run() -> Result<(), &'static str> {
    let mut args = env::args_os().skip(1);
    let command = args
        .next()
        .and_then(|arg| arg.into_string().ok())
        .ok_or(USAGE)?;
    if command == "desktop-session" && args.len() == 0 {
        return desktop::run();
    }
    let path = PathBuf::from(args.next().ok_or(USAGE)?);
    let site = match command.as_str() {
        "add" | "share" | "remove" => Some(origin(
            &args
                .next()
                .and_then(|arg| arg.into_string().ok())
                .ok_or(USAGE)?,
        )?),
        "init" | "list" => None,
        _ => return Err(USAGE),
    };
    if args.next().is_some() {
        return Err(USAGE);
    }

    // A stable sidecar coordinates writers across atomic vault replacements.
    let _lock = if matches!(command.as_str(), "init" | "add" | "remove") {
        Some(lock_writer(&path)?)
    } else {
        None
    };

    let password = secret("Tresorpasswort: ")?;
    if command == "init" {
        if password.chars().count() < 15 {
            return Err("Mindestens 15 Zeichen verwenden");
        }
        if *password != *secret("Tresorpasswort wiederholen: ")? {
            return Err("Passwörter stimmen nicht überein");
        }
        container::save(&path, password.as_bytes(), b"[]", true)?;
        println!("Tresor erstellt.");
        return Ok(());
    }

    let data = container::open(&path, password.as_bytes())?;
    let mut logins: Vec<Login> =
        serde_json::from_slice(&data).map_err(|_| "Ungültige Tresoreinträge")?;
    drop(data);
    match (command.as_str(), site) {
        ("list", _) => {
            for entry in &logins {
                println!("{}  {:?}", entry.origin, entry.username);
            }
        }
        ("share", Some(site)) => {
            drop(password);
            let index = logins
                .iter()
                .position(|entry| entry.origin == site)
                .ok_or("Kein Login für diese Adresse")?;
            let entry = logins.swap_remove(index);
            drop(logins);
            browser::share(entry)?;
        }
        ("add", Some(site)) => {
            if logins.iter().any(|entry| entry.origin == site) {
                return Err("Für diese Adresse existiert bereits ein Eintrag");
            }
            let username = line("Benutzername: ")?;
            let mut login_password = secret("Login-Passwort: ")?;
            if login_password.is_empty() {
                return Err("Login-Passwort fehlt");
            }
            logins.push(Login {
                origin: site,
                username,
                password: std::mem::take(&mut *login_password),
            });
            save(&path, &password, &logins)?;
            println!("Tresor gespeichert.");
        }
        ("remove", Some(site)) => {
            let index = logins
                .iter()
                .position(|entry| entry.origin == site)
                .ok_or("Kein Login für diese Adresse")?;
            logins.remove(index);
            save(&path, &password, &logins)?;
            println!("Tresor gespeichert.");
        }
        _ => return Err(USAGE),
    }
    Ok(())
}

fn lock_writer(path: &Path) -> Result<File, &'static str> {
    let mut lock_path = path.as_os_str().to_os_string();
    lock_path.push(".lock");
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(lock_path)
        .map_err(|_| "Sperrdatei konnte nicht geöffnet werden")?;
    lock.try_lock()
        .map_err(|_| "Tresor wird bereits bearbeitet")?;
    Ok(lock)
}

fn save(path: &Path, password: &str, logins: &[Login]) -> Result<(), &'static str> {
    let bytes = Zeroizing::new(
        serde_json::to_vec(logins).map_err(|_| "Einträge konnten nicht kodiert werden")?,
    );
    container::save(path, password.as_bytes(), &bytes, false)
}

const USAGE: &str = "kryptocore-vault <init|list> <datei>\nkryptocore-vault <add|remove|share> <datei> <https-adresse>";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_https_origin_includes_nondefault_port() {
        assert_eq!(origin(" www.otto.de "), Ok("www.otto.de".into()));
        assert_eq!(
            origin("example.com:8443/path"),
            Ok("example.com:8443".into())
        );
        assert_eq!(
            origin("https://example.com:8443/path"),
            Ok("https://example.com:8443".into())
        );
        assert_eq!(
            origin("http://example.com"),
            Ok("http://example.com".into())
        );
        assert!(origin("https://user@example.com").is_err());
        assert!(origin("//example.com").is_err());
        assert!(origin("ftp://example.com").is_err());
    }

    #[test]
    fn vault_roundtrip_and_rejects_tampering() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("sample.kcv");
        container::save(&path, b"test password", b"synthetic secret", true).unwrap();
        assert!(container::save(&path, b"other", b"replacement", true).is_err());
        assert_eq!(
            &container::open(&path, b"test password").unwrap()[..],
            b"synthetic secret"
        );
        assert!(container::open(&path, b"wrong password").is_err());
        let mut file = std::fs::read(&path).unwrap();
        *file.last_mut().unwrap() ^= 1;
        std::fs::write(&path, file).unwrap();
        assert!(container::open(&path, b"test password").is_err());
    }
}
