$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Push-Location $repo
try {
    npm.cmd ci
    npm.cmd run check
    npm.cmd run build
    Push-Location (Join-Path $repo 'backend')
    try {
        python -m pip install -e '.[drivers,release]'
        python -m PyInstaller (Join-Path $repo 'packaging\windows\polarmarine_gcs.spec') --noconfirm
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
