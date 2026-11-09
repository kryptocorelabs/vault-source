@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv313\Scripts\pythonw.exe" (
    echo Run Setup.cmd before opening Vault.
    pause
    exit /b 1
)
start "" "%~dp0.venv313\Scripts\pythonw.exe" "%~dp0apps\vault\desktop\vault.pyw"
