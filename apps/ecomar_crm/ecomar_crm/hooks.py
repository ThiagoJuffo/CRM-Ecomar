app_name = "ecomar_crm"
app_title = "Ecomar CRM"
app_publisher = "Ecomar"
app_description = "Customizacoes e branding da Ecomar sobre o Frappe CRM"
app_email = "thiago@ecomareng.com"
app_license = "mit"

# O Frappe CRM precisa estar instalado antes deste app.
required_apps = ["frappe/crm"]

# ---------------------------------------------------------------------------
# Branding (Ecomar)
# ---------------------------------------------------------------------------
# Logo exibido na barra de navegacao e na tela de login do Frappe.
app_logo_url = "/assets/ecomar_crm/images/ecomar-logo.svg"

# CSS de marca (cores da Ecomar) aplicado no desk do Frappe.
app_include_css = "/assets/ecomar_crm/css/ecomar_branding.css"

# Favicon e imagem de destaque no site/login.
website_context = {
    "favicon": "/assets/ecomar_crm/images/ecomar-favicon.svg",
    "splash_image": "/assets/ecomar_crm/images/ecomar-logo.svg",
}

# ---------------------------------------------------------------------------
# Ciclo de vida da instalacao
# ---------------------------------------------------------------------------
# Ao instalar o app: aplica o branding (Website Settings) e cria os campos
# customizados da Ecomar no CRM.
after_install = "ecomar_crm.setup.install.after_install"

# ---------------------------------------------------------------------------
# Fixtures (exportar/versionar customizacoes feitas pela interface)
# ---------------------------------------------------------------------------
# Descomente e rode `bench --site <site> export-fixtures` para versionar, por
# exemplo, os campos customizados criados na interface:
#
# fixtures = [
#     {
#         "dt": "Custom Field",
#         "filters": [["fieldname", "like", "custom_ecomar_%"]],
#     },
# ]
