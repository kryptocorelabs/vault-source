//! Explicit, bounded plaintext migration. No keys, slots or local settings transfer.
use crate::Login;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs::{self, File},
    io::{Read, Write},
    path::Path,
};
use zeroize::Zeroizing;

const MAX_EXPORT: usize = 16 * 1024 * 1024;
const FORMAT: &str = "kryptocore-vault-export";

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ImportFile {
    format: String,
    schema_version: u32,
    entries: Vec<Login>,
}

#[derive(Serialize)]
struct ExportFile<'a> {
    format: &'static str,
    schema_version: u32,
    entries: &'a [Login],
}

pub struct Prepared {
    pub entries: Vec<Login>,
    pub data: Zeroizing<Vec<u8>>,
    pub digest: String,
}

fn validate(entries: &mut [Login]) -> Result<(), &'static str> {
    let mut sites = HashSet::new();
    for entry in entries {
        entry.origin =
            crate::origin(&entry.origin).map_err(|_| "Export enthält eine ungültige Website.")?;
        if entry.password.is_empty() {
            return Err("Export enthält einen Login ohne Passwort.");
        }
        if !sites.insert(entry.origin.clone()) {
            return Err("Export enthält doppelte Websites. Es wurde nichts zusammengeführt.");
        }
    }
    Ok(())
}

pub fn prepare(source: &Path) -> Result<Prepared, &'static str> {
    // Reject obvious special files before open (in particular blocking FIFOs).
    let metadata =
        fs::symlink_metadata(source).map_err(|_| "Export konnte nicht geöffnet werden.")?;
    if !metadata.is_file() || is_link(&metadata) {
        return Err("Wähle die reguläre JSON-Datei ohne Verknüpfung.");
    }
    let mut file = File::open(source).map_err(|_| "Export konnte nicht geöffnet werden.")?;
    if !file
        .metadata()
        .map_err(|_| "Export konnte nicht gelesen werden.")?
        .is_file()
    {
        return Err("Wähle eine reguläre JSON-Datei.");
    }
    let mut raw = Zeroizing::new(Vec::new());
    (&mut file)
        .take(MAX_EXPORT as u64 + 1)
        .read_to_end(&mut raw)
        .map_err(|_| "Export konnte nicht gelesen werden.")?;
    if raw.len() > MAX_EXPORT {
        return Err("JSON-Export überschreitet das Limit von 16 MiB.");
    }
    let digest = format!("{:x}", Sha256::digest(&*raw));
    let mut entries = match raw.iter().find(|b| !b.is_ascii_whitespace()) {
        Some(b'[') => serde_json::from_slice::<Vec<Login>>(&raw)
            .map_err(|_| "Ungültiger Rescue-JSON-Export.")?,
        Some(b'{') => {
            let export: ImportFile =
                serde_json::from_slice(&raw).map_err(|_| "Ungültiger Vault-JSON-Export.")?;
            if export.format != FORMAT || export.schema_version != 1 {
                return Err("Unbekanntes JSON-Exportformat oder nicht unterstützte Version.");
            }
            export.entries
        }
        _ => return Err("Eine JSON-Exportdatei wird erwartet."),
    };
    validate(&mut entries)?;
    let data = Zeroizing::new(
        serde_json::to_vec(&entries).map_err(|_| "Einträge konnten nicht kodiert werden.")?,
    );
    // KCV2 total size remains bounded to 4 MiB, including its 221-byte overhead.
    if data.len() > 4 * 1024 * 1024 - 221 {
        return Err("Die importierten Einträge überschreiten das Tresorlimit von 4 MiB.");
    }
    Ok(Prepared {
        entries,
        data,
        digest,
    })
}

fn is_link(metadata: &fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return true;
        }
    }
    false
}

pub fn export(destination: &Path, entries: &[Login], confirmed: bool) -> Result<(), &'static str> {
    if !confirmed {
        return Err("Bestätige zuerst den unverschlüsselten Export.");
    }
    let parent = destination
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    for ancestor in parent.ancestors().filter(|p| !p.as_os_str().is_empty()) {
        let metadata =
            fs::symlink_metadata(ancestor).map_err(|_| "Exportordner nicht verfügbar.")?;
        if !metadata.is_dir() || is_link(&metadata) {
            return Err("Wähle einen geschützten Exportordner ohne Verknüpfungen.");
        }
    }
    if destination.file_name().is_none() || fs::symlink_metadata(destination).is_ok() {
        return Err("Datei existiert bereits. Wähle einen neuen Namen.");
    }
    let data = Zeroizing::new(
        serde_json::to_vec_pretty(&ExportFile {
            format: FORMAT,
            schema_version: 1,
            entries,
        })
        .map_err(|_| "Export konnte nicht kodiert werden.")?,
    );
    if data.len() > MAX_EXPORT {
        return Err("JSON-Export überschreitet das Limit von 16 MiB.");
    }
    let mut temporary = tempfile::NamedTempFile::new_in(parent)
        .map_err(|_| "Export konnte nicht angelegt werden.")?;
    temporary
        .write_all(&data)
        .and_then(|_| temporary.as_file().sync_all())
        .map_err(|_| "Export konnte nicht gespeichert werden.")?;
    temporary
        .persist_noclobber(destination)
        .map_err(|_| "Export konnte nicht übernommen werden. Wähle einen neuen Namen.")?;
    Ok(())
}
