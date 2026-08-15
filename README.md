# CRM Ecomar

CRM da **Ecomar** baseado no [Frappe CRM](https://github.com/frappe/crm) — um CRM
open-source completo (gestão de leads, negócios/deals, funil kanban, e-mail,
tarefas, notas e telefonia) construído sobre o
[Frappe Framework](https://frappeframework.com/).

Este repositório traz tudo pronto para **subir o CRM localmente com Docker**,
para desenvolvimento e avaliação.

---

## 📋 Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose](https://docs.docker.com/compose/) (já vem no Docker Desktop)
- Cerca de 4 GB de RAM livre e conexão com a internet (a primeira instalação
  baixa as imagens e o código do Frappe/CRM)

Para conferir se está tudo certo:

```bash
docker --version
docker compose version
```

---

## 🚀 Como subir (passo a passo)

```bash
# 1. Clone o repositório e entre na pasta
git clone https://github.com/thiagojuffo/crm-ecomar.git
cd crm-ecomar

# 2. Suba o CRM
./scripts/start.sh
```

Na **primeira execução**, a instalação leva **alguns minutos** (baixa o Frappe,
o app CRM e cria o banco de dados). Acompanhe o progresso com:

```bash
./scripts/logs.sh
```

Quando os logs mostrarem os serviços rodando, acesse:

- **URL:** http://localhost:8000
- **Usuário:** `Administrator`
- **Senha:** `admin` (ou o valor de `ADMIN_PASSWORD` no seu `.env`)

> 💡 Se preferir usar o Docker Compose diretamente, é só rodar
> `docker compose up -d` — o `start.sh` é apenas um atalho que também cria o
> `.env` a partir do exemplo.

---

## ⚙️ Configuração

As configurações ficam no arquivo `.env` (criado automaticamente a partir de
`.env.example` no primeiro `start.sh`). Você pode editá-lo antes de subir:

| Variável           | Padrão          | Descrição                                             |
| ------------------ | --------------- | ----------------------------------------------------- |
| `SITE_NAME`        | `crm.localhost` | Nome/domínio local do site                            |
| `DB_ROOT_PASSWORD` | `123`           | Senha do root do MariaDB (**troque fora do local**)   |
| `ADMIN_PASSWORD`   | `admin`         | Senha do usuário `Administrator` do CRM               |
| `WEB_PORT`         | `8000`          | Porta de acesso ao CRM no navegador                   |
| `SOCKETIO_PORT`    | `9000`          | Porta do socket.io (notificações em tempo real)       |
| `CRM_BRANCH`       | `main`          | Branch do app Frappe CRM                              |
| `FRAPPE_BRANCH`    | `version-15`    | Versão do Frappe Framework                            |

> ⚠️ O arquivo `.env` **não** é versionado (está no `.gitignore`), pois contém
> senhas. Ajuste-o localmente conforme a necessidade.

---

## 🧰 Comandos úteis

| Ação                                   | Comando                              |
| -------------------------------------- | ------------------------------------ |
| Subir o CRM                            | `./scripts/start.sh`                 |
| Ver os logs (instalação/execução)      | `./scripts/logs.sh`                  |
| Parar (mantém os dados)                | `./scripts/stop.sh`                  |
| Zerar tudo e reinstalar (apaga dados)  | `./scripts/reset.sh`                 |
| Abrir um terminal no container         | `docker compose exec frappe bash`    |

Rodando comandos do `bench` dentro do container:

```bash
docker compose exec frappe bash
cd frappe-bench
bench --site crm.localhost list-apps      # lista os apps instalados
bench --site crm.localhost migrate        # aplica migrações
bench --site crm.localhost console        # console Python do Frappe
```

---

## 💾 Persistência de dados

Os dados ficam em **volumes Docker**, então sobrevivem a `stop`/`start`:

- `mariadb-data` → banco de dados (MariaDB)
- `frappe-bench` → o bench do Frappe (código, site e configs)

- `./scripts/stop.sh` (ou `docker compose down`) **preserva** os dados.
- `./scripts/reset.sh` (ou `docker compose down -v`) **apaga** os dados e
  permite reinstalar do zero.

---

## 🏗️ Estrutura do repositório

```
crm-ecomar/
├── docker-compose.yml     # Serviços: mariadb, redis e frappe (CRM)
├── docker/
│   └── init.sh            # Provisiona o bench e instala o Frappe CRM
├── scripts/
│   ├── start.sh           # Sobe o CRM
│   ├── stop.sh            # Para (preserva dados)
│   ├── logs.sh            # Acompanha os logs
│   └── reset.sh           # Zera tudo (apaga dados)
├── .env.example           # Modelo de configuração
├── .gitignore
└── README.md
```

---

## 🗺️ Próximos passos

Este setup é focado em **desenvolvimento/avaliação local**. Para evoluir:

- **Customizações da Ecomar:** criar um app Frappe próprio (ex.: `ecomar_crm`)
  com doctypes, campos e automações específicas, instalado por cima do CRM.
- **Produção:** publicar em um servidor/VPS com HTTPS (Traefik ou Nginx) e
  senhas fortes, ou usar o [Frappe Cloud](https://frappecloud.com/) (hospedagem
  gerenciada oficial).
- **Branding:** logo, cores e domínio da Ecomar.

Abra uma issue ou fale com o time para priorizarmos esses passos.

---

## 📚 Referências

- [Frappe CRM (GitHub)](https://github.com/frappe/crm)
- [Documentação do Frappe CRM](https://docs.frappe.io/crm)
- [Frappe Framework](https://frappeframework.com/)
