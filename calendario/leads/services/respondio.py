import logging
import time

import requests
from django.conf import settings

from .utils import get_school_code, get_region_from_lead, SCHOOL_NAMES, SCHOOL_VIDEO_URLS

logger = logging.getLogger(__name__)

API_BASE = 'https://api.respond.io/v2'


def _headers():
    api_key = getattr(settings, 'RESPONDIO_API_KEY', '')
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _ensure_contact(email, first_name=None, phone=None, country_code=None):
    """Check if contact exists, create if not. Returns (identifier, was_created)."""
    hdrs = _headers()

    resp = requests.get(f'{API_BASE}/contact/email:{email}', headers=hdrs, timeout=10)
    if resp.status_code == 200:
        return f'email:{email}', False

    if resp.status_code == 404:
        try:
            data = resp.json()
            primary_id = data.get('primaryId')
            if primary_id:
                return f'id:{primary_id}', False
        except Exception as e:
            logger.warning(f'[Respond.io] Error parsing 404 response for {email}: {e}')

    body = {'email': email, 'language': 'es'}
    if first_name:
        body['firstName'] = first_name
    if phone:
        body['phone'] = phone
    if country_code:
        body['countryCode'] = country_code

    resp = requests.post(f'{API_BASE}/contact/email:{email}', json=body, headers=hdrs, timeout=10)
    if resp.status_code in (200, 201):
        return f'email:{email}', True

    logger.warning(f'[Respond.io] Create contact failed: {resp.status_code} {resp.text[:200]}')
    return None, False


def push_lead(lead):
    """Create/update contact in Respond.io with lead data and tags."""
    api_key = getattr(settings, 'RESPONDIO_API_KEY', '')
    if not api_key:
        logger.warning('[Respond.io] RESPONDIO_API_KEY not configured')
        return

    if not lead.email:
        logger.warning(f'[Respond.io] Lead {lead.pk}: no email, skipping')
        return

    school_code = get_school_code(lead)
    school_name = SCHOOL_NAMES.get(school_code, 'Blocks')
    video_url = SCHOOL_VIDEO_URLS.get(school_code, '')
    region = get_region_from_lead(lead)
    school_abbr = (school_code or 'cb').upper()

    phone = None
    if lead.lead_phone:
        prefix = lead.lead_phone_prefix or ''
        phone = f'{prefix}{lead.lead_phone}'.strip()

    first_name = lead.full_name.split()[0] if lead.full_name else None

    try:
        identifier, was_created = _ensure_contact(
            email=lead.email,
            first_name=first_name,
            phone=phone,
            country_code=lead.country_code,
        )
        if not identifier:
            return

        hdrs = _headers()

        custom_fields = {
            'nombre_lead': lead.full_name or '',
            'nombre_academia': school_name,
            'enlace_video_clase': video_url,
            'pais_lead': lead.lead_country or lead.country_name or '',
        }
        requests.put(
            f'{API_BASE}/contact/{identifier}',
            json={'customFields': custom_fields},
            headers=hdrs,
            timeout=10,
        )

        tags = [region, school_abbr, f'lead-{school_abbr}', 'send-to-respond']
        requests.post(
            f'{API_BASE}/contact/{identifier}/tag',
            json=tags,
            headers=hdrs,
            timeout=10,
        )

        if was_created:
            time.sleep(2)

        logger.info(f'[Respond.io] Lead {lead.pk} synced to {identifier}')

    except Exception as e:
        logger.error(f'[Respond.io] Lead {lead.pk} error: {e}')
        raise
