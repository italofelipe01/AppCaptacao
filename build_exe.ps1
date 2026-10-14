param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

if ($Clean) {
    if (Test-Path "build") {
        Remove-Item -LiteralPath "build" -Recurse -Force
    }
    if (Test-Path "dist") {
        Remove-Item -LiteralPath "dist" -Recurse -Force
    }
}

pyinstaller --noconfirm AppCaptacao.spec
pyinstaller --noconfirm ConfigurarAppCaptacao.spec
