@echo off
REM CUIDADO: apaga TODOS os dados (banco e bench) e permite reinstalar do zero.
setlocal
cd /d "%~dp0.."
set /p resp="Isso vai APAGAR todos os dados do CRM local. Continuar? (s/N) "
if /i "%resp%"=="s" goto apagar
if /i "%resp%"=="sim" goto apagar
echo Cancelado. Nada foi apagado.
goto fim

:apagar
echo Removendo containers e volumes...
docker compose down -v
echo Pronto. Rode scripts\start.bat para instalar do zero.

:fim
pause
endlocal
