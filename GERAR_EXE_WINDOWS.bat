@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Radar DOU + Concursos - criar EXE offline para usuarios
color 0B
echo ====================================================
echo RADAR DOU + CONCURSOS ^| GERAR EXE WINDOWS

echo ====================================================
echo.
if not exist "main.py" (echo ERRO: extraia o projeto completo. & goto :falhou)
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (py -3 -m venv .venv) else (python -m venv .venv)
  if errorlevel 1 (echo ERRO: Python 3 nao encontrado ou ambiente falhou. & goto :falhou)
)
echo [1/3] Instalando compilador e dependencias...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-dev.txt
if errorlevel 1 (echo ERRO ao instalar dependencias. & goto :falhou)
echo [2/3] Gerando EXE Windows x64 autonomo...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name RadarDOU --collect-all telegram --collect-all apscheduler --collect-all playwright --collect-all certifi main.py
if errorlevel 1 (echo ERRO de compilacao. & goto :falhou)
if not exist "dist\RadarDOU.exe" (echo ERRO: arquivo EXE nao apareceu. & goto :falhou)
echo [3/3] Testando o EXE pronto sem abrir janela...
start "" /wait "dist\RadarDOU.exe" --self-test
if errorlevel 1 (
  echo ERRO: o executavel nao passou no autoteste.
  echo Veja %%TEMP%%\radar-dou-self-test-erro.txt se existir.
  goto :falhou
)
if not exist "downloads" mkdir "downloads"
copy /Y "dist\RadarDOU.exe" "downloads\RadarDOU.exe" >nul
if errorlevel 1 (echo ERRO: nao foi possivel copiar o EXE. & goto :falhou)
echo.
echo SUCESSO: downloads\RadarDOU.exe

echo Agora este EXE pode ser copiado para outro Windows 10/11 x64,
echo sem instalar Python ou VS Code.
echo.
pause
exit /b 0
:falhou
echo.
echo O EXE NAO FOI CRIADO OU NAO PASSOU NO TESTE.
echo Deixe esta janela aberta para ler os detalhes.
pause
exit /b 1
