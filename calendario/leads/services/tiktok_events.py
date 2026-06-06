import logging
import time

import requests

from .utils import (
    hash_value, hash_phone, get_school_code, get_region_from_lead,
    get_conversion_value, SCHOOL_PIXEL_TIKTOK,
)
from ..models import ConversionLog

logger = logging.getLogger(__name__)

API_URL = 'https://business-api.tiktok.com/open_api/v1.3/event/track/'


def push_lead(lead):
    """Send SubmitForm event to TikTok Events API."""
    school_code = get_school_code(lead)
    config = SCHOOL_PIXEL_TIKTOK.get(school_code)
    if not config:
        logger.warning(f'[TikTok] Lead {lead.pk}: unknown school {school_code}')
        return

    pixel_id, access_token = config
    region = get_region_from_lead(lead)
    value = get_conversion_value(region, 'lead')

    user_data = {}
    if lead.email:
        user_data['email'] = hash_value(lead.email)
    if lead.lead_phone:
        ph = hash_phone(lead.lead_phone, lead.lead_phone_prefix)
        if ph:
            user_data['phone'] = ph
    if lead.ip_address:
        user_data['ip'] = lead.ip_address
    if lead.user_agent:
        user_data['user_agent'] = lead.user_agent
    if lead.ttclid:
        user_data['ttclid'] = lead.ttclid
    if lead._ttp:
        user_data['ttp'] = lead._ttp
    if lead.journey_id:
        user_data['external_id'] = hash_value(lead.journey_id)
    if lead.full_name:
        first_name = lead.full_name.split()[0] if lead.full_name else ''
        user_data['first_name'] = hash_value(first_name)
    if lead.lead_country:
        user_data['country'] = hash_value(lead.lead_country)
    if lead.city:
        user_data['city'] = hash_value(lead.city)

    event_time = int(lead.date_submitted.timestamp()) if lead.date_submitted else int(time.time())

    event_data = {
        'event': 'SubmitForm',
        'event_time': event_time,
        'event_id': lead.event_id or f'lr-{lead.pk}',
        'user': {k: v for k, v in user_data.items() if v},
        'properties': {'value': value, 'currency': 'EUR'},
    }
    if lead.page_url:
        event_data['page'] = {'url': lead.page_url}

    payload = {
        'event_source': 'web',
        'event_source_id': pixel_id,
        'data': [event_data],
    }

    headers = {
        'Access-Token': access_token,
        'Content-Type': 'application/json',
    }

    start = time.time()
    log = ConversionLog(
        lead=lead,
        platform='tiktok',
        event_name='SubmitForm',
        event_id=lead.event_id,
        pixel_id=pixel_id,
        school=school_code,
        request_body=payload,
    )

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        elapsed = int((time.time() - start) * 1000)

        resp_data = resp.json()
        success = resp.status_code == 200 and resp_data.get('code') == 0

        log.status_code = resp.status_code
        log.response_body = resp.text[:2000]
        log.execution_time_ms = elapsed
        log.success = success
        log.save()

        logger.info(f'[TikTok] Lead {lead.pk} status={resp.status_code} code={resp_data.get("code")} ({elapsed}ms)')

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error(f'[TikTok] Lead {lead.pk} error: {e}')
        raise
