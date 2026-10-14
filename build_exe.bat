@echo off
setlocal

cd /d "%~dp0"

if /I "%1"=="clean" (
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
)

python -m PyInstaller --noconfirm AppCaptacao.spec
if errorlevel 1 (
    echo.
    echo Falha ao gerar o executavel principal.
    exit /b 1
)

python -m PyInstaller --noconfirm ConfigurarAppCaptacao.spec

if errorlevel 1 (
    echo.
    echo Falha ao gerar o configurador.
    exit /b 1
)

echo.
echo Executaveis gerados em dist\AppCaptacao.exe e dist\ConfigurarAppCaptacao.exe
exit /b 0
