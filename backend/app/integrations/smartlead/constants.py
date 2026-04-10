"""URLs Smartlead; ID efectivo de campaña vía tabla `campaign_active` (`get_effective_smartlead_campaign_id`)."""

SMARTLEAD_API_V1_BASE = "https://server.smartlead.ai/api/v1"
SMARTLEAD_DEFAULT_CAMPAIGN_ID = "3154960"

SMARTLEAD_MAX_LEADS_PER_REQUEST = 400

DEFAULT_ADD_LEAD_SETTINGS: dict[str, bool] = {
    "ignore_global_block_list": False,
    "ignore_unsubscribe_list": False,
    "ignore_community_bounce_list": False,
    "ignore_duplicate_leads_in_other_campaign": True,
    "return_lead_ids": True,
}
