import logging
import time

import requests
from django.conf import settings

from calendario.leads.services.utils import (
    hash_value, hash_phone, get_conversion_value,
    SCHOOL_CUSTOMER_GOOGLE, SCHOOL_CONVERSION_ACTIONS,
)
from calendario.leads.services.google_ads import _get_access_token, _format_datetime
from calendario.leads.models import ConversionLog
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)


def push_schedule(reserva):
    """Send schedule conversion to Google Ads via REST API."""
    s = build_schedule_ctx(reserva)
    school_code = s.school_code
    customer_id = SCHOOL_CUSTOMER_GOOGLE.get(school_code)
    actions = SCHOOL_CONVERSION_ACTIONS.get(school_code)
    if not customer_id or not actions:
        logger.warning('[Google Ads] Reserva %s: unknown school %s', reserva.pk, school_code)
        return

    conversion_action_id = actions.get('llamada-agendada')
    if not conversion_action_id:
        return

    developer_token = getattr(settings, 'GOOGLE_ADS_DEVELOPER_TOKEN', '')
    if not developer_token:
        logger.warning('[Google Ads] GOOGLE_ADS_DEVELOPER_TOKEN not configured')
        return

    access_token = _get_access_token()
    if not access_token:
        logger.error('[Google Ads] Could not obtain access token')
        return

    lead = s.lead
    value = get_conversion_value(s.region, 'schedule')
    order_id = s.event_id or f'sch-{reserva.pk}'

    gclid = getattr(lead, 'gclid', '') or '' if lead else ''
    gbraid = getattr(lead, 'gbraid', '') or '' if lead else ''
    wbraid = getattr(lead, 'wbraid', '') or '' if lead else ''

    conversion = {
        'conversionAction': f'customers/{customer_id}/conversionActions/{conversion_action_id}',
        'orderId': str(order_id),
        'conversionDateTime': _format_datetime(s.call_register or s.created),
        'currencyCode': 'EUR',
        'conversionValue': float(value) if value > 0 else 0.0,
        'consent': {
            'adUserData': 'GRANTED',
            'adPersonalization': 'GRANTED',
        },
    }

    if gclid:
        conversion['gclid'] = gclid
    elif gbraid:
        conversion['gbraid'] = gbraid
    elif wbraid:
        conversion['wbraid'] = wbraid

    user_identifiers = []
    if s.lead_email:
        user_identifiers.append({
            'userIdentifierSource': 'FIRST_PARTY',
            'hashedEmail': hash_value(s.lead_email),
        })
    if s.lead_phone_number:
        ph = hash_phone(s.lead_phone_number)
        if ph:
            user_identifiers.append({
                'userIdentifierSource': 'FIRST_PARTY',
                'hashedPhoneNumber': ph,
            })
    if user_identifiers:
        conversion['userIdentifiers'] = user_identifiers

    login_customer_id = getattr(settings, 'GOOGLE_ADS_LOGIN_CUSTOMER_ID', '')
    url = f'https://googleads.googleapis.com/v19/customers/{customer_id}:uploadClickConversions'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'developer-token': developer_token,
        'Content-Type': 'application/json',
    }
    if login_customer_id:
        headers['login-customer-id'] = login_customer_id

    payload = {
        'conversions': [conversion],
        'partialFailure': True,
    }

    start = time.time()
    log = ConversionLog(
        reserva=reserva,
        lead=lead,
        platform='google_ads',
        event_name='llamada-agendada',
        event_id=order_id,
        school=school_code,
        request_body=payload,
    )

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        elapsed = int((time.time() - start) * 1000)

        log.status_code = resp.status_code
        log.response_body = resp.text[:5000]
        log.execution_time_ms = elapsed
        log.success = resp.status_code == 200
        log.save()

        logger.info('[Google Ads] Reserva %s status=%s (%dms)', reserva.pk, resp.status_code, elapsed)

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error('[Google Ads] Reserva %s error: %s', reserva.pk, e)
        raise
