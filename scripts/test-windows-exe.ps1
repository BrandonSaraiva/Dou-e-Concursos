param([Parameter(Mandatory = $true)][string]$Executable)

$ErrorActionPreference = 'Stop'
$Executable = (Resolve-Path -LiteralPath $Executable).Path
$tempRoot = (Resolve-Path -LiteralPath ([IO.Path]::GetTempPath())).Path
$testRoot = Join-Path $tempRoot ("radar-dou-smoke-" + [Guid]::NewGuid().ToString('N'))
$oldHome = $env:RADAR_DOU_HOME
$oldTestMode = $env:RADAR_DOU_SELF_TEST
$oldPath = $env:PATH

function Invoke-SmokeCase([string]$Argument, [string]$Label) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Argument -WorkingDirectory $testRoot -PassThru
    if (!$process.WaitForExit(90000)) {
        & "$env:SystemRoot/System32/taskkill.exe" /T /F /PID $process.Id | Out-Null
        throw "$Label excedeu 90 segundos"
    }
    if ($process.ExitCode -ne 0) {
        foreach ($name in @('self-test-error.txt', 'falha_inicializacao.txt')) {
            $diagnostic = Join-Path $env:RADAR_DOU_HOME $name
            if (Test-Path -LiteralPath $diagnostic) { Get-Content -LiteralPath $diagnostic }
        }
        throw "$Label falhou: código $($process.ExitCode)"
    }
    Write-Host "$Label passou"
}

try {
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    $env:RADAR_DOU_HOME = Join-Path $testRoot 'persistence'
    $env:RADAR_DOU_SELF_TEST = '1'
    # O executável não pode depender de Python no PATH.
    $env:PATH = "$env:SystemRoot/System32;$env:SystemRoot"
    Invoke-SmokeCase '--self-test' 'Imports empacotados, driver Playwright, DPAPI, configuração e escrita no SQLite'
    Invoke-SmokeCase '--self-test-read' 'Reabertura em outro processo e leitura da configuração e histórico'
    $env:RADAR_DOU_HOME = Join-Path $testRoot 'ui'
    Invoke-SmokeCase '--smoke-gui' 'Abertura e encerramento da interface'
} finally {
    $env:PATH = $oldPath
    $env:RADAR_DOU_HOME = $oldHome
    $env:RADAR_DOU_SELF_TEST = $oldTestMode
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = (Resolve-Path -LiteralPath $testRoot).Path
        $prefix = Join-Path $tempRoot 'radar-dou-smoke-'
        if ($resolved -eq $testRoot -and $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
}
