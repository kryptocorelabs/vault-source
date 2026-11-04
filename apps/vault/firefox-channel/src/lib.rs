//! Bounded buffer interface shared by the Vault DLL and Firefox WebAssembly.

use snow::{Builder, HandshakeState, TransportState};
use zeroize::Zeroize;

const BUFFER_SIZE: usize = 16 * 1024;

enum State {
    Handshake(HandshakeState),
    Transport(TransportState),
}

pub struct Channel {
    state: Option<State>,
    buffer: [u8; BUFFER_SIZE],
}

#[no_mangle]
pub extern "C" fn vault_channel_new() -> *mut Channel {
    Box::into_raw(Box::new(Channel {
        state: None,
        buffer: [0; BUFFER_SIZE],
    }))
}

/// # Safety
/// The handle must be live and exclusively owned by the caller.
#[no_mangle]
pub unsafe extern "C" fn vault_channel_buffer(channel: *mut Channel) -> *mut u8 {
    (*channel).buffer.as_mut_ptr()
}

/// # Safety
/// The handle must come from `vault_channel_new` and may be freed only once.
#[no_mangle]
pub unsafe extern "C" fn vault_channel_free(channel: *mut Channel) {
    let mut channel = Box::from_raw(channel);
    channel.buffer.zeroize();
}

/// # Safety
/// The handle must be live and exclusively owned. The caller must fill the
/// first 32 bytes of its buffer with the selected pre-shared key.
#[no_mangle]
pub unsafe extern "C" fn vault_channel_start(
    channel: *mut Channel,
    initiator: u32,
    pairing: u32,
) -> i32 {
    let channel = &mut *channel;
    let mut key = [0; 32];
    key.copy_from_slice(&channel.buffer[..32]);
    channel.buffer.zeroize();
    let result = channel.start(initiator != 0, pairing != 0, &key);
    key.zeroize();
    result.map_or(-1, |size| size as i32)
}

/// # Safety
/// The handle must be live and exclusively owned. The caller must write the
/// input to its buffer and copy the output before the next call.
#[no_mangle]
pub unsafe extern "C" fn vault_channel_step(
    channel: *mut Channel,
    operation: u32,
    len: usize,
) -> i32 {
    let channel = &mut *channel;
    let mut input = [0; BUFFER_SIZE];
    let result = if len <= BUFFER_SIZE {
        input[..len].copy_from_slice(&channel.buffer[..len]);
        channel.buffer.zeroize();
        channel.step(operation, &input[..len])
    } else {
        Err(snow::Error::Input)
    };
    input.zeroize();
    if result.is_err() {
        channel.state = None;
        channel.buffer.zeroize();
    }
    result.map_or(-1, |size| size as i32)
}

impl Channel {
    fn start(
        &mut self,
        initiator: bool,
        pairing: bool,
        key: &[u8; 32],
    ) -> Result<usize, snow::Error> {
        let prologue: &[u8] = if pairing {
            b"KryptoCore Vault Firefox v5 pairing"
        } else {
            b"KryptoCore Vault Firefox v5 session"
        };
        let builder = Builder::new("Noise_NNpsk0_25519_ChaChaPoly_SHA256".parse()?)
            .prologue(prologue)?
            .psk(0, key)?;
        let mut handshake = if initiator {
            builder.build_initiator()?
        } else {
            builder.build_responder()?
        };
        let size = if initiator {
            handshake.write_message(&[], &mut self.buffer)?
        } else {
            0
        };
        self.state = Some(State::Handshake(handshake));
        Ok(size)
    }

    fn step(&mut self, operation: u32, input: &[u8]) -> Result<usize, snow::Error> {
        let (state, size) = match (self.state.take(), operation) {
            (Some(State::Handshake(mut handshake)), 0) => {
                if handshake.read_message(input, &mut self.buffer)? != 0 {
                    return Err(snow::Error::Input);
                }
                let size = if handshake.is_initiator() {
                    0
                } else {
                    handshake.write_message(&[], &mut self.buffer)?
                };
                (State::Transport(handshake.into_transport_mode()?), size)
            }
            (Some(State::Transport(mut transport)), 1) => {
                let size = transport.write_message(input, &mut self.buffer)?;
                (State::Transport(transport), size)
            }
            (Some(State::Transport(mut transport)), 2) => {
                let size = transport.read_message(input, &mut self.buffer)?;
                (State::Transport(transport), size)
            }
            _ => return Err(snow::Error::Input),
        };
        self.state = Some(state);
        Ok(size)
    }
}

#[cfg(target_arch = "wasm32")]
#[no_mangle]
unsafe extern "Rust" fn __getrandom_v03_custom(
    destination: *mut u8,
    len: usize,
) -> Result<(), getrandom::Error> {
    #[link(wasm_import_module = "env")]
    extern "C" {
        fn vault_random(destination: *mut u8, len: usize);
    }
    vault_random(destination, len);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn new_channel() -> Channel {
        Channel {
            state: None,
            buffer: [0; BUFFER_SIZE],
        }
    }

    fn handshake() -> (Channel, Channel) {
        let mut browser = new_channel();
        let mut vault = new_channel();
        let key = [37; 32];
        let opening = browser.start(true, false, &key).unwrap();
        vault.start(false, false, &key).unwrap();
        let reply = vault.step(0, &browser.buffer[..opening]).unwrap();
        browser.step(0, &vault.buffer[..reply]).unwrap();
        (browser, vault)
    }

    #[test]
    fn peers_reject_wrong_key_and_pairing_context() {
        let mut browser = new_channel();
        let mut vault = new_channel();
        let length = browser.start(true, false, &[37; 32]).unwrap();
        vault.start(false, false, &[38; 32]).unwrap();
        assert!(vault.step(0, &browser.buffer[..length]).is_err());
        vault.start(false, true, &[37; 32]).unwrap();
        assert!(vault.step(0, &browser.buffer[..length]).is_err());
    }

    #[test]
    fn transport_authenticates_both_directions_and_rejects_replay() {
        let (mut browser, mut vault) = handshake();
        let request = b"synthetic login request";
        let length = browser.step(1, request).unwrap();
        let ciphertext = &browser.buffer[..length];
        let opened = vault.step(2, ciphertext).unwrap();
        assert_eq!(&vault.buffer[..opened], request);

        let response = b"synthetic password";
        let length = vault.step(1, response).unwrap();
        let opened = browser.step(2, &vault.buffer[..length]).unwrap();
        assert_eq!(&browser.buffer[..opened], response);

        let (mut browser, _) = handshake();
        let length = browser.step(1, request).unwrap();
        let captured = &browser.buffer[..length];
        let (_, mut fresh_vault) = handshake();
        assert!(fresh_vault.step(2, captured).is_err());

        let (mut browser, mut vault) = handshake();
        let length = browser.step(1, request).unwrap();
        browser.buffer[length - 1] ^= 1;
        assert!(vault.step(2, &browser.buffer[..length]).is_err());
    }
}
