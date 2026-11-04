use std::{
    io::{self, BufRead, Read, Write},
    path::PathBuf,
    sync::mpsc,
    thread,
};

use serde::Deserialize;
use serde_json::{json, Value};
use zeroize::Zeroizing;

use crate::{browser, container, lock_writer, origin, save, Login};

// A legal 4 MiB vault entry fits even when the GUI escapes Unicode in JSON.
const MAX_REQUEST: u64 = 16 * 1024 * 1024;

#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Open {
        path: PathBuf,
        password: Zeroizing<String>,
        create: bool,
        recovery: Option<Zeroizing<String>>,
    },
    Recover {
        path: PathBuf,
        recovery: Zeroizing<String>,
        password: Zeroizing<String>,
    },
    EnableRecovery {
        recovery: Zeroizing<String>,
    },
    Backup {
        destination: PathBuf,
    },
    Put {
        previous: Option<String>,
        site: String,
        username: String,
        password: Zeroizing<String>,
    },
    Remove {
        site: String,
    },
    Reveal {
        site: String,
    },
    Share {
        site: String,
    },
}

struct Session {
    path: PathBuf,
    password: Zeroizing<String>,
    share: Option<thread::JoinHandle<()>>,
}

impl Session {
    fn entries(&self) -> Result<Vec<Login>, &'static str> {
        let data = container::open(&self.path, self.password.as_bytes())?;
        serde_json::from_slice(&data).map_err(|_| "Ungültige Tresoreinträge")
    }

    fn handle(&mut self, request: Request) -> Result<Value, &'static str> {
        if let Request::Backup { destination } = &request {
            let _lock = lock_writer(&self.path)?;
            container::backup(&self.path, destination, self.password.as_bytes())?;
            return Ok(json!({}));
        }
        if let Request::EnableRecovery { recovery } = &request {
            check_recovery(recovery)?;
            let _lock = lock_writer(&self.path)?;
            container::enable_recovery(
                &self.path,
                self.password.as_bytes(),
                recovery.as_bytes(),
                false,
            )?;
            return Ok(json!({}));
        }
        let _lock = if matches!(request, Request::Put { .. } | Request::Remove { .. }) {
            Some(lock_writer(&self.path)?)
        } else {
            None
        };
        let mut entries = self.entries()?;
        let find = |site: &str| {
            entries
                .iter()
                .position(|entry| entry.origin == site)
                .ok_or("Eintrag wurde nicht gefunden")
        };
        match request {
            Request::Put {
                previous,
                site,
                username,
                mut password,
            } => {
                let site = origin(&site)?;
                let index = previous.as_deref().map(find).transpose()?;
                if entries
                    .iter()
                    .enumerate()
                    .any(|(i, entry)| Some(i) != index && entry.origin == site)
                {
                    return Err("Für diese Website existiert bereits ein Eintrag");
                }
                let password = if password.is_empty() {
                    let index = index.ok_or("Login-Passwort fehlt")?;
                    std::mem::take(&mut entries[index].password)
                } else {
                    std::mem::take(&mut *password)
                };
                let entry = Login {
                    origin: site,
                    username,
                    password,
                };
                if let Some(index) = index {
                    entries[index] = entry;
                } else {
                    entries.push(entry);
                }
            }
            Request::Remove { site } => {
                let index = find(&site)?;
                entries.remove(index);
            }
            Request::Reveal { site } => {
                let index = find(&site)?;
                let entry = &mut entries[index];
                let mut reply = json!({
                    "origin": entry.origin,
                    "username": entry.username,
                });
                reply["password"] = Value::String(std::mem::take(&mut entry.password));
                return Ok(reply);
            }
            Request::Share { site } => {
                browser::validate_site(&site)?;
                if self
                    .share
                    .as_ref()
                    .is_some_and(|worker| !worker.is_finished())
                {
                    return Err("Es läuft bereits eine Browser-Freigabe");
                }
                let index = find(&site)?;
                let entry = entries.swap_remove(index);
                let (send, receive) = mpsc::sync_channel(1);
                self.share = Some(thread::spawn(move || {
                    let _ = browser::share_with(&entry, |port, token| {
                        send.send(format!("{port}:{token}"))
                            .map_err(|_| "Oberfläche geschlossen")
                    });
                }));
                return receive
                    .recv()
                    .map(|code| json!({"code": code}))
                    .map_err(|_| "Browser-Freigabe konnte nicht gestartet werden");
            }
            Request::Open { .. }
            | Request::Recover { .. }
            | Request::EnableRecovery { .. }
            | Request::Backup { .. } => return Err("Tresor ist bereits geöffnet"),
        }
        save(&self.path, &self.password, &entries)?;
        Ok(list(&entries))
    }
}

fn check_recovery(recovery: &str) -> Result<(), &'static str> {
    if recovery.len() != 64
        || !recovery
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return Err("Der Wiederherstellungsschlüssel muss aus 64 Hex-Zeichen bestehen");
    }
    Ok(())
}

fn list(entries: &[Login]) -> Value {
    json!({"entries": entries.iter().map(|entry| json!({"origin": entry.origin, "username": entry.username})).collect::<Vec<_>>()})
}

pub fn run() -> Result<(), &'static str> {
    let mut session = None::<Session>;
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    loop {
        let mut line = Zeroizing::new(Vec::new());
        let count = (&mut input)
            .take(MAX_REQUEST + 1)
            .read_until(b'\n', &mut line)
            .map_err(|_| "Lesefehler")?;
        if count == 0 {
            return Ok(());
        }
        if count as u64 > MAX_REQUEST {
            return Err("Desktop-Anfrage überschreitet das Größenlimit");
        }
        let result = match serde_json::from_slice(&line) {
            Ok(request) => match &mut session {
                Some(session) => session.handle(request),
                None => match request {
                    Request::Open {
                        path,
                        password,
                        create,
                        recovery,
                    } => (|| {
                        if create {
                            if password.chars().count() < 15 {
                                return Err("Mindestens 15 Zeichen verwenden");
                            }
                            let _lock = lock_writer(&path)?;
                            if let Some(recovery) = recovery {
                                check_recovery(&recovery)?;
                                container::enable_recovery(
                                    &path,
                                    password.as_bytes(),
                                    recovery.as_bytes(),
                                    true,
                                )?;
                            } else {
                                container::save(&path, password.as_bytes(), b"[]", true)?;
                            }
                        }
                        let opened = Session {
                            path,
                            password,
                            share: None,
                        };
                        let entries = opened.entries()?;
                        session = Some(opened);
                        Ok(list(&entries))
                    })(),
                    Request::Recover {
                        path,
                        recovery,
                        password,
                    } => (|| {
                        check_recovery(&recovery)?;
                        if password.chars().count() < 15 {
                            return Err("Mindestens 15 Zeichen verwenden");
                        }
                        let _lock = lock_writer(&path)?;
                        let entries = container::reset_password(
                            &path,
                            recovery.as_bytes(),
                            password.as_bytes(),
                        )?;
                        let opened = Session {
                            path,
                            password,
                            share: None,
                        };
                        session = Some(opened);
                        Ok(list(&entries))
                    })(),
                    _ => Err("Tresor ist gesperrt"),
                },
            },
            Err(_) => Err("Ungültige Desktop-Anfrage"),
        };
        let mut response = result.unwrap_or_else(|error| json!({"error": error}));
        let encoded = serde_json::to_vec(&response);
        for field in ["password", "code"] {
            if let Some(Value::String(secret)) = response.get_mut(field).map(Value::take) {
                drop(Zeroizing::new(secret));
            }
        }
        let encoded = Zeroizing::new(encoded.map_err(|_| "Kodierfehler")?);
        output
            .write_all(&encoded)
            .and_then(|_| output.write_all(b"\n"))
            .and_then(|_| output.flush())
            .map_err(|_| "Ausgabefehler")?;
    }
}
