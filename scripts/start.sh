#!/bin/bash
# Sobe o CRM da Ecomar (Frappe CRM) em ambiente local.
set -e

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo ">> Arquivo .env nao encontrado. Criando a partir do .env.example..."
    cp .env.example .env
fi

echo ">> Subindo os containers (mariadb, redis, frappe)..."
docker compose up -d

echo ""
echo "======================================================================"
echo " CRM da Ecomar subindo!"
echo ""
echo " Na PRIMEIRA execucao a instalacao leva alguns minutos (baixa o"
echo " Frappe, o app CRM e cria o site). Acompanhe o progresso com:"
echo ""
echo "     ./scripts/logs.sh"
echo ""
echo " Quando aparecer a mensagem de que os servicos iniciaram, acesse:"
echo "     http://localhost:$(grep -E '^WEB_PORT=' .env | cut -d= -f2 || echo 8000)"
echo ""
echo " Usuario: Administrator"
echo " Senha:   (valor de ADMIN_PASSWORD no .env, padrao 'admin')"
echo "======================================================================"
