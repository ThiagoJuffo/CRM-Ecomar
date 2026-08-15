#!/bin/bash
# ---------------------------------------------------------------------------
# Script de inicializacao do bench do Frappe CRM para a Ecomar.
#
# Executado automaticamente pelo container "frappe" no primeiro up:
#   - Cria o bench (frappe-bench) na versao configurada.
#   - Aponta MariaDB e Redis para os containers.
#   - Baixa e instala o app "crm" (Frappe CRM).
#   - Cria o site e habilita o modo desenvolvedor.
#
# Nas execucoes seguintes o bench ja existe (persistido no volume
# "frappe-bench"), entao o script apenas inicia os servicos.
# ---------------------------------------------------------------------------
set -e

SITE_NAME="${SITE_NAME:-crm.localhost}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-123}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
CRM_BRANCH="${CRM_BRANCH:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"

cd /home/frappe

# Bench ja inicializado -> apenas inicia
if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo ">> Bench ja existe. Iniciando o Frappe CRM..."
    cd frappe-bench
    exec bench start
fi

echo ">> Criando um novo bench (Frappe ${FRAPPE_BRANCH})..."
bench init --skip-redis-config-generation frappe-bench --version "${FRAPPE_BRANCH}"

cd frappe-bench

echo ">> Apontando MariaDB e Redis para os containers..."
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis e watch do Procfile (rodam em containers/nao sao necessarios)
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

echo ">> Baixando o app Frappe CRM (branch ${CRM_BRANCH})..."
bench get-app crm --branch "${CRM_BRANCH}"

echo ">> Criando o site ${SITE_NAME}..."
bench new-site "${SITE_NAME}" \
    --force \
    --mariadb-root-password "${DB_ROOT_PASSWORD}" \
    --admin-password "${ADMIN_PASSWORD}" \
    --no-mariadb-socket

echo ">> Instalando o Frappe CRM no site..."
bench --site "${SITE_NAME}" install-app crm
bench --site "${SITE_NAME}" set-config developer_mode 1
bench --site "${SITE_NAME}" set-config mute_emails 1
bench --site "${SITE_NAME}" set-config server_script_enabled 1
bench --site "${SITE_NAME}" clear-cache
bench use "${SITE_NAME}"

echo ">> Tudo pronto! Iniciando o Frappe CRM..."
exec bench start
