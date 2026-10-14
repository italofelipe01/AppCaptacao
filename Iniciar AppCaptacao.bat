@echo off
setlocal
cd /d "%~dp0"
title AppCaptacao

where python >nul 2>nul
if errorlevel 1 (
    echo Python nao foi encontrado no PATH.
    echo Instale o Python ou use o executavel empacotado do AppCaptacao.
    pause
    exit /b 1
)

python ".\run.py"
if errorlevel 1 (
    echo.
    echo O AppCaptacao foi encerrado com erro.
    pause
)
