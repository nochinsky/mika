# Native PowerShell 5.1 parser and HTTPS/redirect test, without installing or recording.
$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $source 'install.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$function = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-MikaFile'
}, $true)
if ($null -eq $function) { throw 'Missing installer download function.' }
Invoke-Expression $function.Extent.Text
$file = Join-Path $env:TEMP ('mika-https-test-' + [Guid]::NewGuid().ToString('N'))
try {
    # This GitHub route redirects to raw.githubusercontent.com, exercising real HTTPS hops.
    Get-MikaFile 'https://github.com/nochinsky/mika/raw/refs/heads/main/LICENSE' $file 16384
    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $source 'LICENSE')).Hash
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash -ne $expected) { throw 'Downloaded content mismatch.' }
    $rejected = $false
    try { Get-MikaFile 'http://127.0.0.1:1/forbidden' $file 16384 }
    catch { $rejected = $true }
    if (-not $rejected) { throw 'Installer accepted an insecure URL.' }
    Write-Host 'PASS: Windows PowerShell syntax, HTTPS, redirect handling and protocol rejection'
} finally {
    if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
}
