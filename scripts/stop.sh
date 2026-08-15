#!/bin/bash
# Para o CRM da Ecomar sem apagar os dados (banco e bench sao preservados).
set -e

cd "$(dirname "$0")/.."

echo ">> Parando os containers do CRM da Ecomar..."
docker compose down

echo ">> Pronto. Os dados foram preservados nos volumes."
echo "   Para subir de novo: ./scripts/start.sh"
