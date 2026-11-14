# Offline installer transactions with private app roots and an in-memory user PATH.
# Native startup checks use a compiled fixture; no actual user install is touched.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$source = Split-Path -Parent $PSScriptRoot
$installer = [IO.File]::ReadAllText((Join-Path $source 'install.ps1'))
# Substitute only the platform's per-user storage boundary, retaining transaction code.
$replacements = @{
    "[Environment]::GetFolderPath('LocalApplicationData')" = '$script:fixtureHome'
    "[Environment]::GetEnvironmentVariable('Path', 'User')" = '$script:fixtureUserPath'
    "[Environment]::SetEnvironmentVariable('Path', ((`$entries + `$bin) -join ';'), 'User')" = "`$script:fixtureUserPath = ((`$entries + `$bin) -join ';')"
}
foreach ($entry in $replacements.GetEnumerator()) {
    if (-not $installer.Contains($entry.Key)) { throw 'Installer storage boundary changed; update this fixture.' }
    $installer = $installer.Replace($entry.Key, $entry.Value)
}
$install = [scriptblock]::Create($installer)
$directory = Join-Path ([IO.Path]::GetTempPath()) ('mika-install-state-' + [Guid]::NewGuid().ToString('N'))
$oldPath = $env:Path
$oldArchive = $env:MIKA_ARCHIVE_PATH
$oldVersion = $env:MIKA_VERSION
$oldReinstall = $env:MIKA_REINSTALL
function Assert-True([bool]$Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Expect-Refusal([scriptblock]$Action, [string]$Pattern) {
    $failure = $null
    try { & $Action } catch { $failure = $_.Exception.Message }
    Assert-True ($null -ne $failure -and $failure -match $Pattern) "Expected ownership refusal, got: $failure"
}
try {
    $package = Join-Path $directory 'package/mika'
    $fixtureBinary = Join-Path $package 'bin/mika.exe'
    [void](New-Item -ItemType Directory -Path (Split-Path -Parent $fixtureBinary) -Force)
    Add-Type -TypeDefinition 'using System; public static class MikaInstallStateFixture { public static void Main() { Console.WriteLine("mika 1.2.3"); } }' `
        -OutputAssembly $fixtureBinary -OutputType ConsoleApplication
    [IO.File]::WriteAllText((Join-Path $package 'VERSION'), "v1.2.3`n")
    $archive = Join-Path $directory 'release.zip'
    Compress-Archive -LiteralPath $package -DestinationPath $archive
    [IO.File]::WriteAllText(($archive + '.sha256'), (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash)
    $env:MIKA_ARCHIVE_PATH = $archive
    $env:MIKA_VERSION = 'latest'
    $env:MIKA_REINSTALL = '1'
    $script:fixtureHome = Join-Path $directory 'home'
    $script:fixtureUserPath = 'before;after'
    $root = Join-Path $script:fixtureHome 'Mika/app'
    [void](New-Item -ItemType Directory -Path $root -Force)
    $notes = Join-Path $root 'notes.txt'
    [IO.File]::WriteAllText($notes, 'unrelated data')
    [IO.File]::WriteAllText((Join-Path $root 'VERSION'), 'v1.2.2')
    Expect-Refusal { & $install } 'unrelated directory'
    Assert-True ([IO.File]::ReadAllText($notes) -eq 'unrelated data') 'A VERSION file alone claimed unrelated app data.'
    Assert-True ($script:fixtureUserPath -eq 'before;after') 'Refusal changed the user PATH.'
    Write-Host 'PASS: VERSION alone cannot claim an unrelated application directory'

    [IO.File]::WriteAllText((Join-Path $root 'ARCHIVE_SHA256'), 'not-a-fingerprint')
    Expect-Refusal { & $install } 'Invalid installation markers'
    Assert-True ([IO.File]::ReadAllText($notes) -eq 'unrelated data') 'Invalid ownership markers allowed replacement.'
    Write-Host 'PASS: invalid ownership fingerprint refuses replacement'

    [IO.File]::WriteAllText((Join-Path $root 'ARCHIVE_SHA256'), ('a' * 64))
    $outside = Join-Path $directory 'outside-app'
    Move-Item -LiteralPath $root -Destination $outside
    [void](New-Item -ItemType Junction -Path $root -Target $outside)
    try {
        Expect-Refusal { & $install } 'linked or non-directory'
        Assert-True ([IO.File]::ReadAllText((Join-Path $outside 'notes.txt')) -eq 'unrelated data') 'Linked app target changed.'
    } finally {
        [IO.Directory]::Delete($root, $false)
        Move-Item -LiteralPath $outside -Destination $root
    }
    Write-Host 'PASS: linked application roots refuse replacement'

    & $install
    Assert-True ([IO.File]::ReadAllText((Join-Path $root 'VERSION')).Trim() -eq 'v1.2.3') 'Managed installation did not update.'
    Assert-True ([IO.File]::ReadAllText((Join-Path $root 'ARCHIVE_SHA256')).Trim() -eq
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()) 'Updated fingerprint is incorrect.'
    Assert-True ($script:fixtureUserPath -eq ('before;after;' + (Join-Path $root 'bin'))) 'Fixture PATH was not updated.'
    Write-Host 'PASS: valid managed installation still updates and registers its command'
} finally {
    $env:Path = $oldPath
    $env:MIKA_ARCHIVE_PATH = $oldArchive
    $env:MIKA_VERSION = $oldVersion
    $env:MIKA_REINSTALL = $oldReinstall
    $resolved = [IO.Path]::GetFullPath($directory)
    $prefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\mika-install-state-'
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe fixture cleanup target.' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
