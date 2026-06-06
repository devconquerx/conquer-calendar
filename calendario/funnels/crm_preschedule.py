"""Envío de la Prellamada al CRM ingest (equivalente a funnels
schedules/services/crm_preschedule.py, que opera sobre PreSchedule).

En conquer-calendar la `Prellamada` es el equivalente del PreSchedule: se crea
al terminar el formulario. El tracking (journey_id/event_id/UTMs) vive en
`Prellamada.tracking` (JSON).
"""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def push_pre_schedule(prellamada):
    """Envía los datos de la Prellamada al CRM ingest (upsert por journey_id)."""
    base_url = settings.CRM_BASE_URL.rstrip('/')
    url = f'{base_url}/api/v1/ingest/pre-schedule/'
    api_key = settings.CRM_API_KEY

    if not api_key:
        logger.warning('[CRM] No API key configured, skipping prellamada %s', prellamada.pk)
        return

    tracking = prellamada.tracking if isinstance(prellamada.tracking, dict) else {}
    journey_id = tracking.get('journey_id')
    if not journey_id:
        logger.warning('[CRM] Prellamada %s sin journey_id, skipping', prellamada.pk)
        return

    payload = {
        'journey_id': journey_id,
        'event_id': tracking.get('event_id'),
        'lead_email': prellamada.email,
        'lead_name': prellamada.nombre,
        'lead_phone_number': prellamada.telefono,
        'call_register': prellamada.creado_en.isoformat() if prellamada.creado_en else None,
        'token': str(prellamada.token),
        'form': prellamada.funnel.key if prellamada.funnel_id else None,
        'resultado': prellamada.resultado,
        'lead_scoring_score': float(prellamada.score) if prellamada.score is not None else None,
        'respuestas': prellamada.respuestas or {},
        # UTMs desde el tracking
        'utm_source': tracking.get('utm_source'),
        'utm_campaign': tracking.get('utm_campaign'),
        'utm_medium': tracking.get('utm_medium'),
        'utm_term': tracking.get('utm_term'),
        'utm_content': tracking.get('utm_content'),
        'utm_idcampaign': tracking.get('utm_idcampaign'),
        'utm_adsetid': tracking.get('utm_adsetid'),
        'utm_adid': tracking.get('utm_adid'),
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    start = time.time()
    response = requests.post(
        url,
        json=payload,
        headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
        timeout=15,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    if response.status_code in (200, 201):
        logger.info(
            '[CRM] Prellamada %s sent successfully (%dms) — created=%s',
            prellamada.pk, elapsed_ms, response.status_code == 201,
        )
    else:
        logger.error(
            '[CRM] Prellamada %s failed (%dms) — status=%d response=%s',
            prellamada.pk, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()
