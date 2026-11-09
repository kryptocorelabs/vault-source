use super::*;

const PASSWORD: &[u8] = b"synthetic vault password";
const RECOVERY: &[u8] = b"synthetic recovery code";
const NEW_PASSWORD: &[u8] = b"new synthetic vault password";
const DATA: &[u8] =
    br#"[{"origin":"https://example.invalid","username":"alice","password":"synthetic"}]"#;

fn decrypt_direct_payload(file: &[u8], key: &Key) -> Result<Zeroizing<Vec<u8>>, kryptocore::Error> {
    let nonce = file[EPOCH_AAD_LEN..EPOCH_AAD_LEN + 24].try_into().unwrap();
    decrypt(
        key,
        nonce,
        &file[EPOCH_AAD_LEN + 24..],
        &file[..EPOCH_AAD_LEN],
    )
}

#[test]
fn version_four_uses_direct_payload_key_and_preserves_recovery_on_reset() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("direct.kcv");
    let first = create_with_recovery_v4(&path, PASSWORD, RECOVERY, DATA).unwrap();
    assert_eq!(first.epoch, 1);
    let original = read(&path).unwrap();
    assert!(original.starts_with(DIRECT_KEY_HEADER));
    let (seed, _) = open_recoverable(&original, PASSWORD, 0).unwrap();
    let key = Key::from_bytes(seed.as_slice().try_into().unwrap());
    assert_eq!(&decrypt_direct_payload(&original, &key).unwrap()[..], DATA);
    let mut changed = original.clone();
    changed[3] = b'3';
    assert!(open_bytes(&changed, PASSWORD).is_err());
    let second = save_with_revision(&path, PASSWORD, DATA, false, Some(first))
        .unwrap()
        .unwrap();
    assert_eq!(second.epoch, 2);
    assert_eq!(
        check_revision(revision(&original), Some(second)),
        Err(REVISION_REJECTED)
    );
    let (_, third) =
        reset_password_with_revision(&path, RECOVERY, NEW_PASSWORD, Some(second)).unwrap();
    assert_eq!(third.unwrap().epoch, 3);
    let changed = read(&path).unwrap();
    assert!(changed.starts_with(DIRECT_KEY_HEADER));
    let (new_seed, _) = open_recoverable(&changed, NEW_PASSWORD, 0).unwrap();
    assert!(seed[..] != new_seed[..]);
    assert!(decrypt_direct_payload(&changed, &key).is_err());
    assert!(open(&path, PASSWORD).is_err());
    assert_eq!(&open_with_recovery(&path, RECOVERY).unwrap()[..], DATA);
    let fourth = save_with_revision(&path, NEW_PASSWORD, DATA, false, third)
        .unwrap()
        .unwrap();
    assert_eq!(fourth.epoch, 4);
    assert!(decrypt_direct_payload(&read(&path).unwrap(), &key).is_err());
    assert_eq!(&open_bytes(&original, PASSWORD).unwrap()[..], DATA);
}

#[test]
fn version_four_rejects_a_stale_snapshot_before_rotating_or_copying() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("direct.kcv");
    let first = create_with_recovery_v4(&path, PASSWORD, RECOVERY, DATA).unwrap();
    let stale = read(&path).unwrap();
    let floor = save_with_revision(&path, PASSWORD, DATA, false, Some(first)).unwrap();
    std::fs::write(&path, &stale).unwrap();

    assert!(matches!(
        reset_password_with_revision(&path, RECOVERY, NEW_PASSWORD, floor),
        Err(REVISION_REJECTED)
    ));
    assert!(matches!(
        enable_recovery_with_revision(&path, PASSWORD, b"replacement sheet", false, floor),
        Err(REVISION_REJECTED)
    ));
    assert!(matches!(
        change_password_with_revision(&path, PASSWORD, NEW_PASSWORD, false, None, floor),
        Err(REVISION_REJECTED)
    ));
    let backup = folder.path().join("backup.kcv");
    assert!(matches!(
        backup_with_revision(&path, &backup, PASSWORD, floor),
        Err(REVISION_REJECTED)
    ));
    assert!(!backup.exists());
    assert_eq!(read(&path).unwrap(), stale);
    assert_eq!(&open_with_recovery(&path, RECOVERY).unwrap()[..], DATA);
}

#[test]
fn upgrade_keeps_both_slots_and_the_original_for_both_legacy_versions() {
    let folder = tempfile::tempdir().unwrap();
    let legacy = folder.path().join("legacy.kcv");
    let epoch = folder.path().join("epoch.kcv");
    create_with_recovery(&legacy, PASSWORD, RECOVERY, DATA).unwrap();
    let floor = enable_epoch_copy(&legacy, &epoch, PASSWORD).unwrap();
    for (index, (source, minimum)) in [(&legacy, None), (&epoch, Some(floor))]
        .into_iter()
        .enumerate()
    {
        let target = folder.path().join(format!("direct-{index}.kcv"));
        let old = read(source).unwrap();
        let (entries, revision) = upgrade_payload_copy(source, &target, PASSWORD, minimum).unwrap();
        assert_eq!(revision.epoch, 1);
        assert_eq!(entries.len(), 1);
        let (slots, aad) = layout(&old).unwrap();
        let updated = read(&target).unwrap();
        assert_eq!(&old[slots..aad], &updated[EPOCH_PREFIX..EPOCH_AAD_LEN]);
        assert_eq!(read(source).unwrap(), old);
        assert_eq!(&open_with_recovery(&target, RECOVERY).unwrap()[..], DATA);
        assert!(upgrade_payload_copy(source, &target, PASSWORD, minimum).is_err());
        assert_eq!(read(&target).unwrap(), updated);
    }
}
