@echo off
setlocal EnableExtensions
rem pushd (e nao cd /d) tambem abre a pasta quando ela esta na rede (\\servidor\...).
pushd "%~dp0"
title AppCaptacao

echo ==============================================================
echo   AppCaptacao - automacao de relatorios do Sienge
echo ==============================================================
echo.

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" goto criar_venv

rem O .venv guarda o caminho do Python do computador que o criou. Copiado junto
rem com a pasta (por exemplo, dentro de um .zip), ele nao abre em outra maquina.
"%VENV_PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto iniciar

echo O ambiente .venv desta pasta nao funciona neste computador
echo (foi criado em outra maquina ou esta incompleto). Ele sera recriado.
rd /s /q "%VENV_DIR%" 2>nul
if exist "%VENV_DIR%" goto falha_remover_venv

:criar_venv
echo Preparando o ambiente do aplicativo neste computador.
call :localizar_python
if errorlevel 1 goto sem_python

echo Criando o ambiente virtual em .venv ...
%PYTHON_SISTEMA% -m venv "%VENV_DIR%"
if errorlevel 1 goto falha_venv
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check -q
echo.

:iniciar
rem O run.py instala as bibliotecas que faltarem, confere a configuracao,
rem o navegador e o banco, e so entao abre o app no navegador.
"%VENV_PY%" "%~dp0run.py" %*
if errorlevel 1 goto falha_app
popd
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

:falha_remover_venv
echo.
echo [ERRO] Nao foi possivel apagar o .venv antigo desta pasta.
echo        Feche outras janelas do AppCaptacao, apague a pasta .venv
echo        e abra este arquivo novamente.
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
popd
exit /b 1
