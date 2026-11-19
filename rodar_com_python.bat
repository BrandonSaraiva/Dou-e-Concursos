@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Radar DOU + Concursos - inicializador com diagnostico
color 0B
echo ================================================================
echo       RADAR DOU + CONCURSOS  -  WINDOWS
echo ================================================================
echo.
echo Pasta: %CD%
echo.
if not exist "main.py" (
  echo ERRO: o arquivo main.py nao esta nesta pasta.
  echo Extraia o ZIP completo antes de executar este .bat.
  goto :failed
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Preparando Python para este aplicativo...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo ERRO: Python nao encontrado neste computador.
      echo Instale o Python 3 em https://www.python.org/downloads/windows/
      echo Durante a instalacao, marque 'Add Python to PATH'.
      goto :failed
    )
    python -m venv .venv
  )
  if errorlevel 1 (
    echo ERRO: nao foi possivel criar o ambiente Python.
    goto :failed
  )
)
echo [2/3] Conferindo as bibliotecas necessarias...
".venv\Scripts\python.exe" -c "import telegram, requests, bs4, playwright" >nul 2>nul
if errorlevel 1 (
  echo Bibliotecas ausentes: instalando (necessita internet)...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo ERRO: houve falha ao instalar as bibliotecas.
    goto :failed
  )
)
echo [3/3] Abrindo a janela do Radar DOU + Concursos...
echo.
echo ATENCAO: esta janela fica aberta para mostrar eventuais erros.
echo Se o aplicativo abrir, deixe esta janela minimizada.
echo.
".venv\Scripts\python.exe" -u main.py
set "APP_EXIT=%ERRORLEVEL%"
echo.
if not "%APP_EXIT%"=="0" (
  echo ERRO: o aplicativo terminou com codigo %APP_EXIT%.
  echo Copie o erro mostrado acima e envie para diagnostico.
) else (
  echo O Radar DOU foi encerrado normalmente.
)
echo.
pause
exit /b %APP_EXIT%

:failed
echo.
echo O Radar nao conseguiu iniciar. Veja a mensagem acima.
echo.
pause
exit /b 1
