import logging
import time
from datetime import datetime

import requests
from django.conf import settings

from .utils import (
    hash_value, hash_phone, get_school_code, get_region_from_lead,
    get_conversion_value, SCHOOL_CUSTOMER_GOOGLE, SCHOOL_CONVERSION_ACTIONS,
)
from ..models import ConversionLog

logger = logging.getLogger(__name__)


def push_lead(lead):
    """Send lead registration conversion to Google Ads via REST API."""
    school_code = get_school_code(lead)
    customer_id = SCHOOL_CUSTOMER_GOOGLE.get(school_code)
    actions = SCHOOL_CONVERSION_ACTIONS.get(school_code)
    if not customer_id or not actions:
        logger.warning(f'[Google Ads] Lead {lead.pk}: unknown school {school_code}')
        return

    conversion_action_id = actions.get('registro-lead')
    if not conversion_action_id:
        return

    developer_token = getattr(settings, 'GOOGLE_ADS_DEVELOPER_TOKEN', '')
    if not developer_token:
        logger.warning('[Google Ads] GOOGLE_ADS_DEVELOPER_TOKEN not configured')
        return

    access_token = _get_access_token()

    region = get_region_from_lead(lead)
    value = get_conversion_value(region, 'lead')
    order_id = lead.event_id or f'lr-{lead.pk}'

    gclid = lead.gclid or ''
    gbraid = lead.gbraid or ''
    wbraid = lead.wbraid or ''

    conversion = {
        'conversionAction': f'customers/{customer_id}/conversionActions/{conversion_action_id}',
        'orderId': str(order_id),
        'conversionDateTime': _format_datetime(lead.date_submitted or lead.created),
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
    if lead.email:
        user_identifiers.append({
            'userIdentifierSource': 'FIRST_PARTY',
            'hashedEmail': hash_value(lead.email),
        })
    if lead.lead_phone:
        ph = hash_phone(lead.lead_phone, lead.lead_phone_prefix)
        if ph:
            user_identifiers.append({
                'userIdentifierSource': 'FIRST_PARTY',
                'hashedPhoneNumber': ph,
            })
    if user_identifiers:
        conversion['userIdentifiers'] = user_identifiers

    login_customer_id = getattr(settings, 'GOOGLE_ADS_LOGIN_CUSTOMER_ID', '')
    url = f'https://googleads.googleapis.com/v24/customers/{customer_id}:uploadClickConversions'
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
        lead=lead,
        platform='google_ads',
        event_name='registro-lead',
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

        logger.info(f'[Google Ads] Lead {lead.pk} status={resp.status_code} ({elapsed}ms)')

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error_message = str(e)[:2000]
        log.execution_time_ms = elapsed
        log.save()
        logger.error(f'[Google Ads] Lead {lead.pk} error: {e}')
        raise


def _get_access_token():
    """Exchange refresh token for access token via Google OAuth2."""
    client_id = getattr(settings, 'GOOGLE_ADS_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_ADS_CLIENT_SECRET', '')
    refresh_token = getattr(settings, 'GOOGLE_ADS_REFRESH_TOKEN', '')

    if not all([client_id, client_secret, refresh_token]):
        return None

    try:
        resp = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }, timeout=10)
        return resp.json().get('access_token')
    except Exception as e:
        logger.error(f'[Google Ads] OAuth error: {e}')
        raise


def _format_datetime(dt):
    """Format datetime for Google Ads API (yyyy-mm-dd hh:mm:ss+hh:mm).

    OJO: %z de strftime emite el offset SIN dos puntos (+0000) y la API lo
    rechaza (INVALID_STRING_DATE_TIME_SECONDS_WITH_OFFSET): hay que insertar
    el ':' a mano. Datetimes naive → se asume UTC.
    """
    if not dt:
        dt = datetime.now()
    s = dt.strftime('%Y-%m-%d %H:%M:%S%z')
    if len(s) >= 5 and s[-5] in '+-':
        return s[:-2] + ':' + s[-2:]
    return s + '+00:00'
