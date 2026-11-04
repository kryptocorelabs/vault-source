#![forbid(unsafe_code)]
#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(windows)]
fn main() -> std::io::Result<()> {
    use std::{env, fs::OpenOptions, io};

    #[derive(serde::Deserialize)]
    struct Request<'a> {
        v: u8,
        m: &'a str,
        enroll: Option<bool>,
    }

    if env::args_os().nth(2).as_deref() != Some(std::ffi::OsStr::new("vault@kryptocorelabs")) {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "Unexpected extension",
        ));
    }
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    let mut pipe = match OpenOptions::new()
        .read(true)
        .write(true)
        .open(r"\\.\pipe\kryptocorelabs-vault-firefox-v5")
    {
        Ok(pipe) => pipe,
        Err(_) => return write_frame(&mut output, br#"{"v":5,"code":"unavailable"}"#),
    };

    for handshake in [true, false] {
        let frame = read_frame(&mut input, 12 * 1024)?;
        let Request { v, m, enroll } =
            serde_json::from_slice(&frame).map_err(|_| io::ErrorKind::InvalidData)?;
        if v != 5 || m.is_empty() || enroll.is_some() != handshake {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        write_frame(&mut pipe, &frame)?;
        let reply = read_frame(&mut pipe, 32 * 1024)?;
        write_frame(&mut output, &reply)?;
        if handshake
            && serde_json::from_slice::<serde_json::Value>(&reply)
                .map_err(|_| io::ErrorKind::InvalidData)?
                .get("code")
                .is_some()
        {
            break;
        }
    }
    Ok(())
}

#[cfg(windows)]
fn write_frame(output: &mut impl std::io::Write, frame: &[u8]) -> std::io::Result<()> {
    output.write_all(&(frame.len() as u32).to_le_bytes())?;
    output.write_all(frame)?;
    output.flush()
}

#[cfg(windows)]
fn read_frame(
    input: &mut impl std::io::Read,
    limit: usize,
) -> std::io::Result<zeroize::Zeroizing<Vec<u8>>> {
    let mut header = [0; 4];
    input.read_exact(&mut header)?;
    let length = u32::from_le_bytes(header) as usize;
    if length == 0 || length > limit {
        return Err(std::io::ErrorKind::InvalidData.into());
    }
    let mut bytes = zeroize::Zeroizing::new(vec![0; length]);
    input.read_exact(&mut bytes)?;
    Ok(bytes)
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Vault Firefox native messaging is available on Windows.");
}
