# Mika's per-user Windows installer. PowerShell 5.1+; no admin or build tools needed.
# Optional offline install: $env:MIKA_ARCHIVE_PATH = 'C:\Downloads\mika-windows-x86_64.zip'
& {
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-MikaFile([string]$Url, [string]$Destination, [long]$Limit) {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(10)
    $client.MaxResponseContentBufferSize = $Limit
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('Mika-Installer/0.1.0')
    try {
        $uri = [Uri]$Url
        for ($hop = 0; $hop -le 5; $hop++) {
            if ($uri.Scheme -ne 'https') { throw 'Only HTTPS release downloads are permitted.' }
            $response = $client.GetAsync($uri).GetAwaiter().GetResult()
            try {
                $code = [int]$response.StatusCode
                if ($code -ge 300 -and $code -lt 400) {
                    if ($null -eq $response.Headers.Location) { throw 'Redirect without a destination.' }
                    $uri = New-Object Uri($uri, $response.Headers.Location)
                    continue
                }
                [void]$response.EnsureSuccessStatusCode()
                $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
                if ($bytes.LongLength -gt $Limit) { throw 'Release download exceeds its size limit.' }
                [System.IO.File]::WriteAllBytes($Destination, $bytes)
                return
            } finally { $response.Dispose() }
        }
        throw 'Too many release redirects.'
    } finally { $client.Dispose(); $handler.Dispose() }
}

$work = $null
$backup = $null
$installed = $false
$success = $false
$root = $null
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Use install.sh on Linux or WSL.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Mika requires 64-bit Windows.' }
    $architecture = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) { $architecture = $env:PROCESSOR_ARCHITEW6432 }
    if ($architecture -ne 'AMD64') { throw 'Prebuilt releases currently support Windows x64 only.' }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $version = $env:MIKA_VERSION
    if (-not $version) { $version = 'latest' }
    if ($version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { throw 'Invalid MIKA_VERSION.' }
    $base = 'https://github.com/nochinsky/mika/releases'
    if ($version -eq 'latest') { $base += '/latest/download' } else { $base += "/download/$version" }
    $asset = 'mika-windows-x86_64.zip'
    $parent = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Mika'
    $root = Join-Path $parent 'app'
    if ((Test-Path -LiteralPath $root) -and -not (Test-Path -LiteralPath (Join-Path $root 'VERSION'))) {
        throw "Refusing to replace an unrelated directory: $root"
    }
    [void](New-Item -ItemType Directory -Path $parent -Force)
    $work = Join-Path $parent ('.install-' + [Guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $work)
    $archive = Join-Path $work $asset
    $checksum = $archive + '.sha256'
    Write-Host "Installing Mika ($version) for Windows..."
    if ($env:MIKA_ARCHIVE_PATH) {
        Copy-Item -LiteralPath $env:MIKA_ARCHIVE_PATH -Destination $archive
        Copy-Item -LiteralPath ($env:MIKA_ARCHIVE_PATH + '.sha256') -Destination $checksum
    } else {
        Get-MikaFile "$base/$asset" $archive 268435456
        Get-MikaFile "$base/$asset.sha256" $checksum 4096
    }
    $expected = ((Get-Content -LiteralPath $checksum -Raw).Trim() -split '\s+')[0]
    if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid release checksum file.' }
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw 'Release checksum mismatch. Nothing was installed.' }
    # Reject paths escaping the package root before extraction.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if (-not $name.StartsWith('mika/') -or $name -match '(^|/)\.\.(/|$)' -or $name.Contains(':')) {
                throw 'Unsafe release archive path.'
            }
        }
    } finally { $zip.Dispose() }
    Expand-Archive -LiteralPath $archive -DestinationPath $work
    $candidate = Join-Path $work 'mika'
    $binary = Join-Path $candidate 'bin\mika.exe'
    if (-not (Test-Path -LiteralPath $binary) -or -not (Test-Path -LiteralPath (Join-Path $candidate 'VERSION'))) {
        throw 'Incomplete release package.'
    }
    & $binary --version
    if ($LASTEXITCODE -ne 0) { throw 'The release binary could not start on this system.' }
    if (Test-Path -LiteralPath $root) {
        $backup = Join-Path $work 'previous-app'
        Move-Item -LiteralPath $root -Destination $backup
    }
    Move-Item -LiteralPath $candidate -Destination $root
    $installed = $true
    $bin = Join-Path $root 'bin'
    & (Join-Path $bin 'mika.exe') --version
    if ($LASTEXITCODE -ne 0) { throw 'Installed binary failed its startup check.' }
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    if (-not ($entries | Where-Object { $_.TrimEnd('\') -ieq $bin.TrimEnd('\') })) {
        $newPath = ($entries + $bin) -join ';'
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    }
    if (-not (($env:Path -split ';') | Where-Object { $_.TrimEnd('\') -ieq $bin.TrimEnd('\') })) {
        $env:Path = $bin + ';' + $env:Path
    }
    $success = $true
    Write-Host "`nMika installed. Run: mika"
    Write-Host 'Restart your terminal for the PATH change to apply to future sessions.'
    Write-Host 'On first run, Mika asks before downloading its 279 MB model. No audio was recorded.'
} catch {
    Write-Error "Mika installation failed: $($_.Exception.Message)" -ErrorAction Continue
    throw
} finally {
    if (-not $success) {
        if ($installed -and (Test-Path -LiteralPath $root)) { Remove-Item -LiteralPath $root -Recurse -Force }
        if ($backup -and (Test-Path -LiteralPath $backup)) { Move-Item -LiteralPath $backup -Destination $root }
    }
    if ($work -and (Test-Path -LiteralPath $work)) {
        try { Remove-Item -LiteralPath $work -Recurse -Force }
        catch { Write-Warning "Could not remove installer scratch directory: $work. Close running Mika processes before updating." }
    }
}
}
