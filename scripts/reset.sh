#!/bin/bash
# CUIDADO: apaga TODOS os dados (banco de dados e bench) e permite recomecar
# a instalacao do zero. Use apenas em ambiente de desenvolvimento.
set -e

cd "$(dirname "$0")/.."

read -r -p ">> Isso vai APAGAR todos os dados do CRM local. Continuar? (s/N) " resposta
case "$resposta" in
    s|S|sim|SIM)
        echo ">> Removendo containers e volumes..."
        docker compose down -v
        echo ">> Pronto. Rode ./scripts/start.sh para instalar do zero."
        ;;
    *)
        echo ">> Cancelado. Nada foi apagado."
        ;;
esac
