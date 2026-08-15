@echo off
REM Para o CRM da Ecomar sem apagar os dados.
setlocal
cd /d "%~dp0.."
echo Parando os containers do CRM da Ecomar...
docker compose down
echo.
echo Pronto. Os dados foram preservados. Para subir de novo: scripts\start.bat
pause
endlocal
