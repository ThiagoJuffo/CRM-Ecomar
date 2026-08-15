#!/bin/bash
# ---------------------------------------------------------------------------
# Script de inicializacao do bench do Frappe CRM para a Ecomar.
#
# Executado automaticamente pelo container "frappe":
#   - Cria o bench (frappe-bench) na versao configurada.
#   - Aponta MariaDB e Redis para os containers.
#   - Instala os apps "crm" (Frappe CRM) e "ecomar_crm" (customizacoes/branding).
#   - Cria o site e habilita o modo desenvolvedor.
#
# E idempotente: se o bench ja existe mas o site sumiu, ele recria o site;
# caso contrario, apenas inicia os servicos.
# ---------------------------------------------------------------------------
set -e

SITE_NAME="${SITE_NAME:-crm.localhost}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-123}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
CRM_BRANCH="${CRM_BRANCH:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"

BENCH_DIR="/home/frappe/frappe-bench"

# ---------------------------------------------------------------------------
# Instala o app local "ecomar_crm" no bench.
#
# Obs.: `bench get-app <path-local>` falha nesta versao do bench (ele tenta
# tratar o caminho como um repositorio git). Por isso instalamos "na mao":
# copiando a pasta para apps/, instalando no venv (editavel) e registrando
# em sites/apps.txt.
# ---------------------------------------------------------------------------
instalar_app_ecomar() {
    cd "${BENCH_DIR}"
    if [ ! -d "/workspace/apps/ecomar_crm" ]; then
        echo ">> [aviso] /workspace/apps/ecomar_crm nao encontrado; pulando ecomar_crm."
        return 0
    fi
    echo ">> Instalando o app Ecomar CRM (customizacoes e branding)..."
    rm -rf apps/ecomar_crm
    cp -r /workspace/apps/ecomar_crm apps/ecomar_crm
    ./env/bin/pip install -e apps/ecomar_crm
    # Garante quebra de linha no fim de apps.txt antes de anexar; caso contrario
    # o novo app "gruda" na ultima linha (ex.: crm + ecomar_crm -> crmecomar_crm).
    if [ -f sites/apps.txt ] && [ -n "$(tail -c1 sites/apps.txt 2>/dev/null)" ]; then
        echo >> sites/apps.txt
    fi
    grep -qxF ecomar_crm sites/apps.txt 2>/dev/null || echo ecomar_crm >> sites/apps.txt
}

# ---------------------------------------------------------------------------
# Cria o site e instala os apps (idempotente).
# ---------------------------------------------------------------------------
provisionar_site() {
    cd "${BENCH_DIR}"

    echo ">> Criando o site ${SITE_NAME}..."
    bench new-site "${SITE_NAME}" \
        --force \
        --mariadb-root-password "${DB_ROOT_PASSWORD}" \
        --admin-password "${ADMIN_PASSWORD}" \
        --no-mariadb-socket

    echo ">> Instalando o Frappe CRM no site..."
    bench --site "${SITE_NAME}" install-app crm

    echo ">> Instalando o Ecomar CRM no site..."
    bench --site "${SITE_NAME}" install-app ecomar_crm
    bench build --app ecomar_crm || true

    bench --site "${SITE_NAME}" set-config developer_mode 1
    bench --site "${SITE_NAME}" set-config mute_emails 1
    bench --site "${SITE_NAME}" set-config server_script_enabled 1

    # Site padrao: faz http://localhost:8000 tambem resolver para o site.
    bench set-config -g default_site "${SITE_NAME}"

    bench --site "${SITE_NAME}" clear-cache
    bench use "${SITE_NAME}"
}

cd /home/frappe

# ---------------------------------------------------------------------------
# Bench ja inicializado
# ---------------------------------------------------------------------------
if [ -d "${BENCH_DIR}/apps/frappe" ]; then
    cd "${BENCH_DIR}"
    # Garante que o app ecomar_crm esteja presente/atualizado no bench.
    instalar_app_ecomar

    # Auto-recuperacao: se o site nao existir, provisiona.
    if [ ! -d "${BENCH_DIR}/sites/${SITE_NAME}" ]; then
        echo ">> Bench existe, mas o site ${SITE_NAME} esta ausente. Provisionando..."
        provisionar_site
    else
        echo ">> Bench e site ja existem. Iniciando o Frappe CRM..."
    fi
    exec bench start
fi

# ---------------------------------------------------------------------------
# Primeiro provisionamento (bench novo)
# ---------------------------------------------------------------------------
echo ">> Criando um novo bench (Frappe ${FRAPPE_BRANCH})..."
bench init --skip-redis-config-generation frappe-bench --version "${FRAPPE_BRANCH}"

cd "${BENCH_DIR}"

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

instalar_app_ecomar
provisionar_site

echo ">> Tudo pronto! Iniciando o Frappe CRM..."
exec bench start
