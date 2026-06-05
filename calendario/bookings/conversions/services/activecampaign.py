import logging

from django.conf import settings

from calendario.leads.services.activecampaign import ActiveCampaignClient
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)

# Tag IDs por escuela para eventos Schedule (distintos de los tags lead funnel-region)
SCHEDULE_SCHOOL_TAG_MAP = {
    'cb': '460',   # Blocks
    'cf': '464',   # Finance
    'fi': '464',   # Finance
    'cl': '477',   # Languages
}


def push_schedule(reserva):
    """Sync schedule to ActiveCampaign: create/update contact and assign school tag."""
    api_url = getattr(settings, 'ACTIVECAMPAIGN_API_URL', '')
    api_key = getattr(settings, 'ACTIVECAMPAIGN_API_KEY', '')
    if not api_url or not api_key:
        logger.warning('[ActiveCampaign] API not configured')
        return

    s = build_schedule_ctx(reserva)
    if not s.lead_email:
        return

    school_code = s.school_code
    client = ActiveCampaignClient()

    try:
        first_name = None
        if s.lead_name:
            first_name = s.lead_name.split()[0] if s.lead_name.strip() else None

        contact = client.create_or_update_contact(s.lead_email, first_name)
        if not contact:
            logger.warning('[ActiveCampaign] Reserva %s: failed to create/update contact', reserva.pk)
            return

        contact_id = contact.get('id')
        if not contact_id:
            return

        tag_id = SCHEDULE_SCHOOL_TAG_MAP.get(school_code)
        if tag_id:
            client.add_tag(contact_id, tag_id)

        logger.info('[ActiveCampaign] Reserva %s synced, contact_id=%s', reserva.pk, contact_id)

    except Exception as e:
        logger.error('[ActiveCampaign] Reserva %s error: %s', reserva.pk, e)
        raise
