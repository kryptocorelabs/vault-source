param(
    [Parameter(Mandatory)][string]$PythonExe,
    [string]$OutputDirectory = 'dist/vault-onefile',
    [string]$WorkDirectory = 'dist/vault-onefile-work'
)

$ErrorActionPreference = 'Stop'
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$desktop = Join-Path $PSScriptRoot 'desktop'
$output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
$work = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WorkDirectory)
$previousConfig = $env:PYINSTALLER_CONFIG_DIR
$previousPath = $env:Path
$previousPythonPath = $env:PYTHONPATH
$null = New-Item -ItemType Directory -Force -Path $output, $work

Push-Location $repo
try {
    & $python -c 'import struct,sys; sys.exit(not (sys.platform=="win32" and sys.version_info[:2]==(3,13) and struct.calcsize("P")==8))'
    if ($LASTEXITCODE -ne 0) { throw 'The build requires Windows and 64-bit Python 3.13.' }
    & cargo build --locked --release -p kryptocore-vault -p vault-firefox-channel
    if ($LASTEXITCODE -ne 0) { throw 'Building the Vault Rust binaries failed.' }

    $target = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { 'target' }
    $release = (Resolve-Path (Join-Path $target 'release')).Path
    $env:PYINSTALLER_CONFIG_DIR = $work
    # Limit native dependency discovery to the selected environment and Windows.
    # Other developer tools can ship incompatible DLLs with Windows DLL names.
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONPATH = $null
    $options = @(
        '-m', 'PyInstaller', '--onefile', '--windowed', '--noupx', '--noconfirm', '--clean',
        '--name', 'KryptoCore-Vault-Portable',
        '--distpath', $output, '--workpath', $work, '--specpath', $work
    )
    foreach ($asset in 'emblem.png', 'vault-emblem.png') {
        $options += @('--add-data', "$(Join-Path $desktop $asset);.")
    }
    foreach ($binary in 'kryptocore-vault.exe', 'vault-firefox-host.exe', 'vault_firefox_channel.dll') {
        $options += @('--add-binary', "$(Join-Path $release $binary);.")
    }
    & $python @options (Join-Path $desktop 'vault.pyw')
    if ($LASTEXITCODE -ne 0) { throw 'Bundling the one-file Vault failed.' }

    $file = Join-Path $output 'KryptoCore-Vault-Portable.exe'
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  KryptoCore-Vault-Portable.exe" | Set-Content (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii
    Get-Item -LiteralPath $file
} finally {
    Pop-Location
    $env:PYINSTALLER_CONFIG_DIR = $previousConfig
    $env:Path = $previousPath
    $env:PYTHONPATH = $previousPythonPath
}
