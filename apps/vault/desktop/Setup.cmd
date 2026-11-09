@echo off
setlocal
cd /d "%~dp0"
set "VAULT_PYTHON="
set "VAULT_PYTHON_TAG="

call :try_python ".venv313\Scripts\python.exe"
if defined VAULT_PYTHON goto dependencies

if defined KCV_PYTHON_EXE (
    call :try_python "%KCV_PYTHON_EXE%"
    if not defined VAULT_PYTHON goto python_failed
    goto create_venv
)

if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\py.exe" call :try_python "%LOCALAPPDATA%\Microsoft\WindowsApps\py.exe" -V:3.13
if exist "%LOCALAPPDATA%\Python\bin\py.exe" call :try_python "%LOCALAPPDATA%\Python\bin\py.exe" -V:3.13
call :try_python py -3.13
call :try_python python3.13
call :try_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :try_python python
if not defined VAULT_PYTHON goto python_failed

:create_venv
"%VAULT_PYTHON%" %VAULT_PYTHON_TAG% -m venv .venv313
if errorlevel 1 goto failed

:dependencies
".venv313\Scripts\python.exe" -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Open Start-Vault.cmd.
pause
exit /b 0

:python_failed
echo Python 3.13 x64 was not found. Install it or set KCV_PYTHON_EXE to its full path.
:failed
echo Vault setup failed. Review the message above.
pause
exit /b 1

:try_python
if defined VAULT_PYTHON exit /b 0
"%~1" %2 -c "import sys, sysconfig; raise SystemExit(0 if sys.version_info[:2] == (3, 13) and sysconfig.get_platform() == 'win-amd64' else 1)" >nul 2>&1
if not errorlevel 1 (
    set "VAULT_PYTHON=%~1"
    set "VAULT_PYTHON_TAG=%2"
)
exit /b 0
