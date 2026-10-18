# Per-user Windows removal. PowerShell 5.1+; no admin or execution-policy change.
& {
param([switch]$KeepModel, [switch]$Yes)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-MikaItem([string]$Path) {
    try { return Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch {
        if ($_.CategoryInfo.Category -eq 'ObjectNotFound') { return $null }
        throw
    }
}

function Assert-MikaDirectory([string]$Path) {
    $item = Get-MikaItem $Path
    if ($null -ne $item -and (-not $item.PSIsContainer -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint))) {
        throw "Refusing a linked or non-directory application/data path: $Path"
    }
}

function Assert-MikaLock([string]$Path) {
    $item = Get-MikaItem $Path
    if ($null -ne $item -and ($item.PSIsContainer -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint))) { throw "Unsafe lock file: $Path" }
}

function Assert-MikaInstallation([string]$Parent) {
    $root = Join-Path $Parent 'app'
    $models = Join-Path $Parent 'models'
    foreach ($directory in @($Parent, $root, $models)) { Assert-MikaDirectory $directory }
    if ($null -ne (Get-MikaItem $root)) {
        foreach ($name in @('VERSION', 'ARCHIVE_SHA256')) {
            $marker = Get-MikaItem (Join-Path $root $name)
            if ($null -eq $marker -or $marker.PSIsContainer -or $marker.Length -gt 256 -or
                ($marker.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw "Not an installer-managed app; refusing to remove $root"
            }
        }
        $version = [IO.File]::ReadAllText((Join-Path $root 'VERSION')).Trim()
        $hash = [IO.File]::ReadAllText((Join-Path $root 'ARCHIVE_SHA256')).Trim()
        if ($version -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or $hash -notmatch '^[a-fA-F0-9]{64}$') {
            throw "Invalid installation markers; refusing to remove $root"
        }
    }
    Assert-MikaLock (Join-Path $Parent '.installer.lock')
    Assert-MikaLock (Join-Path $models '.download.lock')
}

function Remove-MikaTree([string]$Path, [switch]$ApplicationRoot) {
    $item = Get-MikaItem $Path
    if ($null -eq $item) { return }
    # Never recurse through symlinks/junctions, including on Windows PowerShell 5.1.
    if ($item.PSIsContainer) {
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) {
                if ($ApplicationRoot -and $child.Name -in @('VERSION', 'ARCHIVE_SHA256')) { continue }
                Remove-MikaTree $child.FullName
            }
            if ($ApplicationRoot) {
                # Retain ownership markers until payload deletion succeeds, for retries.
                Remove-MikaTree (Join-Path $Path 'VERSION')
                Remove-MikaTree (Join-Path $Path 'ARCHIVE_SHA256')
            }
        }
        [IO.Directory]::Delete($Path, $false)
    } else {
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            [IO.File]::SetAttributes($Path, ($item.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)))
        }
        [IO.File]::Delete($Path)
    }
}

function Remove-MikaPathEntry([string]$Value, [string]$Bin) {
    $target = $Bin.TrimEnd([char[]]'\/')
    $entries = @($Value -split ';' | Where-Object {
        -not [string]::Equals($_.Trim().Trim('"').TrimEnd([char[]]'\/'), $target, [StringComparison]::OrdinalIgnoreCase)
    })
    return [string]::Join(';', [string[]]$entries)
}

function Get-MikaUserPath { return [Environment]::GetEnvironmentVariable('Path', 'User') }
function Set-MikaUserPath([string]$Value) { [Environment]::SetEnvironmentVariable('Path', $Value, 'User') }

function Confirm-MikaRemoval {
    if ([Console]::IsInputRedirected) { throw 'No interactive terminal; no changes made. Set MIKA_UNINSTALL_YES=1 only for deliberate unattended removal.' }
    $answer = Read-Host 'Remove Mika? [y/N]'
    return $answer -match '^(y|yes)$'
}

function Invoke-MikaUninstall([string]$Parent, [bool]$KeepModel, [bool]$Yes) {
    if (-not [IO.Path]::IsPathRooted($Parent)) { throw 'An absolute per-user data directory is required.' }
    $root = Join-Path $Parent 'app'
    $models = Join-Path $Parent 'models'
    $bin = Join-Path $root 'bin'
    $model = 'granite-speech-5.0-470m-turboctc-Q4_K_M.gguf'
    Assert-MikaInstallation $Parent
    Write-Host "Mika will remove:`n  App: $root"
    if ($KeepModel) { Write-Host "  Speech model will be kept: $models" }
    else { Write-Host "  Cached speech model and its partial downloads: $models" }
    Write-Host '  Mika user-PATH entry. Unrelated files and notes outside the app are kept.'
    Write-Host 'Close Mika before continuing.'
    if (-not $Yes -and -not (Confirm-MikaRemoval)) {
        Write-Host 'Cancelled; no changes made.'
        return
    }
    $installLock = $null
    $downloadLock = $null
    try {
        if ($null -ne (Get-MikaItem $Parent)) {
            try {
                $installLock = [IO.File]::Open((Join-Path $Parent '.installer.lock'), [IO.FileMode]::OpenOrCreate,
                                              [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            } catch { throw 'Another Mika installer/uninstaller is running, or the directory is not writable.' }
        }
        if ($null -ne (Get-MikaItem $models)) {
            try {
                $downloadLock = [IO.File]::Open((Join-Path $models '.download.lock'), [IO.FileMode]::OpenOrCreate,
                                               [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            } catch { throw 'A Mika model download is running, or the cache is not writable. Close Mika and try again.' }
        }
        Assert-MikaInstallation $Parent
        $modelFiles = @()
        if (-not $KeepModel -and $null -ne (Get-MikaItem $models)) {
            $pattern = '^' + [regex]::Escape($model) + '(\.part\..+)?$'
            $modelFiles = @(Get-ChildItem -LiteralPath $models -Force | Where-Object { $_.Name -match $pattern })
            foreach ($file in $modelFiles) {
                if ($file.PSIsContainer) { throw "Not a model file: $($file.FullName)" }
            }
        }
        # Fail before removal for the ordinary running-app case; never kill processes.
        $executable = Join-Path $bin 'mika.exe'
        $item = Get-MikaItem $executable
        if ($null -ne $item -and -not $item.PSIsContainer -and
            -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            try {
                $probe = [IO.File]::Open($executable, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
                $probe.Dispose()
            } catch { throw 'Mika is running or its executable is locked. Close Mika and try again.' }
        }
        Remove-MikaTree $root -ApplicationRoot
        foreach ($file in $modelFiles) { Remove-MikaTree $file.FullName }
        $oldPath = Get-MikaUserPath
        $newPath = Remove-MikaPathEntry $oldPath $bin
        if ($newPath -cne $oldPath) { Set-MikaUserPath $newPath }
        $env:Path = Remove-MikaPathEntry $env:Path $bin
        if ($null -ne $downloadLock) {
            $downloadLock.Dispose()
            $downloadLock = $null
            [IO.File]::Delete((Join-Path $models '.download.lock'))
        }
        if ($null -ne (Get-MikaItem $models) -and @(Get-ChildItem -LiteralPath $models -Force).Count -eq 0) {
            [IO.Directory]::Delete($models, $false)
        }
        if ($null -ne $installLock) {
            $remaining = @(Get-ChildItem -LiteralPath $Parent -Force)
            if ($remaining.Count -eq 1 -and $remaining[0].Name -eq '.installer.lock') {
                $installLock.Dispose()
                $installLock = $null
                [IO.File]::Delete((Join-Path $Parent '.installer.lock'))
                # A concurrent new install may recreate content; never recurse here.
                try { [IO.Directory]::Delete($Parent, $false) }
                catch { Write-Warning "Directory retained: $Parent" }
            } else {
                Write-Warning "Retained models, unrelated files or recovery directories remain in $Parent"
            }
        }
        Write-Host 'Mika uninstalled. Restart other terminals to refresh PATH and command lookup.'
    } finally {
        if ($null -ne $downloadLock) { $downloadLock.Dispose() }
        if ($null -ne $installLock) { $installLock.Dispose() }
    }
}

try {
    if ($env:OS -ne 'Windows_NT') { throw 'Use uninstall.sh on Linux or WSL.' }
    foreach ($name in @('MIKA_KEEP_MODEL', 'MIKA_UNINSTALL_YES')) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($value -and $value -ne '0' -and $value -ne '1') { throw "$name must be 0 or 1." }
    }
    $parent = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Mika'
    Invoke-MikaUninstall $parent ($KeepModel.IsPresent -or $env:MIKA_KEEP_MODEL -eq '1') ($Yes.IsPresent -or $env:MIKA_UNINSTALL_YES -eq '1')
} catch {
    throw "Mika uninstallation failed: $($_.Exception.Message). If removal was interrupted, rerun after closing Mika."
}
} @args
