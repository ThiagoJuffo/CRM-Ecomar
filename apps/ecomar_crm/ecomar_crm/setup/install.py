"""Rotinas executadas na instalacao do app Ecomar CRM.

Aplica o branding da Ecomar (Website Settings) e cria os campos
customizados usados pela Ecomar no Frappe CRM.
"""

import frappe

BRAND_NAME = "Ecomar CRM"
LOGO = "/assets/ecomar_crm/images/ecomar-logo.svg"
FAVICON = "/assets/ecomar_crm/images/ecomar-favicon.svg"


def after_install():
    _aplicar_branding()
    _criar_campos_customizados()
    frappe.db.commit()


def _aplicar_branding():
    """Configura nome, logo e favicon da marca no Website Settings.

    Envolvido em try/except para que uma eventual diferenca de campo entre
    versoes do Frappe nao interrompa a instalacao do app.
    """
    try:
        ws = frappe.get_single("Website Settings")
        campos = {
            "app_name": BRAND_NAME,
            "app_logo": LOGO,
            "banner_image": LOGO,
            "favicon": FAVICON,
            "brand_html": f'<img src="{LOGO}" alt="{BRAND_NAME}" style="height:28px">',
            "copyright": "Ecomar",
        }
        for campo, valor in campos.items():
            if ws.meta.has_field(campo):
                ws.set(campo, valor)
        ws.save(ignore_permissions=True)
        frappe.msgprint("Branding da Ecomar aplicado.", alert=True)
    except Exception:
        frappe.log_error(title="Ecomar CRM: falha ao aplicar branding")


def _criar_campos_customizados():
    """Cria campos customizados da Ecomar no doctype CRM Lead.

    Exemplo de customizacao versionada em codigo. Ajuste/expanda conforme a
    necessidade da Ecomar (adicione outros doctypes e campos ao dicionario).
    """
    if not frappe.db.exists("DocType", "CRM Lead"):
        # CRM ainda nao instalado; nada a fazer.
        return

    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    campos = {
        "CRM Lead": [
            {
                "fieldname": "custom_ecomar_segmento",
                "label": "Segmento (Ecomar)",
                "fieldtype": "Select",
                "options": "\nIndustrial\nComercial\nResidencial\nPublico",
                "insert_after": "source",
            },
        ],
    }
    create_custom_fields(campos, ignore_validate=True)
