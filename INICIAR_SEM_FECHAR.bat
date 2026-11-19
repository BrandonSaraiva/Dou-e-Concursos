@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Radar DOU - diagnostico Windows
if not exist "%~dp0DIAGNOSTICAR_RADAR.ps1" (
    echo ERRO: DIAGNOSTICAR_RADAR.ps1 nao foi encontrado na mesma pasta.
    echo Extraia OS DOIS arquivos do pacote de diagnostico na pasta do Radar.
    pause
    exit /b 1
)
rem -NoExit mantem o PowerShell aberto inclusive quando o Python termina inesperadamente.
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0DIAGNOSTICAR_RADAR.ps1"
