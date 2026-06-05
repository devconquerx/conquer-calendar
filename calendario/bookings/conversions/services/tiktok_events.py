import logging
import time

import requests

from calendario.leads.services.utils import (
    hash_value, hash_phone, get_conversion_value, SCHOOL_PIXEL_TIKTOK,
)
from calendario.leads.models import ConversionLog
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)

API_URL = 'https://business-api.tiktok.com/open_api/v1.3/event/track/'


def push_schedule(reserva):
    """Send Schedule event to TikTok Events API."""
    s = build_schedule_ctx(reserva)
    school_code = s.school_code
    config = SCHOOL_PIXEL_TIKTOK.get(school_code)
    if not config:
        logger.warning('[TikTok] Reserva %s: unknown school %s', reserva.pk, school_code)
        return

    pixel_id, access_token = config
    lead = s.lead
    value = get_conversion_value(s.region, 'schedule')

    user_data = {}
    if s.lead_email:
        user_data['email'] = hash_value(s.lead_email)
    if s.lead_phone_number:
        ph = hash_phone(s.lead_phone_number)
        if ph:
            user_data['phone'] = ph
    if s.journey_id:
        user_data['external_id'] = hash_value(s.journey_id)
    if s.lead_name:
        user_data['first_name'] = hash_value(s.lead_name.split()[0])
    if s.lead_country:
        user_data['country'] = hash_value(s.lead_country)

    if lead:
        if lead.ip_address:
            user_data['ip'] = lead.ip_address
        if lead.user_agent:
            user_data['user_agent'] = lead.user_agent
        if lead.ttclid:
            user_data['ttclid'] = lead.ttclid
        if lead._ttp:
            user_data['ttp'] = lead._ttp
        if lead.city:
            user_data['city'] = hash_value(lead.city)

    event_time = int(s.call_register.timestamp()) if s.call_register else int(time.time())

    event_data = {
        'event': 'Schedule',
        'event_time': event_time,
        'event_id': s.event_id or f'sch-{reserva.pk}',
        'user': {k: v for k, v in user_data.items() if v},
        'properties': {'value': value, 'currency': 'EUR'},
    }
    if s.page_url:
        event_data['page'] = {'url': s.page_url}

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
        reserva=reserva,
        lead=lead,
        platform='tiktok',
        event_name='Schedule',
        event_id=event_data['event_id'],
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

        logger.info('[TikTok] Reserva %s status=%s code=%s (%dms)', reserva.pk, resp.status_code, resp_data.get('code'), elapsed)

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error('[TikTok] Reserva %s error: %s', reserva.pk, e)
        raise
