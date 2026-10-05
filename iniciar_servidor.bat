@echo off
setlocal enabledelayedexpansion
title Central de Chamados Brasfort - Servidor de Rede
color 0B

:: Garante que o diretorio atual seja a pasta do projeto
cd /d "%~dp0"

echo ======================================================================
echo           CENTRAL DE CHAMADOS BRASFORT - INICIANDO SERVIDOR
echo ======================================================================
echo.

:: 1. Verifica se a pasta do ambiente virtual existe
if not exist "%~dp0venv\Scripts\activate.bat" goto :NO_VENV

:: 2. Ativa o ambiente virtual
call "%~dp0venv\Scripts\activate.bat"

:: 3. Libera a porta 5000 caso tenha ficado presa por execucao anterior
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo [AVISO] Processo anterior PID %%p ocupando a porta 5000. Liberando...
    taskkill /F /PID %%p >nul 2>&1
)

:: 3.1 Garante que a regra do Firewall do Windows esteja ativa para acesso em rede
netsh advfirewall firewall show rule name="Central de Chamados Brasfort (Porta 5000)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FIREWALL] Configurando liberacao da porta 5000 no Firewall do Windows...
    netsh advfirewall firewall add rule name="Central de Chamados Brasfort (Porta 5000)" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
)

:: 4. Obtem o IP real da maquina na rede local atraves do helper Python
set LOCAL_IP=
for /f %%i in ('call "%~dp0venv\Scripts\python.exe" "%~dp0scripts\get_ip.py" 2^>nul') do (
    set "LOCAL_IP=%%i"
)
if not defined LOCAL_IP (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
        if not defined LOCAL_IP (
            set "IP_TEMP=%%a"
            set "IP_TEMP=!IP_TEMP: =!"
            if not "!IP_TEMP!"=="" set "LOCAL_IP=!IP_TEMP!"
        )
    )
)

:: 5. Define variaveis de ambiente
set PYTHONUNBUFFERED=1
set HOST=0.0.0.0
set PORT=5000

cls
echo ======================================================================
echo                 CENTRAL DE CHAMADOS - BRASFORT
echo           SERVIDOR DE REDE ATIVO (ACESSO LOCAL E LAN)
echo ======================================================================
echo.
echo  * Diretorio:      %~dp0
echo  * Servidor WSGI:  Waitress Multi-thread (Pool de 8 threads)
echo  * Firewall:       Porta 5000 TCP Liberada para a Rede Local
echo.
echo  ==================================================================
echo   LINKS DE ACESSO:
echo   - Neste computador:      http://127.0.0.1:5000
echo.
if defined LOCAL_IP (
    echo   - OUTROS COMPUTADORES:   http://!LOCAL_IP!:5000
    echo     (Compartilhe este link com qualquer usuario na mesma rede!)
) else (
    echo   - OUTROS COMPUTADORES:   http://172.16.50.5:5000
    echo     (Compartilhe este link com qualquer usuario na mesma rede!)
)
echo  ==================================================================
echo.
echo  [PWA]  Aplicativo Web PWA disponivel em qualquer navegador.
echo  [DICA] Para parar o servidor, pressione Ctrl + C nesta janela.
echo ======================================================================
echo.
echo  Iniciando servidor de rede e abrindo navegador local...
echo.

:: 6. Abre o navegador padrao no endereco local
start "" http://127.0.0.1:5000

:: 7. Executa o servidor de rede Waitress via app.py
call "%~dp0venv\Scripts\python.exe" app.py

:: 8. Encerramento seguro: esta janela NUNCA fecha sem confirmacao do usuario
set EXIT_CODE=%ERRORLEVEL%
echo.
echo ======================================================================
if %EXIT_CODE% NEQ 0 (
    color 0C
    echo [ALERTA] O servidor encerrou com codigo de erro: %EXIT_CODE%
) else (
    echo [INFO] O servidor foi encerrado.
)
echo ======================================================================
echo.
echo Esta janela nao sera fechada automaticamente para que voce possa ver o log.
echo Pressione qualquer tecla para fechar...
pause >nul
exit /b 0

:NO_VENV
color 0C
echo ======================================================================
echo [ERRO] O ambiente virtual Python [venv] nao foi encontrado!
echo Diretorio verificado: %~dp0venv
echo ======================================================================
echo.
echo Certifique-se de que a pasta venv existe na raiz do projeto.
echo.
echo Pressione qualquer tecla para fechar esta janela...
pause >nul
exit /b 1
