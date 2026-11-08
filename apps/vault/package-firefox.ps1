param([string]$OutputDirectory = 'dist')

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$extension = Join-Path $PSScriptRoot 'extension'
$manifest = Get-Content -LiteralPath (Join-Path $extension 'manifest.firefox.json') -Raw | ConvertFrom-Json
$output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
$package = Join-Path $output "vault-firefox-amo-$($manifest.version)"

Push-Location $repo
try {
    $previousFlags = $env:CARGO_TARGET_WASM32_UNKNOWN_UNKNOWN_RUSTFLAGS
    $env:CARGO_TARGET_WASM32_UNKNOWN_UNKNOWN_RUSTFLAGS = '--cfg getrandom_backend="custom"'
    cargo build --locked --release -p vault-firefox-channel --target wasm32-unknown-unknown
    if ($LASTEXITCODE -ne 0) { throw 'Firefox WebAssembly build failed.' }
    $graphJson = cargo metadata --locked --format-version 1 --filter-platform wasm32-unknown-unknown
    if ($LASTEXITCODE -ne 0) { throw 'Could not enumerate Firefox dependencies.' }
    $graph = $graphJson | ConvertFrom-Json
} finally {
    $env:CARGO_TARGET_WASM32_UNKNOWN_UNKNOWN_RUSTFLAGS = $previousFlags
    Pop-Location
}

$null = New-Item -ItemType Directory -Path $package -Force
$files = @('popup.html', 'popup.css', 'popup.js', 'login-form.js', 'firefox-client.js',
    'firefox-background.js', 'firefox-page.js', 'vault-icon.svg')
foreach ($file in $files) {
    Copy-Item -LiteralPath (Join-Path $extension $file) -Destination $package
}
Copy-Item -LiteralPath (Join-Path $extension 'manifest.firefox.json') -Destination (Join-Path $package 'manifest.json')
$wasm = Join-Path $graph.target_directory 'wasm32-unknown-unknown/release/vault_firefox_channel.wasm'
Copy-Item -LiteralPath $wasm -Destination $package
$notices = Join-Path $package 'third-party'
$null = New-Item -ItemType Directory -Path $notices -Force
$dependencyRows = [Collections.Generic.List[string]]::new()
$packages = @{}
$nodes = @{}
foreach ($crate in $graph.packages) { $packages[$crate.id] = $crate }
foreach ($node in $graph.resolve.nodes) { $nodes[$node.id] = $node }
$rootCrate = @($graph.packages | Where-Object name -eq 'vault-firefox-channel')
$pending = [Collections.Generic.Stack[string]]::new()
$seen = [Collections.Generic.HashSet[string]]::new()
$pending.Push($rootCrate[0].id)
while ($pending.Count) {
    $id = $pending.Pop()
    if (!$seen.Add($id)) { continue }
    foreach ($dependency in $nodes[$id].deps) {
        if (@($dependency.dep_kinds | Where-Object { $null -eq $_.kind }).Count) {
            $pending.Push($dependency.pkg)
        }
    }
    $crate = $packages[$id]
    if (!$crate.source) { continue }
    $label = "$($crate.name)-$($crate.version)"
    $dependencyRows.Add("| $($crate.name) | $($crate.version) | $($crate.license) |")
    $folder = Join-Path $notices $label
    $null = New-Item -ItemType Directory -Path $folder -Force
    $texts = @(Get-ChildItem -LiteralPath (Split-Path -Parent $crate.manifest_path) -File |
        Where-Object Name -Match '^(LICENSE|COPYING|COPYRIGHT|NOTICE)([.-].*)?$')
    if (!$texts.Count) { throw "License text missing for $label." }
    foreach ($file in $texts) { Copy-Item -LiteralPath $file.FullName -Destination $folder }
}
$notice = Join-Path $notices 'THIRD_PARTY_NOTICES.md'
@('# Firefox channel dependencies', '', 'The compiled channel includes these Rust dependencies.',
    'License texts are included in the corresponding directories.', '', '| Crate | Version | License |',
    '| --- | --- | --- |') + @($dependencyRows | Sort-Object) | Set-Content -LiteralPath $notice -Encoding utf8
$zipFiles = foreach ($file in $files + @('manifest.json', 'vault_firefox_channel.wasm')) {
    Join-Path $package $file
}
$archive = "$package.zip"
Compress-Archive -LiteralPath $zipFiles -DestinationPath $archive -Force
Compress-Archive -LiteralPath $notices -DestinationPath $archive -Update
$wasmHash = (Get-FileHash -LiteralPath $wasm -Algorithm SHA256).Hash.ToLowerInvariant()
$zipHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
@("$zipHash  $(Split-Path -Leaf $archive)", "$wasmHash  $(Split-Path -Leaf $package)/vault_firefox_channel.wasm") |
    Set-Content -LiteralPath "$package-SHA256SUMS.txt" -Encoding ascii
Write-Output "$package.zip"
