import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def push_onboarding_session(reserva):
    """Envía la Reserva al CRM como OnboardingSession (nuestro endpoint).

    A diferencia del ingest de Schedule (services/crm.py, de Andres), la tabla de
    onboarding pide muy pocos campos: fecha de registro, fecha/hora de la llamada y
    los datos del lead. La venta de ConquerPass y el onboarder se resuelven del lado
    del CRM (por email / por un job aparte)."""
    base_url = settings.CRM_BASE_URL.rstrip('/')
    url = f'{base_url}/api/v1/ingest/onboarding-session/'
    api_key = settings.CRM_API_KEY

    if not api_key:
        logger.warning('[CRM-ONB] No API key configured, skipping reserva %s', reserva.pk)
        return

    payload = {
        'call_register': reserva.fecha_creacion.isoformat() if reserva.fecha_creacion else None,
        'call_datetime': reserva.inicio_utc.isoformat() if reserva.inicio_utc else None,
        'lead_name': reserva.nombre_invitado or '',
        'lead_email': reserva.email_invitado or '',
        'lead_phone_number': reserva.telefono_invitado or '',
        'event_name': reserva.event_type.nombre if reserva.event_type_id else '',
        'onboarder_email': reserva.host.email if reserva.host_id else '',
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
            '[CRM-ONB] Reserva %s sent successfully (%dms) — response: %s',
            reserva.pk, elapsed_ms, response.text[:200],
        )
    else:
        logger.error(
            '[CRM-ONB] Reserva %s failed (%dms) — status=%d response=%s',
            reserva.pk, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()
