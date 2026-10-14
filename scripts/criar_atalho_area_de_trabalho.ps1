<#
.SYNOPSIS
    Cria o atalho "AppCaptacao" na Area de Trabalho, com o icone do app.

.DESCRIPTION
    O atalho aponta para "Iniciar AppCaptacao.bat" na raiz do projeto, que confere
    o ambiente e abre o app no navegador. Funciona tambem com a Area de Trabalho
    sincronizada pelo OneDrive.

.PARAMETER Pasta
    Pasta onde o atalho sera criado. Padrao: Area de Trabalho do usuario.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\criar_atalho_area_de_trabalho.ps1
#>
param(
    [string]$Pasta = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$alvo = Join-Path $raiz "Iniciar AppCaptacao.bat"
$icone = Join-Path $raiz "packaging\appcaptacao.ico"

if (-not (Test-Path -LiteralPath $alvo)) {
    throw "Nao encontrei '$alvo'. Rode este script de dentro da pasta scripts do projeto."
}

$atalho = Join-Path $Pasta "AppCaptacao.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($atalho)
$link.TargetPath = $alvo
$link.WorkingDirectory = $raiz
$link.Description = "Abre o AppCaptacao (automacao de relatorios do Sienge)"
$link.WindowStyle = 1
if (Test-Path -LiteralPath $icone) {
    $link.IconLocation = "$icone,0"
}
$link.Save()

Write-Host "Atalho criado: $atalho"
