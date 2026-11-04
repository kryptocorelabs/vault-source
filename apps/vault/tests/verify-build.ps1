param([Parameter(Mandatory)][string]$OutputDirectory)

$ErrorActionPreference = 'Stop'
$vault = Split-Path -Parent $PSScriptRoot
$repo = (Resolve-Path (Join-Path $vault '../..')).Path
$output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
if (Test-Path -LiteralPath $output) { throw 'Choose a fresh output directory.' }
$null = New-Item -ItemType Directory -Path $output
$previousTarget = $env:CARGO_TARGET_DIR

function Read-PackageHashes([string]$archive) {
    $hashes = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            if (!$entry.Name) { continue }
            $stream = $entry.Open()
            try {
                $hashes.Add($entry.FullName, (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash)
            } finally {
                $stream.Dispose()
            }
        }
    } finally {
        $zip.Dispose()
    }
    return ,$hashes
}

Push-Location $repo
try {
    $env:CARGO_TARGET_DIR = Join-Path $output 'desktop-target'
    cargo build --locked --release -p kryptocore-vault -p vault-firefox-channel
    if ($LASTEXITCODE -ne 0) { throw 'Windows native build failed.' }
    $desktop = Join-Path $env:CARGO_TARGET_DIR 'release'
    $manifestPath = Join-Path $vault 'extension/manifest.firefox.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $archiveName = "vault-firefox-amo-$($manifest.version).zip"
    $packages = foreach ($name in 'first', 'second') {
        $env:CARGO_TARGET_DIR = Join-Path $output "wasm-target-$name"
        $packageDirectory = Join-Path $output $name
        & (Join-Path $vault 'package-firefox.ps1') -OutputDirectory $packageDirectory | Out-Host
        Join-Path $packageDirectory $archiveName
    }
    $first = Read-PackageHashes $packages[0]
    $second = Read-PackageHashes $packages[1]
    if ($first.Count -ne $second.Count) { throw 'Firefox package member counts differ.' }
    foreach ($name in $first.Keys) {
        if (!$second.ContainsKey($name) -or $first[$name] -ne $second[$name]) {
            throw "Firefox builds differ for $name."
        }
    }
    if ($first['manifest.json'] -ne (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -or
        !$first.ContainsKey('vault_firefox_channel.wasm')) {
        throw 'Firefox package is missing the expected manifest or WASM.'
    }

    $rows = foreach ($file in 'kryptocore-vault.exe', 'vault-firefox-host.exe', 'vault_firefox_channel.dll') {
        $hash = (Get-FileHash -LiteralPath (Join-Path $desktop $file) -Algorithm SHA256).Hash
        "$($hash.ToLowerInvariant())  $file"
    }
    $rows += "$($first['vault_firefox_channel.wasm'].ToLowerInvariant())  vault_firefox_channel.wasm"
    $rows += "$((Get-FileHash -LiteralPath $packages[0] -Algorithm SHA256).Hash.ToLowerInvariant())  $archiveName"
    $rows | Set-Content -LiteralPath (Join-Path $output 'SHA256SUMS.txt') -Encoding ascii
    $rows
} finally {
    Pop-Location
    $env:CARGO_TARGET_DIR = $previousTarget
}
