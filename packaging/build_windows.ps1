# Builds the Windows SnapForge .exe, verifies it with --self-test, and
# zips the result into a single file ready to share.
#
# Run from the repository root, with the project's virtual environment
# active (pip install -e ".[dev]" first — see README.md):
#
#   .\packaging\build_windows.ps1
#
# Output: packaging\dist\SnapForge-v0.1.0-windows.zip

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

Remove-Item -Recurse -Force build, dist, snapforge.spec -ErrorAction SilentlyContinue

$iconArg = @()
if (Test-Path "packaging\icons\snapforge.ico") {
    $iconArg = @("--icon", "packaging\icons\snapforge.ico")
}

pyinstaller --noconfirm --windowed --name SnapForge @iconArg --paths src src\snapforge\main.py

Write-Host "Running self-test against the built exe..."
& ".\dist\SnapForge\SnapForge.exe" --self-test
if ($LASTEXITCODE -ne 0) {
    Write-Error "Self-test failed (exit code $LASTEXITCODE) — not zipping a broken build."
    exit 1
}

$version = (python -c "import sys; sys.path.insert(0, 'src'); import snapforge; print(snapforge.__version__)").Trim()
$zipName = "SnapForge-v$version-windows.zip"
Compress-Archive -Path "dist\SnapForge" -DestinationPath $zipName -Force

Write-Host "Done: $zipName"
