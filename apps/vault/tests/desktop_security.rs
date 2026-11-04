use std::{
    io::{ErrorKind, Write},
    process::{Command, Stdio},
};

#[test]
fn oversized_desktop_input_ends_the_session_without_echoing_input() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_kryptocore-vault"))
        .arg("desktop-session")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut oversized = vec![b'x'; 16 * 1024 * 1024 + 2];
    let last = oversized.len() - 1;
    oversized[last] = b'\n';
    if let Err(error) = input.write_all(&oversized) {
        assert_eq!(error.kind(), ErrorKind::BrokenPipe);
    }
    drop(input);
    let output = child.wait_with_output().unwrap();
    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
    assert_eq!(
        String::from_utf8(output.stderr).unwrap().trim(),
        "Desktop-Anfrage überschreitet das Größenlimit"
    );
}
