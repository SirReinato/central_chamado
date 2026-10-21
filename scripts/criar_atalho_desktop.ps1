# =====================================================================
# SCRIPT POWERSHELL: CRIAR ATALHO NA ÁREA DE TRABALHO
# Hub Central - SirReinato Brasfort - Iniciar Servidor Flask
# =====================================================================

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$BatTarget = Join-Path $ProjectDir "iniciar_servidor.bat"
$IconTarget = Join-Path $ProjectDir "static\icons\favicon.ico"

# Identifica a Área de Trabalho (Desktop) do usuário dinamicamente
$DesktopDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)

if (-not (Test-Path $DesktopDir)) {
    Write-Error "Pasta da Área de Trabalho não encontrada: $DesktopDir"
    exit 1
}

if (-not (Test-Path $BatTarget)) {
    Write-Error "Script iniciar_servidor.bat não encontrado em: $BatTarget"
    exit 1
}

$ShortcutPath = Join-Path $DesktopDir "Iniciar Hub Central - SirReinato Brasfort.lnk"

Write-Host "Criando atalho na Área de Trabalho..." -ForegroundColor Cyan
Write-Host "Destino: $ShortcutPath" -ForegroundColor Gray

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatTarget
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "Iniciar o Hub Central - SirReinato Brasfort (Servidor de Rede Local)"

if (Test-Path $IconTarget) {
    $Shortcut.IconLocation = "$IconTarget,0"
}

$Shortcut.Save()

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "   ATALHO CRIADO COM SUCESSO NA SUA ÁREA DE TRABALHO!" -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "Nome do Atalho: Iniciar Hub Central - SirReinato Brasfort.lnk" -ForegroundColor White
Write-Host "Localização:    $ShortcutPath" -ForegroundColor White
Write-Host "Ícone:          Personalizado Brasfort (favicon.ico)" -ForegroundColor White
Write-Host "Ação:           Inicia o Servidor de Rede e abre o navegador" -ForegroundColor White
Write-Host "===============================================================" -ForegroundColor Green
