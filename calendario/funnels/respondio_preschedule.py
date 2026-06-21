"""Asignación de etiquetas de pre-schedule en Respond.io para la Prellamada.

En conquer-calendar la `Prellamada` es el equivalente del PreSchedule del CRM.
Aquí solo replicamos las etiquetas de WhatsApp que el CRM ponía vía
`send_preschedule_to_respondio`: se asegura el contacto y se le añaden
`preschedule-<ABBR>` y `send-to-respond`.

Las etiquetas de CAMBIO DE ESTADO (pre-schedule-confirmed, schedule-confirmed,
schedule-not-show, etc.) NO se mueven aquí: dependen de acciones del setter sobre
un registro ya creado y siguen viviendo en el CRM.
"""
import logging

import requests
from django.conf import settings

from calendario.leads.services.utils import SCHOOL_SLUG_TO_CODE
from calendario.leads.services.respondio import API_BASE, _headers, _ensure_contact

logger = logging.getLogger(__name__)


def _school_abbr(prellamada):
    """Deriva la abreviatura (CB/CL/CF/CG) desde la escuela del funnel."""
    funnel = prellamada.funnel
    escuela = (funnel.escuela if funnel else '') or ''
    code = SCHOOL_SLUG_TO_CODE.get(escuela.lower().strip())
    return (code or '').upper()


def push_pre_schedule(prellamada):
    """Asegura el contacto en Respond.io y le añade las etiquetas de pre-schedule."""
    api_key = getattr(settings, 'RESPONDIO_API_KEY', '')
    if not api_key:
        logger.warning('[Respond.io] RESPONDIO_API_KEY not configured')
        return

    email = prellamada.email
    if not email:
        logger.warning('[Respond.io] Prellamada %s: no email, skipping', prellamada.pk)
        return

    school_abbr = _school_abbr(prellamada)
    if not school_abbr:
        logger.warning(
            '[Respond.io] Prellamada %s: escuela no mapeable (%s), skipping',
            prellamada.pk, getattr(prellamada.funnel, 'escuela', None),
        )
        return

    first_name = prellamada.nombre.split()[0] if prellamada.nombre and prellamada.nombre.strip() else None
    phone = prellamada.telefono or None

    try:
        identifier, _ = _ensure_contact(
            email=email,
            first_name=first_name,
            phone=phone,
        )
        if not identifier:
            return

        tags = [f'preschedule-{school_abbr}', 'send-to-respond']
        requests.post(
            f'{API_BASE}/contact/{identifier}/tag',
            json=tags,
            headers=_headers(),
            timeout=10,
        )

        logger.info(
            '[Respond.io] Prellamada %s synced to %s (preschedule-%s)',
            prellamada.pk, identifier, school_abbr,
        )

    except Exception as e:
        logger.error('[Respond.io] Prellamada %s error: %s', prellamada.pk, e)
        raise
