@echo off
REM Acompanha os logs do container do Frappe (util na instalacao inicial).
REM Pressione Ctrl+C para sair.
setlocal
cd /d "%~dp0.."
docker compose logs -f frappe
endlocal
