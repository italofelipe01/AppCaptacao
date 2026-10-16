<#
.SYNOPSIS
    Gera project\static\css\tailwind-local.css a partir dos templates.

.DESCRIPTION
    Usa o executavel standalone do Tailwind (sem Node). Na primeira vez baixa o executavel
    para %LOCALAPPDATA%\AppCaptacao\ferramentas e confere o SHA-256 fixado abaixo. Depois roda
    sem internet. Ver docs/specs/frontend-css-gerado.md.

.PARAMETER Observar
    Continua rodando e gera de novo a cada mudanca nos templates.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gerar_css.ps1
#>
param(
    [switch]$Observar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

$versao = "v3.4.17"
# sha256sums.txt do release v3.4.17, linha ./tailwindcss-windows-x64.exe
$sha256 = "67F1C5E3F5A03406A7BF5BADF5ADA09B79F3AE78EC43450C15F7E983068DA346"

$pastaFerramentas = Join-Path $env:LOCALAPPDATA "AppCaptacao\ferramentas"
$tailwind = Join-Path $pastaFerramentas "tailwindcss-$versao-windows-x64.exe"

if (-not (Test-Path -LiteralPath $tailwind)) {
    New-Item -ItemType Directory -Force -Path $pastaFerramentas | Out-Null
    $download = "$tailwind.download"
    $url = "https://github.com/tailwindlabs/tailwindcss/releases/download/$versao/tailwindcss-windows-x64.exe"
    Write-Host "Baixando Tailwind $versao de $url"
    Invoke-WebRequest -Uri $url -OutFile $download -UseBasicParsing
    $obtido = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash
    if ($obtido -ne $sha256) {
        Remove-Item -LiteralPath $download -Force
        throw "SHA-256 do Tailwind baixado nao confere (esperado $sha256, obtido $obtido)."
    }
    Move-Item -LiteralPath $download -Destination $tailwind
}

$parametros = @(
    "--config", (Join-Path $PSScriptRoot "css\tailwind.config.js"),
    "--input", (Join-Path $PSScriptRoot "css\entrada.css"),
    "--output", (Join-Path $raiz "project\static\css\tailwind-local.css")
)
if ($Observar) { $parametros += "--watch" }

& $tailwind @parametros
if ($LASTEXITCODE -ne 0) { throw "Tailwind terminou com codigo $LASTEXITCODE" }
Write-Host "CSS gerado em project\static\css\tailwind-local.css"
