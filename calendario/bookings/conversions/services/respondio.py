import logging
import time

import requests
from django.conf import settings

from calendario.leads.services.utils import SCHOOL_NAMES, SCHOOL_VIDEO_URLS
from calendario.leads.services.respondio import _headers, _ensure_contact
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)

API_BASE = 'https://api.respond.io/v2'

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


def push_schedule(reserva):
    """Send schedule data to Respond.io: ensure contact, set custom fields, add tags."""
    api_key = getattr(settings, 'RESPONDIO_API_KEY', '')
    if not api_key:
        logger.warning('[Respond.io] RESPONDIO_API_KEY not configured')
        return

    s = build_schedule_ctx(reserva)
    email = s.lead_email
    if not email:
        logger.warning('[Respond.io] Reserva %s: no email, skipping', reserva.pk)
        return

    if s.confirmation in (4, 7, 9):
        logger.info('[Respond.io] Reserva %s: skipped (confirmation=%s)', reserva.pk, s.confirmation)
        return

    school_code = s.school_code
    school_name = SCHOOL_NAMES.get(school_code, '')
    school_abbr = (school_code or '').upper()
    video_url = SCHOOL_VIDEO_URLS.get(school_code, '')

    call_date = ''
    call_time = ''
    if s.call_datetime:
        dia = s.call_datetime.day
        mes = MESES_ES.get(s.call_datetime.month, '')
        call_date = f'{dia} de {mes}'
        call_time = s.call_datetime.strftime('%H:%M')

    first_name = s.lead_name.split()[0] if s.lead_name and s.lead_name.strip() else ''

    try:
        identifier, was_created = _ensure_contact(
            email=email,
            first_name=first_name or None,
            phone=s.lead_phone_number,
            country_code=s.lead_country,
        )
        if not identifier:
            return

        hdrs = _headers()

        custom_fields = {
            'nombre_lead': s.lead_name or '',
            'nombre_setter': s.setter or '',
            'nombre_closer': s.closer or '',
            'nombre_academia': school_name,
            'fecha_llamada': call_date,
            'hora_llamada_eu': call_time,
            'pais_lead': s.lead_country or '',
            'meet_url': s.meet_join_url or '',
            'enlace_video_clase': video_url,
        }

        payload = {
            'firstName': first_name,
            'custom_fields': [
                {'name': k, 'value': v} for k, v in custom_fields.items()
            ],
        }

        resp = requests.put(
            f'{API_BASE}/contact/{identifier}',
            json=payload,
            headers=hdrs,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            logger.warning('[Respond.io] Reserva %s: update failed %s %s', reserva.pk, resp.status_code, resp.text[:200])
            return

        tags = ['send-to-respond']
        if school_abbr:
            tags.append(f'schedule-{school_abbr}')

        requests.post(
            f'{API_BASE}/contact/{identifier}/tag',
            json=tags,
            headers=hdrs,
            timeout=10,
        )

        if was_created:
            time.sleep(2)

        logger.info('[Respond.io] Reserva %s synced to %s', reserva.pk, identifier)

    except Exception as e:
        logger.error('[Respond.io] Reserva %s error: %s', reserva.pk, e)
        raise
