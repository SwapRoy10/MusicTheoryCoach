param(
    [Parameter(Mandatory=$true)][string]$Score,
    [string]$Assignment,
    [string]$Out = "output",
    [switch]$AllowSoprano,
    [switch]$Pdf,
    [string]$MuseScore
)
$runtime = Join-Path $PSScriptRoot '.runtime\python\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = 'python' }
$arguments = @((Join-Path $PSScriptRoot 'run.py'), $Score, '--out', $Out)
if ($Assignment) { $arguments += @('--assignment', $Assignment) }
if ($AllowSoprano) { $arguments += '--allow-soprano' }
if ($Pdf) { $arguments += '--pdf' }
if ($MuseScore) { $arguments += @('--musescore', $MuseScore) }
& $runtime @arguments
exit $LASTEXITCODE
