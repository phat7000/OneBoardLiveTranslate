# Build a complete runtime on the developer machine; customers only run the EXE.
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$Version = "",
    [string]$Icon = "",
    [string]$Iscc = "",
    [switch]$AllowDirty,
    [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Python) { $Python = Join-Path $ProjectDir ".venv\Scripts\python.exe" }
$BuildArgs = @((Join-Path $ProjectDir "packaging\build_oneboard.py"))
if ($Version) { $BuildArgs += @("--version", $Version) }
if ($Icon) { $BuildArgs += @("--icon", $Icon) }
if ($Iscc) { $BuildArgs += @("--iscc", $Iscc) }
if ($AllowDirty) { $BuildArgs += "--allow-dirty" }
if ($SkipArchive) { $BuildArgs += "--skip-archive" }
& $Python @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "OneBoard release build failed (exit $LASTEXITCODE)" }
