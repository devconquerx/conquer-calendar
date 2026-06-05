import logging
import time

import requests
from django.conf import settings

from calendario.leads.services.utils import (
    hash_value, hash_phone, get_conversion_value, SCHOOL_PIXEL_META,
)
from calendario.leads.models import ConversionLog
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)

API_VERSION = 'v21.0'


def push_schedule(reserva):
    """Send Schedule event to Meta Conversions API."""
    s = build_schedule_ctx(reserva)
    school_code = s.school_code
    pixel_id = SCHOOL_PIXEL_META.get(school_code)
    if not pixel_id:
        logger.warning('[Meta CAPI] Reserva %s: unknown school %s', reserva.pk, school_code)
        return

    access_token = getattr(settings, 'META_ACCESS_TOKEN', '')
    if not access_token:
        logger.warning('[Meta CAPI] META_ACCESS_TOKEN not configured')
        return

    lead = s.lead
    value = get_conversion_value(s.region, 'schedule')

    user_data = {}
    if s.lead_email:
        user_data['em'] = [hash_value(s.lead_email)]
    if s.lead_name:
        user_data['fn'] = [hash_value(s.lead_name.split()[0])]
    if s.lead_phone_number:
        ph = hash_phone(s.lead_phone_number)
        if ph:
            user_data['ph'] = [ph]

    if lead:
        if lead._fbp:
            user_data['fbp'] = lead._fbp
        if lead._fbc:
            user_data['fbc'] = lead._fbc
        if lead.ip_address:
            user_data['client_ip_address'] = lead.ip_address
        if lead.user_agent:
            user_data['client_user_agent'] = lead.user_agent

    event_time = int(s.call_register.timestamp()) if s.call_register else int(time.time())

    event_data = {
        'event_name': 'Schedule',
        'event_time': event_time,
        'event_id': s.event_id or f'sch-{reserva.pk}',
        'action_source': 'website',
        'user_data': {k: v for k, v in user_data.items() if v},
        'custom_data': {'value': value, 'currency': 'EUR'},
    }
    if s.page_url:
        event_data['event_source_url'] = s.page_url

    payload = {
        'data': [event_data],
        'access_token': access_token,
    }

    url = f'https://graph.facebook.com/{API_VERSION}/{pixel_id}/events'

    start = time.time()
    log = ConversionLog(
        reserva=reserva,
        lead=lead,
        platform='meta',
        event_name='Schedule',
        event_id=event_data['event_id'],
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

        logger.info('[Meta CAPI] Reserva %s status=%s (%dms)', reserva.pk, resp.status_code, elapsed)

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error('[Meta CAPI] Reserva %s error: %s', reserva.pk, e)
        raise
