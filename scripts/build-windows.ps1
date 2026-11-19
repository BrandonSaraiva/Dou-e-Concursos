param(
    [string]$Python = 'python',
    [switch]$SmokeOnly
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    if (!$SmokeOnly) {
        & $Python -c "import platform, struct; assert platform.system() == 'Windows' and struct.calcsize('P') == 8, 'Use Python para Windows x64'"
        if ($LASTEXITCODE -ne 0) { throw 'Python Windows x64 indisponível' }
        & $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name RadarDOU `
            --collect-all telegram --collect-all apscheduler --collect-all playwright --collect-all certifi main.py
        if ($LASTEXITCODE -ne 0) { throw 'A compilação com PyInstaller falhou' }
    }

    $exe = (Resolve-Path -LiteralPath 'dist/RadarDOU.exe').Path
    & ./scripts/test-windows-exe.ps1 -Executable $exe
    Write-Host "Executável validado: $exe"
} finally {
    Pop-Location
}
