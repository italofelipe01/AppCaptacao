@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AppCaptacao

echo ==============================================================
echo   AppCaptacao - automacao de relatorios do Sienge
echo ==============================================================
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto iniciar

echo Primeira execucao: preparando o ambiente do aplicativo.
call :localizar_python
if errorlevel 1 goto sem_python

echo Criando o ambiente virtual em .venv ...
%PYTHON_SISTEMA% -m venv "%~dp0.venv"
if errorlevel 1 goto falha_venv
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check -q
echo.

:iniciar
rem O run.py instala as bibliotecas que faltarem, confere a configuracao,
rem o navegador e o banco, e so entao abre o app no navegador.
"%VENV_PY%" "%~dp0run.py" %*
if errorlevel 1 goto falha_app
exit /b 0

:localizar_python
set "PYTHON_SISTEMA="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_SISTEMA=py -3"
)
if defined PYTHON_SISTEMA exit /b 0
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_SISTEMA=python"
    exit /b 0
)
exit /b 1

:sem_python
echo.
echo [ERRO] Python 3.11 ou mais novo nao foi encontrado.
echo        Instale pelo site https://www.python.org/downloads/ marcando
echo        "Add python.exe to PATH" e abra este arquivo novamente.
echo        Alternativa sem Python: use o AppCaptacao.exe empacotado.
goto pausar

:falha_venv
echo.
echo [ERRO] Nao foi possivel criar o ambiente virtual em .venv.
echo        Confira se a pasta do projeto permite gravacao.
goto pausar

:falha_app
echo.
echo O AppCaptacao foi encerrado. Leia as mensagens acima.
goto pausar

:pausar
echo.
pause
exit /b 1
