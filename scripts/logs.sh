#!/bin/bash
# Acompanha os logs do container do Frappe (util para ver a instalacao inicial).
set -e

cd "$(dirname "$0")/.."

docker compose logs -f frappe
