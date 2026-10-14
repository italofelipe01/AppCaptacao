@echo off
rem Duplo clique: cria o atalho "AppCaptacao" na Area de Trabalho.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar_atalho_area_de_trabalho.ps1"
if errorlevel 1 (
    echo.
    echo Nao foi possivel criar o atalho. Veja a mensagem acima.
)
echo.
pause
