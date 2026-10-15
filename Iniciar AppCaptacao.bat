@echo off
setlocal EnableExtensions
rem pushd (e nao cd /d) tambem abre a pasta quando ela esta na rede (\\servidor\...).
pushd "%~dp0"
title AppCaptacao
rem Mostra a saida do Python na hora, linha a linha.
set "PYTHONUNBUFFERED=1"
set "SAIDA=1"

echo ==============================================================
echo   AppCaptacao - automacao de relatorios do Sienge
echo ==============================================================
echo.

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo [1/3] Conferindo o ambiente Python desta pasta (.venv)...
if not exist "%VENV_PY%" goto venv_ausente

rem O .venv guarda o caminho do Python do computador que o criou. Copiado junto
rem com a pasta (por exemplo, dentro de um .zip), ele nao abre em outra maquina.
"%VENV_PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto venv_pronto

echo       O .venv desta pasta nao funciona neste computador: foi criado em
echo       outra maquina ou esta incompleto. Resposta do Python do .venv:
"%VENV_PY%" -c "import sys; print('      Python', sys.version.split()[0], '- o AppCaptacao precisa do 3.11 ou mais novo')" 2>&1
echo       Apagando o .venv antigo para recria-lo...
rd /s /q "%VENV_DIR%" 2>nul
if exist "%VENV_DIR%" goto falha_remover_venv
goto criar_venv

:venv_ausente
echo       Ainda nao existe .venv nesta pasta: primeira execucao neste computador.

:criar_venv
echo.
echo [2/3] Preparando o ambiente do aplicativo...
call :localizar_python
if errorlevel 1 goto sem_python
echo       Python encontrado: %PYTHON_SISTEMA%
echo       Criando o ambiente virtual em .venv ...
%PYTHON_SISTEMA% -m venv "%VENV_DIR%"
if errorlevel 1 goto falha_venv
echo       Atualizando o pip ...
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check -q
if errorlevel 1 echo       [AVISO] O pip nao foi atualizado; seguindo com a versao atual.
echo       Ambiente criado. As bibliotecas sao instaladas no passo 3.
goto iniciar

:venv_pronto
"%VENV_PY%" -c "import sys; print('      .venv pronto: Python', sys.version.split()[0])"
echo.
echo [2/3] Ambiente ja preparado neste computador.

:iniciar
echo.
echo [3/3] Iniciando o AppCaptacao: checklist do ambiente e abertura do app.
echo       As etapas da automacao e os erros aparecem nesta janela.
echo.
rem O run.py instala as bibliotecas que faltarem, confere a configuracao,
rem o navegador e o banco, e so entao abre o app no navegador.
"%VENV_PY%" "%~dp0run.py" %*
set "CODIGO=%errorlevel%"
if not "%CODIGO%"=="0" goto falha_app

echo.
echo ==============================================================
echo   [ OK  ] AppCaptacao finalizado sem erros.
echo ==============================================================
set "SAIDA=0"
goto pausar

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
echo   [ERRO ] Python 3.11 ou mais novo nao foi encontrado.
echo           Instale pelo site https://www.python.org/downloads/ marcando
echo           "Add python.exe to PATH" e abra este arquivo novamente.
echo           Alternativa sem Python: use o AppCaptacao.exe empacotado.
goto pausar

:falha_remover_venv
echo.
echo   [ERRO ] Nao foi possivel apagar o .venv antigo desta pasta.
echo           Feche outras janelas do AppCaptacao, apague a pasta .venv
echo           e abra este arquivo novamente.
goto pausar

:falha_venv
echo.
echo   [ERRO ] Nao foi possivel criar o ambiente virtual em .venv.
echo           Confira se a pasta do projeto permite gravacao.
goto pausar

:falha_app
echo.
echo ==============================================================
echo   [ERRO ] O AppCaptacao terminou com erro (codigo %CODIGO%).
echo           Leia as mensagens acima. Detalhes no log tecnico, no caminho
echo           mostrado em "Log tecnico:" no inicio desta janela.
echo ==============================================================
goto pausar

:pausar
rem Sucesso ou erro, a janela so fecha quando o usuario apertar uma tecla.
echo.
echo Pressione qualquer tecla para fechar esta janela...
pause >nul
popd
exit /b %SAIDA%
