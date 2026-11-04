use std::{
    fmt::Write,
    net::TcpListener,
    time::{Duration, Instant},
};

use subtle::ConstantTimeEq;
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};
use zeroize::Zeroizing;

use crate::Login;

pub fn share(entry: Login) -> Result<(), &'static str> {
    share_with(&entry, |port, token| {
        println!(
            "Einmalcode für {} (90 Sekunden):\n{port}:{token}",
            entry.origin
        );
        Ok(())
    })?;
    println!("Freigabe beendet.");
    Ok(())
}

pub fn share_with(
    entry: &Login,
    announce: impl FnOnce(u16, &str) -> Result<(), &'static str>,
) -> Result<(), &'static str> {
    validate_site(&entry.origin)?;
    let listener = TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, 0))
        .map_err(|_| "Lokale Verbindung konnte nicht geöffnet werden")?;
    let port = listener
        .local_addr()
        .map_err(|_| "Lokaler Port fehlt")?
        .port();
    let server =
        Server::from_listener(listener, None).map_err(|_| "Lokale Verbindung fehlgeschlagen")?;
    let mut random = Zeroizing::new([0u8; 32]);
    getrandom::fill(&mut random[..]).map_err(|_| "Zufallsquelle nicht verfügbar")?;
    let mut token = Zeroizing::new(String::with_capacity(64));
    for byte in random.iter() {
        write!(&mut *token, "{byte:02x}").map_err(|_| "Code konnte nicht erstellt werden")?;
    }
    drop(random);
    let host = format!("127.0.0.1:{port}");
    announce(port, &token)?;
    serve_once(&server, entry, &host, &token, Duration::from_secs(90))
}

pub fn validate_site(site: &str) -> Result<(), &'static str> {
    if site.starts_with("https://") {
        Ok(())
    } else {
        Err("Für den Browser-Abruf bitte die vollständige HTTPS-Adresse der Website hinterlegen")
    }
}

fn serve_once(
    server: &Server,
    entry: &Login,
    host: &str,
    token: &str,
    lifetime: Duration,
) -> Result<(), &'static str> {
    let deadline = Instant::now() + lifetime;
    while let Some(wait) = deadline.checked_duration_since(Instant::now()) {
        let Some(request) = server
            .recv_timeout(wait)
            .map_err(|_| "Lokale Verbindung unterbrochen")?
        else {
            break;
        };
        if Instant::now() >= deadline || !authorized(&request, host, token, &entry.origin) {
            let _ = request.respond(Response::empty(403));
            continue;
        }
        let body = Zeroizing::new(
            serde_json::to_vec(entry).map_err(|_| "Eintrag konnte nicht kodiert werden")?,
        );
        let response = Response::new(
            StatusCode(200),
            Vec::new(),
            &body[..],
            Some(body.len()),
            None,
        )
        .with_header(Header::from_bytes("Content-Type", "application/json").expect("static header"))
        .with_header(Header::from_bytes("Cache-Control", "no-store").expect("static header"));
        request
            .respond(response)
            .map_err(|_| "Übertragung fehlgeschlagen")?;
        return Ok(());
    }
    Err("Freigabe abgelaufen")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::TcpStream,
    };

    #[test]
    fn browser_bridge_rejects_wrong_origin_and_code_before_one_success() {
        for origin in [
            Some("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            Some("moz-extension://01234567-89ab-cdef-0123-456789abcdef"),
            None,
        ] {
            exercise_bridge(origin);
        }
    }

    fn exercise_bridge(accepted_origin: Option<&str>) {
        let listener = TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, 0)).unwrap();
        let address = listener.local_addr().unwrap();
        let server = Server::from_listener(listener, None).unwrap();
        let token = "a".repeat(64);
        let extension = format!("chrome-extension://{}", "a".repeat(32));
        let site = "https://example.com";
        let entry = Login {
            origin: site.into(),
            username: "demo".into(),
            password: "synthetic-secret".into(),
        };
        std::thread::scope(|scope| {
            let worker = scope.spawn(|| {
                serve_once(
                    &server,
                    &entry,
                    &address.to_string(),
                    &token,
                    Duration::from_secs(5),
                )
            });
            for (origin, target, code, expected) in [
                (
                    Some("https://malicious.example"),
                    site,
                    token.as_str(),
                    "403",
                ),
                (Some("null"), site, token.as_str(), "403"),
                (None, site, "wrong-code", "403"),
                (
                    Some(extension.as_str()),
                    "https://example.com.evil.example",
                    token.as_str(),
                    "403",
                ),
                (Some(extension.as_str()), site, "wrong-code", "403"),
                (accepted_origin, site, token.as_str(), "200"),
            ] {
                let mut stream = TcpStream::connect(address).unwrap();
                stream
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .unwrap();
                let origin =
                    origin.map_or_else(String::new, |value| format!("Origin: {value}\r\n"));
                write!(stream, "POST /login HTTP/1.1\r\nHost: {address}\r\n{origin}X-Vault-Site: {target}\r\nX-Vault-Code: {code}\r\nX-Vault-Client: firefox\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").unwrap();
                let mut response = String::new();
                stream.read_to_string(&mut response).unwrap();
                assert_eq!(response.split_whitespace().nth(1), Some(expected));
                assert_eq!(response.contains("synthetic-secret"), expected == "200");
            }
            assert!(worker.join().unwrap().is_ok());
        });
    }
}

fn authorized(request: &Request, host: &str, token: &str, site: &str) -> bool {
    let header = |name: &'static str| {
        let mut values = request.headers().iter().filter(|h| h.field.equiv(name));
        let value = values.next()?.value.as_str();
        values.next().is_none().then_some(value)
    };
    let origin_allowed = match header("Origin") {
        Some(origin) => extension_origin(origin),
        // Firefox can omit Origin on privileged requests. Pages cannot send
        // these custom headers cross-origin without a successful CORS preflight.
        None => {
            header("X-Vault-Client") == Some("firefox")
                && !request.headers().iter().any(|h| h.field.equiv("Origin"))
        }
    };
    request.method() == &Method::Post
        && request.url() == "/login"
        && header("Host") == Some(host)
        && origin_allowed
        && header("X-Vault-Site") == Some(site)
        && header("X-Vault-Code")
            .is_some_and(|code| bool::from(code.as_bytes().ct_eq(token.as_bytes())))
}

fn extension_origin(origin: &str) -> bool {
    if let Some(id) = origin.strip_prefix("chrome-extension://") {
        return id.len() == 32 && id.bytes().all(|c| (b'a'..=b'p').contains(&c));
    }
    origin.strip_prefix("moz-extension://").is_some_and(|id| {
        id.len() == 36
            && id.bytes().enumerate().all(|(index, byte)| {
                if matches!(index, 8 | 13 | 18 | 23) {
                    byte == b'-'
                } else {
                    byte.is_ascii_hexdigit()
                }
            })
    })
}
