@echo off
REM Sobe o CRM da Ecomar (Frappe CRM) em ambiente local no Windows.
setlocal
cd /d "%~dp0.."

if not exist ".env" (
    echo Arquivo .env nao encontrado. Criando a partir do .env.example...
    copy ".env.example" ".env" >nul
)

echo Subindo os containers (mariadb, redis, frappe)...
docker compose up -d
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao subir. O Docker Desktop esta aberto e rodando?
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo  CRM da Ecomar subindo!
echo.
echo  Na PRIMEIRA vez a instalacao leva alguns minutos. Acompanhe com:
echo      scripts\logs.bat
echo.
echo  Depois acesse:  http://localhost:8000
echo  Usuario: Administrator   Senha: admin
echo ======================================================================
pause
endlocal
