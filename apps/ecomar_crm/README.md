# Ecomar CRM

App Frappe com as **customizações e o branding da Ecomar**, instalado por cima
do [Frappe CRM](https://github.com/frappe/crm).

> Mantenha as regras de negócio da Ecomar **aqui**, neste app — nunca editando
> o código do `crm` ou do `frappe` diretamente. Assim é possível atualizar o
> Frappe CRM sem perder as customizações.

## O que este app faz

- **Branding:** aplica nome, logo, favicon e cores da Ecomar (via
  `Website Settings` + CSS de marca no desk do Frappe).
- **Campos customizados:** cria, na instalação, o campo
  `Segmento (Ecomar)` no doctype `CRM Lead` (exemplo do padrão a seguir).

## Estrutura

```
ecomar_crm/
├── pyproject.toml
└── ecomar_crm/
    ├── hooks.py                 # branding + registro do after_install
    ├── modules.txt             # módulo "Ecomar CRM"
    ├── patches.txt
    ├── setup/
    │   └── install.py          # aplica branding e cria campos customizados
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

> As cores e o logo atuais são **placeholders** (paleta eco-marinha). É só
> trocar pela identidade oficial.

## Adicionar novas customizações

- **Campos customizados:** adicione ao dicionário em
  `setup/install.py` (`_criar_campos_customizados`). Para campos criados pela
  interface, exporte com `bench --site <site> export-fixtures` e ative o bloco
  `fixtures` em `hooks.py`.
- **Automação (server scripts / eventos):** use `doc_events` em `hooks.py`.
- **Novos doctypes da Ecomar:** `bench --site <site> new-doctype`, deixando o
  módulo como *Ecomar CRM*.
