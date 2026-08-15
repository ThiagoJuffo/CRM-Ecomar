# Ecomar CRM

App Frappe com as **customizações e o branding da Ecomar**, instalado por cima
do [Frappe CRM](https://github.com/frappe/crm).

> Mantenha as regras de negócio da Ecomar **aqui**, neste app — nunca editando
> o código do `crm` ou do `frappe` diretamente. Assim é possível atualizar o
> Frappe CRM sem perder as customizações.

## O que este app faz

Na instalação (`after_install`), de forma **idempotente**, o app aplica toda a
configuração inicial do CRM da Ecomar:

- **Branding:** nome, logo, favicon e cores da Ecomar (via `Website Settings` +
  CSS de marca no desk).
- **Locale do Brasil:** moeda **BRL**, idioma **pt-BR**, fuso **America/Sao_Paulo**,
  formato de data `dd/mm/aaaa` e de número `#.###,##`.
- **Origens de lead** (`CRM Lead Source`): Site, Indicação, WhatsApp, Instagram,
  Facebook, Google, Telefone, Feira/Evento, Parceiro, Marketing.
- **Funil de vendas solar:**
  - Status de **Lead**: Novo → Em Contato → Qualificado → Não Qualificado.
  - Status de **Deal**: Qualificação → Visita Técnica → Proposta Enviada →
    Negociação → Fechado (Ganho / Perdido), com probabilidades e cores.
- **Campos de energia solar** (no `CRM Lead` e no `CRM Deal`): Tipo de
  Instalação, Potência Estimada (kWp), Consumo Médio (kWh), Valor Médio da Conta
  (R$), Concessionária, Tipo de Telhado e Fase da Rede.

> Reaplicar a configuração a qualquer momento:
> ```bash
> bench --site crm.localhost execute ecomar_crm.setup.install.after_install
> ```

## Estrutura

```
ecomar_crm/
├── pyproject.toml
└── ecomar_crm/
    ├── hooks.py                 # branding + registro do after_install
    ├── modules.txt             # módulo "Ecomar CRM"
    ├── patches.txt
    ├── setup/
    │   └── install.py          # branding, locale, origens, funil e campos solar
    └── public/
        ├── css/ecomar_branding.css
        └── images/ecomar-logo.svg, ecomar-favicon.svg
```

## Instalação

No ambiente Docker deste repositório o app é instalado **automaticamente** pelo
`docker/init.sh` (junto com o `crm`). Para instalar manualmente num bench
existente:

```bash
bench get-app ecomar_crm /caminho/para/apps/ecomar_crm
bench --site crm.localhost install-app ecomar_crm
bench build --app ecomar_crm
bench --site crm.localhost clear-cache
```

## Branding: trocar pelos assets oficiais da Ecomar

1. Substitua os arquivos (mantendo os nomes):
   - `ecomar_crm/public/images/ecomar-logo.svg`
   - `ecomar_crm/public/images/ecomar-favicon.svg`
2. Ajuste as cores em `ecomar_crm/public/css/ecomar_branding.css`
   (variáveis `--ecomar-*` no topo do arquivo).
3. Rode:
   ```bash
   bench build --app ecomar_crm
   bench --site crm.localhost clear-cache
   ```

> As cores já usam o **verde oficial da Ecomar** (`--ecomar-primary: #1e9e1e`).
> O logo/favicon são uma **recriação vetorial** fiel ao conceito da marca
> (folha + casa com painel solar) — para ficar pixel-perfect, substitua os SVGs
> pelos arquivos oficiais (mesmo nome) e rode o build.

## Adicionar novas customizações

- **Campos customizados:** adicione ao dicionário em
  `setup/install.py` (`_criar_campos_customizados`). Para campos criados pela
  interface, exporte com `bench --site <site> export-fixtures` e ative o bloco
  `fixtures` em `hooks.py`.
- **Automação (server scripts / eventos):** use `doc_events` em `hooks.py`.
- **Novos doctypes da Ecomar:** `bench --site <site> new-doctype`, deixando o
  módulo como *Ecomar CRM*.
