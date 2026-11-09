# Windows and Firefox release check

Test the exact Vault executable and Mozilla-signed XPI intended for users.
Use a disposable Windows account where possible and close any running Vault
before the check. The script uses a fresh Firefox profile, a temporary copy
of the public demo vault and a loopback HTTPS form. The Vault native-host
registration is temporary and the script restores the previous value.

Use Python 3.13, OpenSSL on PATH, Firefox and a matching GeckoDriver. Install
the test-only packages into an isolated environment:

```powershell
python -m pip install selenium==4.52.0 pywinauto==0.6.9
python apps/vault/tests/firefox-release-e2e.py --vault PATH_TO_EXE --addon PATH_TO_SIGNED_XPI --fixture PATH_TO_DEMO_KCV --firefox PATH_TO_FIREFOX --geckodriver PATH_TO_GECKODRIVER
```

Use [the public demo vault](https://github.com/kryptocorelabs/kryptocorelabs/blob/main/demo/fixtures/demo-vault.kcv).
The test requires local port 8443 and an interactive Windows desktop. It
installs the XPI with Firefox signature enforcement enabled and uses the real
toolbar to pair and fill. It checks the target fields on origin mismatch,
navigation and tab switch, then checks locking and unlocking with the same
pairing. The mocked CI tests separately force a reply to arrive after a
session change.

## Maintainer result on 2026-11-09

The exact portable evaluation build at source commit `a3de37a` passed with
Firefox 159.0.1 and the signed 0.1.16 XPI on Windows x64.

| Artifact | SHA-256 |
| --- | --- |
| `KryptoCore-Vault-Portable.exe` | `3caa1663f33b5a93b21d1a3146ee5640b4321a531015eddd14c02ba4b1688255` |
| `KryptoCore-Vault-Firefox-0.1.16.xpi` | `c7b14f08a86aeb84028a3d3e870489fe39876f2c08c095384dbce595532a4df9` |

Pairing and explicit fill worked. The form stayed unsubmitted. The other
origin, new document and other tab stayed empty. Locking blocked fill and
unlocking restored fill with the same pairing. Repeat for each new candidate
EXE and XPI. This is a maintainer integration test.
