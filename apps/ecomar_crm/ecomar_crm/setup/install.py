"""Configuracao inicial do CRM da Ecomar.

Executado no `after_install` do app. Aplica, de forma idempotente:

  1. Branding da Ecomar (Website Settings).
  2. Locale do Brasil (moeda BRL, idioma pt-BR, fuso de Sao Paulo).
  3. Origens de lead (CRM Lead Source).
  4. Funil de vendas solar (status de Lead e de Deal, em portugues).
  5. Campos de energia solar no Lead e no Deal.

Tudo pode ser reaplicado a qualquer momento com:
    bench --site <site> execute ecomar_crm.setup.install.after_install
"""

import frappe

BRAND_NAME = "Ecomar Engenharia"
LOGO = "/assets/ecomar_crm/images/ecomar-logo.svg"
FAVICON = "/assets/ecomar_crm/images/ecomar-favicon.svg"


def after_install():
    _aplicar_branding()
    _configurar_locale_brasil()
    _criar_origens_lead()
    _criar_status_lead()
    _criar_status_deal()
    _criar_campos_energia_solar()
    frappe.db.commit()


# ---------------------------------------------------------------------------
# 1. Branding
# ---------------------------------------------------------------------------
def _aplicar_branding():
    try:
        ws = frappe.get_single("Website Settings")
        campos = {
            "app_name": BRAND_NAME,
            "app_logo": LOGO,
            "banner_image": LOGO,
            "favicon": FAVICON,
            "brand_html": f'<img src="{LOGO}" alt="{BRAND_NAME}" style="height:28px">',
            "copyright": "Ecomar Engenharia",
        }
        for campo, valor in campos.items():
            if ws.meta.has_field(campo):
                ws.set(campo, valor)
        ws.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="Ecomar CRM: falha ao aplicar branding")


# ---------------------------------------------------------------------------
# 2. Locale do Brasil
# ---------------------------------------------------------------------------
def _configurar_locale_brasil():
    try:
        ss = frappe.get_single("System Settings")
        preferidos = {
            "country": "Brazil",
            "time_zone": "America/Sao_Paulo",
            "language": "pt-BR",
            "date_format": "dd/mm/yyyy",
            "time_format": "HH:mm:ss",
            "number_format": "#.###,##",
            "first_day_of_the_week": "Monday",
        }
        for campo, valor in preferidos.items():
            if ss.meta.has_field(campo):
                ss.set(campo, valor)
        ss.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="Ecomar CRM: falha ao configurar System Settings")

    # Moeda padrao BRL (Global Defaults)
    try:
        gd = frappe.get_single("Global Defaults")
        if gd.meta.has_field("default_currency"):
            gd.default_currency = "BRL"
        if gd.meta.has_field("country"):
            gd.country = "Brazil"
        gd.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="Ecomar CRM: falha ao definir moeda padrao")


# ---------------------------------------------------------------------------
# 3. Origens de lead
# ---------------------------------------------------------------------------
def _criar_origens_lead():
    origens = [
        "Site",
        "Indicacao",
        "WhatsApp",
        "Instagram",
        "Facebook",
        "Google",
        "Telefone",
        "Feira / Evento",
        "Parceiro",
        "Marketing",
    ]
    for nome in origens:
        _garantir_registro("CRM Lead Source", {"source_name": nome})


# ---------------------------------------------------------------------------
# 4. Funil de vendas (status)
# ---------------------------------------------------------------------------
def _criar_status_lead():
    # (nome, tipo, cor, posicao)
    status = [
        ("Novo", "Open", "blue", 1),
        ("Em Contato", "Ongoing", "orange", 2),
        ("Qualificado", "Ongoing", "teal", 3),
        ("Nao Qualificado", "Lost", "gray", 4),
    ]
    for nome, tipo, cor, pos in status:
        _garantir_registro(
            "CRM Lead Status",
            {"lead_status": nome},
            {"type": tipo, "color": cor, "position": pos},
        )


def _criar_status_deal():
    # Funil de vendas de energia solar (nome, tipo, cor, probabilidade, posicao)
    status = [
        ("Qualificacao", "Open", "blue", 10, 1),
        ("Visita Tecnica", "Ongoing", "cyan", 25, 2),
        ("Proposta Enviada", "Ongoing", "amber", 50, 3),
        ("Negociacao", "Ongoing", "violet", 75, 4),
        ("Fechado - Ganho", "Won", "green", 100, 5),
        ("Fechado - Perdido", "Lost", "red", 0, 6),
    ]
    for nome, tipo, cor, prob, pos in status:
        _garantir_registro(
            "CRM Deal Status",
            {"deal_status": nome},
            {"type": tipo, "color": cor, "probability": prob, "position": pos},
        )


# ---------------------------------------------------------------------------
# 5. Campos de energia solar (CRM Lead e CRM Deal)
# ---------------------------------------------------------------------------
def _campos_solar(insert_after):
    """Retorna a lista de campos de energia solar, ancorada em `insert_after`."""
    return [
        {
            "fieldname": "custom_secao_energia_solar",
            "label": "Dados de Energia Solar",
            "fieldtype": "Section Break",
            "insert_after": insert_after,
            "collapsible": 1,
        },
        {
            "fieldname": "custom_tipo_instalacao",
            "label": "Tipo de Instalacao",
            "fieldtype": "Select",
            "options": "\nResidencial\nComercial\nIndustrial\nRural\nPublico",
            "insert_after": "custom_secao_energia_solar",
        },
        {
            "fieldname": "custom_potencia_kwp",
            "label": "Potencia Estimada (kWp)",
            "fieldtype": "Float",
            "insert_after": "custom_tipo_instalacao",
        },
        {
            "fieldname": "custom_consumo_medio_kwh",
            "label": "Consumo Medio Mensal (kWh)",
            "fieldtype": "Float",
            "insert_after": "custom_potencia_kwp",
        },
        {
            "fieldname": "custom_valor_conta",
            "label": "Valor Medio da Conta (R$)",
            "fieldtype": "Currency",
            "insert_after": "custom_consumo_medio_kwh",
        },
        {
            "fieldname": "custom_coluna_solar",
            "fieldtype": "Column Break",
            "insert_after": "custom_valor_conta",
        },
        {
            "fieldname": "custom_concessionaria",
            "label": "Concessionaria",
            "fieldtype": "Data",
            "insert_after": "custom_coluna_solar",
        },
        {
            "fieldname": "custom_tipo_telhado",
            "label": "Tipo de Telhado",
            "fieldtype": "Select",
            "options": "\nCeramico\nFibrocimento\nMetalico\nLaje\nSolo\nOutro",
            "insert_after": "custom_concessionaria",
        },
        {
            "fieldname": "custom_fase_rede",
            "label": "Fase da Rede",
            "fieldtype": "Select",
            "options": "\nMonofasico\nBifasico\nTrifasico",
            "insert_after": "custom_tipo_telhado",
        },
    ]

    # (nota) fieldnames iguais no Lead e no Deal facilitam o mapeamento de dados.


def _criar_campos_energia_solar():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    campos = {}
    if frappe.db.exists("DocType", "CRM Lead"):
        campos["CRM Lead"] = _campos_solar(insert_after="source")
    if frappe.db.exists("DocType", "CRM Deal"):
        campos["CRM Deal"] = _campos_solar(insert_after="industry")

    if campos:
        create_custom_fields(campos, ignore_validate=True)


# ---------------------------------------------------------------------------
# Utilitario
# ---------------------------------------------------------------------------
def _garantir_registro(doctype, chave, extras=None):
    """Cria o registro se ainda nao existir (idempotente)."""
    try:
        if frappe.db.exists(doctype, chave):
            return
        doc = frappe.new_doc(doctype)
        doc.update(chave)
        if extras:
            doc.update(extras)
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title=f"Ecomar CRM: falha ao criar {doctype} {chave}")
