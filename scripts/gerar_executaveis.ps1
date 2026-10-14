<#
.SYNOPSIS
    Gera dist\AppCaptacao.exe e dist\ConfigurarAppCaptacao.exe com o PyInstaller.

.PARAMETER Limpar
    Apaga build\ e dist\ antes de gerar.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gerar_executaveis.ps1 -Limpar
#>
param(
    [switch]$Limpar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente .venv nao encontrado. Abra 'Iniciar AppCaptacao.bat' uma vez para cria-lo."
}

& $python -m pip install --disable-pip-version-check -q -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar requirements-dev.txt" }

if ($Limpar) {
    foreach ($pasta in "build", "dist") {
        if (Test-Path -LiteralPath $pasta) { Remove-Item -LiteralPath $pasta -Recurse -Force }
    }
}

foreach ($spec in "packaging\AppCaptacao.spec", "packaging\ConfigurarAppCaptacao.spec") {
    & $python -m PyInstaller --noconfirm $spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executavel de $spec" }
}

Write-Host ""
Write-Host "Executaveis gerados em $raiz\dist:"
Get-ChildItem -LiteralPath (Join-Path $raiz "dist") -Filter *.exe | ForEach-Object { Write-Host "  $($_.Name)" }
