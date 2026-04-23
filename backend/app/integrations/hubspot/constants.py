"""Propiedades solicitadas en POST /crm/objects/2026-03/contacts/search (fijas)."""

CONTACT_SEARCH_PROPERTIES: tuple[str, ...] = (
    "email",
    "is_new_lead",
    "company",
    "firstname",
    "lastname",
    "jobtitle",
    "hs_email_last_email_name",
    "nombre_ultimo_mensaje",
    "ultima_respuesta_de_mensaje",
    "es_contacto_principal",
    "email_disponible",
    "hs_email_last_open_date",
    "hs_email_last_click_date",
    "hs_linkedin_url",
    "website",
    "datos_enriquecidos",
    "address",
    "pais",
    "company_size",
    "campaign_id",
)

# GET /crm/objects/2026-03/calls (listado + asociaciones)
CALL_LIST_PROPERTY_NAMES: tuple[str, ...] = (
    "hs_call_title",
    "hs_call_body",
    "hs_call_to_number",
    "hs_call_from_number",
)

# Propiedades del contacto al enriquecer cada llamada con contacto asociado
CONTACT_PROPERTIES_FOR_CALL_LIST: tuple[str, ...] = (
    "firstname",
    "lastname",
    "call_start_time",
    "call_end_time",
    "estatus_llamada",
)

# GET /crm/objects/2026-03/meetings (listado + asociaciones)
MEETING_LIST_PROPERTY_NAMES: tuple[str, ...] = (
    "hs_meeting_title",
    "hs_meeting_body",
    "hs_internal_meeting_notes",
    "hs_meeting_external_url",
    "hs_meeting_start_time",
    "hs_meeting_end_time",
)

CONTACT_PROPERTIES_FOR_MEETING_LIST: tuple[str, ...] = (
    "firstname",
    "lastname",
)
