@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv
    ) else (
        py -3.12 -m venv .venv
    )
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :failed

powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "scripts\build-windows.ps1" -Python ".venv\Scripts\python.exe"
if errorlevel 1 goto :failed

echo.
echo RadarDOU.exe compilado e testado em dist\RadarDOU.exe.
pause
exit /b 0

:failed
echo.
echo A compilacao ou a validacao do executavel falhou. Confira a mensagem acima.
pause
exit /b 1
