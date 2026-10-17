# Per-user Windows installer. Rerun to update; MIKA_REINSTALL=1 forces a repair.
# PowerShell 5.1+; no administrator access or build tools required.
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
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('Mika-Installer/0.1.1')
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
$installLock = $null
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
    $reinstall = $env:MIKA_REINSTALL
    if (-not $reinstall) { $reinstall = '0' }
    if ($reinstall -ne '0' -and $reinstall -ne '1') { throw 'MIKA_REINSTALL must be 0 or 1.' }
    $base = 'https://github.com/nochinsky/mika/releases'
    if ($version -eq 'latest') { $base += '/latest/download' } else { $base += "/download/$version" }
    $asset = 'mika-windows-x86_64.zip'
    $parent = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Mika'
    $root = Join-Path $parent 'app'
    [void](New-Item -ItemType Directory -Path $parent -Force)
    try {
        $installLock = [IO.File]::Open((Join-Path $parent '.installer.lock'), [IO.FileMode]::OpenOrCreate,
                                     [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch { throw 'Another Mika installer may be running, or the install directory is not writable.' }
    if ((Test-Path -LiteralPath $root) -and -not (Test-Path -LiteralPath (Join-Path $root 'VERSION'))) {
        throw "Refusing to replace an unrelated directory: $root"
    }
    $work = Join-Path $parent ('.install-' + [Guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $work)
    $archive = Join-Path $work $asset
    $checksum = $archive + '.sha256'
    Write-Host 'Checking for Mika updates...'
    if ($env:MIKA_ARCHIVE_PATH) {
        Copy-Item -LiteralPath ($env:MIKA_ARCHIVE_PATH + '.sha256') -Destination $checksum
    } else { Get-MikaFile "$base/$asset.sha256" $checksum 4096 }
    $expected = ((Get-Content -LiteralPath $checksum -Raw).Trim() -split '\s+')[0]
    if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid release checksum file.' }
    $current = $false
    $installedVersion = ''
    $versionFile = Join-Path $root 'VERSION'
    $fingerprint = Join-Path $root 'ARCHIVE_SHA256'
    $binary = Join-Path $root 'bin\mika.exe'
    if (Test-Path -LiteralPath $versionFile) { $installedVersion = [IO.File]::ReadAllText($versionFile).Trim() }
    if ($reinstall -eq '0' -and (Test-Path -LiteralPath $fingerprint) -and (Test-Path -LiteralPath $binary)) {
        if ([IO.File]::ReadAllText($fingerprint).Trim() -eq $expected) {
            try {
                $actual = & $binary --version 2>$null
                $current = $LASTEXITCODE -eq 0 -and $actual -eq ('mika ' + ($installedVersion -replace '^v', ''))
            } catch { $current = $false }
        }
    }
    if ($current) {
        $message = 'Mika ' + ($installedVersion -replace '^v', '') + ' is already up to date.'
    } else {
        if ($env:MIKA_ARCHIVE_PATH) { Copy-Item -LiteralPath $env:MIKA_ARCHIVE_PATH -Destination $archive }
        else { Get-MikaFile "$base/$asset" $archive 268435456 }
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
            throw 'Release checksum mismatch. Existing installation unchanged.'
        }
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
        $versionFile = Join-Path $candidate 'VERSION'
        if (-not (Test-Path -LiteralPath $binary) -or -not (Test-Path -LiteralPath $versionFile)) {
            throw 'Incomplete release package.'
        }
        $candidateVersion = [IO.File]::ReadAllText($versionFile).Trim()
        if ($candidateVersion -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { throw 'Invalid package version.' }
        $actual = & $binary --version
        if ($LASTEXITCODE -ne 0) { throw 'The release binary could not start on this system.' }
        if ($actual -ne ('mika ' + ($candidateVersion -replace '^v', ''))) { throw 'Package version does not match its binary.' }
        [IO.File]::WriteAllText((Join-Path $candidate 'ARCHIVE_SHA256'), $expected.ToLowerInvariant())
        if (Test-Path -LiteralPath $root) {
            $backup = Join-Path $work 'previous-app'
            Move-Item -LiteralPath $root -Destination $backup
        }
        # Record intent before moving: an interrupted/throwing move may already have succeeded.
        $installed = $true
        Move-Item -LiteralPath $candidate -Destination $root
        $null = & (Join-Path $root 'bin\mika.exe') --version
        if ($LASTEXITCODE -ne 0) { throw 'Installed binary failed its startup check.' }
        if ($installedVersion -and $installedVersion -ne $candidateVersion) {
            $message = 'Updated Mika ' + ($installedVersion -replace '^v', '') + ' -> ' + ($candidateVersion -replace '^v', '') + '.'
        } elseif ($installedVersion) { $message = 'Reinstalled Mika ' + ($candidateVersion -replace '^v', '') + '.' }
        else { $message = 'Installed Mika ' + ($candidateVersion -replace '^v', '') + '.' }
    }
    $bin = Join-Path $root 'bin'
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    if (-not ($entries | Where-Object { $_.TrimEnd('\') -ieq $bin.TrimEnd('\') })) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $bin) -join ';'), 'User')
    }
    if (-not (($env:Path -split ';') | Where-Object { $_.TrimEnd('\') -ieq $bin.TrimEnd('\') })) {
        $env:Path = $bin + ';' + $env:Path
    }
    $success = $true
    Write-Host $message
    Write-Host 'Run: mika'
} catch {
    throw "Mika installation failed: $($_.Exception.Message)"
} finally {
    $keepRecovery = $false
    if (-not $success) {
        try {
            $hasBackup = $backup -and (Test-Path -LiteralPath $backup)
            if (($installed -or $hasBackup) -and (Test-Path -LiteralPath $root)) { Remove-Item -LiteralPath $root -Recurse -Force }
            if ($hasBackup) { Move-Item -LiteralPath $backup -Destination $root }
        } catch {
            $keepRecovery = $true
            Write-Warning "Could not restore automatically. Recovery files retained at $work. Close running Mika processes."
        }
    }
    if (-not $keepRecovery -and $work -and (Test-Path -LiteralPath $work)) {
        try { Remove-Item -LiteralPath $work -Recurse -Force }
        catch { Write-Warning "Could not remove installer scratch directory: $work. Close running Mika processes before updating." }
    }
    if ($installLock) { $installLock.Dispose() }
}
}
