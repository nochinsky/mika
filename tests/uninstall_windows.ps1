# Offline removal fixtures, compatible with Windows PowerShell 5.1 and pwsh.
# Never invokes the real entry point or touches the actual user PATH/install.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$source = Split-Path -Parent $PSScriptRoot
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $source 'uninstall.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($function in $ast.FindAll({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst]
}, $true)) { Invoke-Expression $function.Extent.Text }

function Get-MikaUserPath { return $script:testUserPath }
function Set-MikaUserPath([string]$Value) { $script:testUserPath = $Value }
function Assert-True([bool]$Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Expect-Failure([scriptblock]$Action) {
    $failed = $false
    try { & $Action } catch { $failed = $true }
    Assert-True $failed 'Expected removal to be refused.'
}
function New-Fixture([string]$Directory) {
    $parent = Join-Path $Directory 'data/Mika'
    $root = Join-Path $parent 'app'
    $models = Join-Path $parent 'models'
    $bin = Join-Path $root 'bin'
    [void](New-Item -ItemType Directory -Path $bin -Force)
    [void](New-Item -ItemType Directory -Path $models -Force)
    [IO.File]::WriteAllText((Join-Path $root 'VERSION'), "vtest`n")
    [IO.File]::WriteAllText((Join-Path $root 'ARCHIVE_SHA256'), ('a' * 64))
    [IO.File]::WriteAllText((Join-Path $bin 'mika.exe'), 'fake executable, never run')
    [IO.File]::WriteAllText((Join-Path $parent '.installer.lock'), '')
    [IO.File]::WriteAllText((Join-Path $models '.download.lock'), '')
    $model = Join-Path $models 'granite-speech-5.0-470m-turboctc-Q4_K_M.gguf'
    [IO.File]::WriteAllText($model, 'fake model')
    [IO.File]::WriteAllText(($model + '.part.abc'), 'partial')
    $script:testUserPath = 'before;' + $bin + ';after;' + $bin + '-other;'
    $env:Path = $script:testUserPath
    return [pscustomobject]@{ Parent = $parent; Root = $root; Models = $models; Model = $model; Bin = $bin; Directory = $Directory }
}
$script:passed = 0
function Run-Test([string]$Name, [scriptblock]$Action) {
    $directory = Join-Path ([IO.Path]::GetTempPath()) ('Mika removal fixture ü ' + [Guid]::NewGuid().ToString('N'))
    $oldPath = $env:Path
    try {
        $fixture = New-Fixture $directory
        & $Action $fixture
        $script:passed++
        Write-Host "PASS: $Name"
    } finally {
        $env:Path = $oldPath
        if (Test-Path -LiteralPath $directory) { Remove-Item -LiteralPath $directory -Recurse -Force }
    }
}

Run-Test 'full removal, exact PATH cleanup and idempotence' { param($f)
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True (-not (Test-Path -LiteralPath $f.Parent)) 'Full removal left app/model data.'
    Assert-True ($script:testUserPath -ceq ('before;after;' + $f.Bin + '-other;')) 'Unrelated PATH content changed.'
    Assert-True ($env:Path -ceq $script:testUserPath) 'Current process PATH was not cleaned.'
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True (-not (Test-Path -LiteralPath $f.Parent)) 'Repeated removal recreated data.'
}
Run-Test 'keep speech model' { param($f)
    Invoke-MikaUninstall $f.Parent $true $true
    Assert-True (-not (Test-Path -LiteralPath $f.Root)) 'Application was not removed.'
    Assert-True ([IO.File]::ReadAllText($f.Model) -eq 'fake model') 'Model was not preserved.'
    Assert-True (Test-Path -LiteralPath ($f.Model + '.part.abc')) 'Kept partial model was removed.'
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True (-not (Test-Path -LiteralPath $f.Parent)) 'Later full removal failed.'
}
Run-Test 'unrelated data and recovery directories survive' { param($f)
    $notes = Join-Path $f.Models 'notes.txt'
    [IO.File]::WriteAllText($notes, 'private notes')
    $recovery = Join-Path $f.Parent '.install-recovery'
    [void](New-Item -ItemType Directory -Path $recovery)
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True ([IO.File]::ReadAllText($notes) -eq 'private notes') 'Unrelated cache file was deleted.'
    Assert-True (Test-Path -LiteralPath $recovery) 'Recovery directory was removed.'
    Assert-True (-not (Test-Path -LiteralPath $f.Model)) 'Owned model was retained.'
}
Run-Test 'missing/invalid ownership markers refuse deletion' { param($f)
    $hash = Join-Path $f.Root 'ARCHIVE_SHA256'
    Remove-Item -LiteralPath $hash
    Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true }
    Assert-True (Test-Path -LiteralPath $f.Model) 'Cache changed before ownership validation.'
    [IO.File]::WriteAllText($hash, 'bad hash')
    Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true }
    Assert-True (Test-Path -LiteralPath $f.Root) 'Unrecognized app was removed.'
}
Run-Test 'locked installer refuses deletion' { param($f)
    $lock = [IO.File]::Open((Join-Path $f.Parent '.installer.lock'), 'Open', 'ReadWrite', 'None')
    try { Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true } }
    finally { $lock.Dispose() }
    Assert-True (Test-Path -LiteralPath $f.Root) 'Locked installation changed.'
}
Run-Test 'locked download refuses deletion' { param($f)
    $lock = [IO.File]::Open((Join-Path $f.Models '.download.lock'), 'Open', 'ReadWrite', 'None')
    try { Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true } }
    finally { $lock.Dispose() }
    Assert-True (Test-Path -LiteralPath $f.Root) 'App removed during a download.'
    Assert-True (Test-Path -LiteralPath $f.Model) 'Active model removed.'
}
Run-Test 'locked executable refuses deletion before changes' { param($f)
    $lock = [IO.File]::Open((Join-Path $f.Bin 'mika.exe'), 'Open', 'ReadWrite', 'None')
    try { Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true } }
    finally { $lock.Dispose() }
    Assert-True (Test-Path -LiteralPath $f.Model) 'Model removed while executable locked.'
    Assert-True ($env:Path -ceq $script:testUserPath) 'PATH changed on refusal.'
}
Run-Test 'model-named directories refuse deletion before app changes' { param($f)
    Remove-Item -LiteralPath $f.Model
    [void](New-Item -ItemType Directory -Path $f.Model)
    Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true }
    Assert-True (Test-Path -LiteralPath $f.Root) 'Application changed before cache validation.'
}
Run-Test 'declined confirmation makes no changes' { param($f)
    function Confirm-MikaRemoval { return $false }
    Invoke-MikaUninstall $f.Parent $false $false
    Assert-True (Test-Path -LiteralPath $f.Root) 'Decline removed application.'
    Assert-True (Test-Path -LiteralPath $f.Model) 'Decline removed model.'
    Assert-True ($env:Path -ceq $script:testUserPath) 'Decline changed PATH.'
}
Run-Test 'read-only application file is removable' { param($f)
    $file = Join-Path $f.Root 'readonly.txt'
    [IO.File]::WriteAllText($file, 'owned app data')
    [IO.File]::SetAttributes($file, [IO.FileAttributes]::ReadOnly)
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True (-not (Test-Path -LiteralPath $f.Parent)) 'Read-only data prevented cleanup.'
}
Run-Test 'nested directory links do not delete outside content' { param($f)
    $outside = Join-Path $f.Directory 'outside'
    [void](New-Item -ItemType Directory -Path $outside)
    $sentinel = Join-Path $outside 'keep.txt'
    [IO.File]::WriteAllText($sentinel, 'safe')
    $link = Join-Path $f.Root 'nested-link'
    $type = if ($env:OS -eq 'Windows_NT') { 'Junction' } else { 'SymbolicLink' }
    [void](New-Item -ItemType $type -Path $link -Target $outside)
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True ([IO.File]::ReadAllText($sentinel) -eq 'safe') 'Removal traversed a directory link.'
}
Run-Test 'linked application, model and parent roots are refused' { param($f)
    $index = 0
    foreach ($path in @($f.Root, $f.Models, $f.Parent)) {
        $outside = Join-Path $f.Directory ('outside-' + $index++)
        Move-Item -LiteralPath $path -Destination $outside
        $type = if ($env:OS -eq 'Windows_NT') { 'Junction' } else { 'SymbolicLink' }
        [void](New-Item -ItemType $type -Path $path -Target $outside)
        try {
            Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true }
            Assert-True (Test-Path -LiteralPath $f.Model) 'Linked data was modified.'
        } finally {
            [IO.Directory]::Delete($path, $false)
            Move-Item -LiteralPath $outside -Destination $path
        }
    }
}
Run-Test 'payload failure retains ownership for a retry' { param($f)
    $blocked = Join-Path $f.Root 'blocked-payload'
    [IO.File]::WriteAllText($blocked, 'owned data')
    $original = ${function:Remove-MikaTree}
    function Remove-MikaTree([string]$Path, [switch]$ApplicationRoot) {
        if ($Path -eq $blocked) { throw 'Injected payload deletion failure.' }
        & $original $Path -ApplicationRoot:$ApplicationRoot
    }
    Expect-Failure { Invoke-MikaUninstall $f.Parent $false $true }
    Assert-True (Test-Path -LiteralPath (Join-Path $f.Root 'VERSION')) 'Retry lost ownership version.'
    Assert-True (Test-Path -LiteralPath (Join-Path $f.Root 'ARCHIVE_SHA256')) 'Retry lost ownership fingerprint.'
    Remove-Item Function:Remove-MikaTree
    Invoke-MikaUninstall $f.Parent $false $true
    Assert-True (-not (Test-Path -LiteralPath $f.Parent)) 'Retry did not finish removal.'
}
$actual = Remove-MikaPathEntry 'first;"C:\Mika\app\bin\";C:\MIKA\app\bin;C:\Mika\app\bin-extra;;last' 'C:\Mika\app\bin'
Assert-True ($actual -ceq 'first;C:\Mika\app\bin-extra;;last') 'PATH case/quotes/trailing slash matching failed.'
Write-Host "PASS: $script:passed removal fixtures plus Windows PATH normalization; no actual user install/PATH changed"
