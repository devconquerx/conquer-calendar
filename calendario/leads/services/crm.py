import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Lead.school (slug interno del calendario) → código de escuela del CRM, el
# vocabulario que guardaba el funnel viejo en LeadRegister.school. OJO finance:
# el CRM usa 'fi' (SCHOOL_TAGS/SCHOOL_PIXEL_MAP indexan por 'fi'); con el slug
# largo su Meta CAPI/TikTok/Ads de paridad daban SKIP (pixel_id=None). La
# traducción vive SOLO aquí: internamente el calendario sigue con el slug (los
# tags de Respond.io derivan 'CF' de él y no deben cambiar).
_SCHOOL_CRM_CODE = {
    'conquer-blocks': 'cb', 'conquerblocks': 'cb', 'conquer-blocks-esp': 'cb',
    'conquer-finance': 'fi', 'conquerfinance': 'fi', 'cf': 'fi',
    'conquer-languages': 'cl', 'conquerlanguages': 'cl',
    'conquer-legal': 'cg', 'conquerlegal': 'cg',
}


def push_lead(lead):
    """Send lead data to the CRM ingest API after NeverBounce validation."""
    base_url = settings.CRM_BASE_URL.rstrip('/')
    url = f'{base_url}/api/v1/ingest/lead-register/'
    api_key = settings.CRM_API_KEY

    if not api_key:
        logger.warning('[CRM] No API key configured, skipping lead %s', lead.pk)
        return

    payload = {
        'email': lead.email,
        'full_name': lead.full_name,
        'last_name': lead.last_name,
        'lead_phone': lead.lead_phone,
        'lead_phone_prefix': lead.lead_phone_prefix,
        'lead_country': lead.lead_country,
        'date_submitted': lead.date_submitted.isoformat() if lead.date_submitted else None,
        'ip_address': lead.ip_address,
        'page_url': lead.page_url,
        'funnel': lead.funnel,
        'school': _SCHOOL_CRM_CODE.get((lead.school or '').lower().strip(), lead.school),
        'product': lead.product,
        'conditions': lead.conditions,
        # UTMs
        'utm_source': lead.utm_source,
        'utm_campaign': lead.utm_campaign,
        'utm_medium': lead.utm_medium,
        'utm_content': lead.utm_content,
        'utm_term': lead.utm_term,
        'utm_idcampaign': lead.utm_idcampaign,
        'utm_adsetid': lead.utm_adsetid,
        'utm_adid': lead.utm_adid,
        'utm_form_variant': lead.utm_form_variant,
        'utm_title': lead.utm_title,
        'utm_vsl': lead.utm_vsl,
        # Click IDs
        'gclid': lead.gclid,
        'gbraid': lead.gbraid,
        'wbraid': lead.wbraid,
        'fbclid': lead.fbclid,
        'msclkid': lead.msclkid,
        'dclid': lead.dclid,
        'ttclid': lead.ttclid,
        'gclsrc': lead.gclsrc,
        # Cookies de píxel (advanced matching del CAPI de paridad del CRM; el
        # funnel viejo las mandaba y el ingest ya las acepta)
        '_fbp': lead._fbp,
        '_fbc': lead._fbc,
        '_ttp': lead._ttp,
        '_ga': lead._ga,
        '_gid': lead._gid,
        # Tracking
        'event_id': lead.event_id,
        'journey_id': lead.journey_id,
        'recaptcha_score': float(lead.recaptcha_score) if lead.recaptcha_score is not None else None,
        'user_agent': lead.user_agent,
        # Geo
        'country_code': lead.country_code,
        'country_name': lead.country_name,
        'city': lead.city,
        'is_proxy': lead.is_proxy,
        # NeverBounce result
        'neverbounce_result': lead.neverbounce_result,
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    start = time.time()
    response = requests.post(
        url,
        json=payload,
        headers={
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
        },
        timeout=15,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    if response.status_code in (200, 201):
        logger.info(
            '[CRM] Lead %s sent successfully (%dms) — response: %s',
            lead.pk, elapsed_ms, response.text[:200],
        )
    else:
        logger.error(
            '[CRM] Lead %s failed (%dms) — status=%d response=%s',
            lead.pk, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()
