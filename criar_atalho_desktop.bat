@echo off
title Criar Atalho na Area de Trabalho - Central de Chamados
color 0B
cd /d "%~dp0"

echo ======================================================================
echo    CRIANDO BOTAO/ATALHO NA AREA DE TRABALHO PARA O SERVIDOR FLASK
echo ======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\criar_atalho_desktop.ps1"

echo.
echo Pressione qualquer tecla para fechar esta janela...
pause >nul
