# Radar DOU + Concursos — diagnostico Windows (uso por INICIAR_SEM_FECHAR.bat).
# Executa o Python com console e salva os erros para que a janela nunca desapareca silenciosamente.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$log = Join-Path $root 'diagnostico_inicio.txt'

function Registro([string] $mensagem) {
    $mensagem = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $mensagem"
    Write-Host $mensagem
    Add-Content -LiteralPath $log -Value $mensagem -Encoding UTF8
}
function Check-Exit([string]$etapa) {
    if ($LASTEXITCODE -ne 0) { throw "$etapa falhou (codigo $LASTEXITCODE). Confira diagnostico_inicio.txt." }
}

Set-Content -LiteralPath $log -Value "RADAR DOU + CONCURSOS | DIAGNOSTICO DE INICIALIZACAO | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8
Registro "Projeto: $root"
Registro "Windows: $([Environment]::OSVersion.VersionString)"
try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'main.py'))) {
        throw 'O arquivo main.py nao foi encontrado. Extraia todo o ZIP do projeto e coloque estes dois arquivos na mesma pasta que main.py.'
    }
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        Registro 'Etapa 1/4: criando ambiente Python...'
        $py = Get-Command 'py.exe' -ErrorAction SilentlyContinue
        if ($py) {
            & $py.Source -3 -m venv (Join-Path $root '.venv') 2>&1 | Tee-Object -FilePath $log -Append
        } else {
            $py = Get-Command 'python.exe' -ErrorAction SilentlyContinue
            if (-not $py) { throw 'Python nao encontrado. Instale Python 3 com suporte Tkinter antes de continuar.' }
            & $py.Source -m venv (Join-Path $root '.venv') 2>&1 | Tee-Object -FilePath $log -Append
        }
        Check-Exit 'Criacao do ambiente Python'
    }
    Registro 'Etapa 2/4: verificando Python e Tkinter...'
    & $python -V 2>&1 | Tee-Object -FilePath $log -Append
    Check-Exit 'Verificacao da versao do Python'
    & $python -c "import tkinter; print('TKINTER_OK',tkinter.TkVersion)" 2>&1 | Tee-Object -FilePath $log -Append
    Check-Exit 'Tkinter (interface grafica)'

    Registro 'Etapa 3/4: verificando dependencias Python...'
    & $python -c "import telegram, requests, bs4, playwright; print('BIBLIOTECAS_OK')" 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        Registro 'Instalando bibliotecas ausentes...'
        & $python -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt') 2>&1 | Tee-Object -FilePath $log -Append
        Check-Exit 'Instalacao das bibliotecas'
    }
    Registro 'Etapa 4/4: inicializando a janela do Radar...'
    Registro 'A janela do PowerShell permanecera aberta mesmo que o aplicativo feche.'
    & $python -X faulthandler -u (Join-Path $root 'main.py') 2>&1 | Tee-Object -FilePath $log -Append
    $codigo = $LASTEXITCODE
    Registro "O aplicativo foi encerrado (codigo $codigo)."
    if ($codigo -ne 0) {
        Registro 'Houve um erro. Procure Traceback/Error no diagnostico_inicio.txt.'
    } else {
        Registro 'O programa encerrou sem codigo de erro. Se nenhuma janela abriu, envie o diagnostico_inicio.txt.'
    }
} catch {
    Registro "FALHA: $($_.Exception.Message)"
    Registro "Detalhes: $($_.ScriptStackTrace)"
}
Registro "Diagnostico gravado em $log"
Write-Host ''
Write-Host 'Pode copiar o arquivo diagnostico_inicio.txt e enviar aqui (oculte qualquer token de bot antes).' -ForegroundColor Yellow
Write-Host 'Esta janela deve continuar aberta. Pressione Enter para sair.' -ForegroundColor Cyan
[void][Console]::ReadLine()
