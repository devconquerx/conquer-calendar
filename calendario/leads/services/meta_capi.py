import logging
import time

import requests
from django.conf import settings

from .utils import (
    hash_value, hash_phone, get_school_code, get_region_from_lead,
    get_conversion_value, SCHOOL_PIXEL_META,
)
from ..models import ConversionLog

logger = logging.getLogger(__name__)

API_VERSION = 'v21.0'


def push_lead(lead):
    """Send Lead event to Meta Conversions API."""
    school_code = get_school_code(lead)
    pixel_id = SCHOOL_PIXEL_META.get(school_code)
    if not pixel_id:
        logger.warning(f'[Meta CAPI] Lead {lead.pk}: unknown school {school_code}')
        return

    access_token = getattr(settings, 'META_ACCESS_TOKEN', '')
    if not access_token:
        logger.warning('[Meta CAPI] META_ACCESS_TOKEN not configured')
        return

    region = get_region_from_lead(lead)
    value = get_conversion_value(region, 'lead')

    user_data = {}
    if lead.email:
        user_data['em'] = [hash_value(lead.email)]
    if lead.full_name:
        user_data['fn'] = [hash_value(lead.full_name.split()[0] if lead.full_name else '')]
    if lead.lead_phone:
        ph = hash_phone(lead.lead_phone, lead.lead_phone_prefix)
        if ph:
            user_data['ph'] = [ph]
    if lead._fbp:
        user_data['fbp'] = lead._fbp
    if lead._fbc:
        user_data['fbc'] = lead._fbc
    if lead.ip_address:
        user_data['client_ip_address'] = lead.ip_address
    if lead.user_agent:
        user_data['client_user_agent'] = lead.user_agent

    event_time = int(lead.date_submitted.timestamp()) if lead.date_submitted else int(time.time())

    event_data = {
        'event_name': 'Lead',
        'event_time': event_time,
        'event_id': lead.event_id or f'lr-{lead.pk}',
        'action_source': 'website',
        'user_data': {k: v for k, v in user_data.items() if v},
        'custom_data': {'value': value, 'currency': 'EUR'},
    }
    if lead.page_url:
        event_data['event_source_url'] = lead.page_url

    payload = {
        'data': [event_data],
        'access_token': access_token,
    }

    url = f'https://graph.facebook.com/{API_VERSION}/{pixel_id}/events'

    start = time.time()
    log = ConversionLog(
        lead=lead,
        platform='meta',
        event_name='Lead',
        event_id=lead.event_id,
        pixel_id=pixel_id,
        school=school_code,
        request_body=payload,
    )

    try:
        resp = requests.post(url, json=payload, timeout=15)
        elapsed = int((time.time() - start) * 1000)

        log.status_code = resp.status_code
        log.response_body = resp.text[:2000]
        log.execution_time_ms = elapsed
        log.success = resp.status_code == 200
        log.save()

        logger.info(f'[Meta CAPI] Lead {lead.pk} status={resp.status_code} ({elapsed}ms)')

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error(f'[Meta CAPI] Lead {lead.pk} error: {e}')
        raise
