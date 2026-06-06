import logging
import time

import requests
from django.conf import settings

from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)


def push_schedule(reserva):
    """Send schedule data to the CRM ingest API."""
    base_url = settings.CRM_BASE_URL.rstrip('/')
    url = f'{base_url}/api/v1/ingest/schedule/'
    api_key = settings.CRM_API_KEY

    if not api_key:
        logger.warning('[CRM] No API key configured, skipping reserva %s', reserva.pk)
        return

    s = build_schedule_ctx(reserva)

    payload = {
        'lead_email': s.lead_email,
        'lead_name': s.lead_name,
        'lead_phone_number': s.lead_phone_number,
        'lead_country': s.lead_country,
        'call_register': s.call_register.isoformat() if s.call_register else None,
        'call_datetime': s.call_datetime.isoformat() if s.call_datetime else None,
        'event': s.event,
        'closer_from_make': s.closer_from_make,
        'form': s.form,
        'specialisation': s.specialisation,
        'timezone_string': s.timezone_string,
        'meet_join_url': s.meet_join_url,
        # Scoring
        'lead_scoring_score': float(s.lead_scoring_score) if s.lead_scoring_score is not None else None,
        'lead_scoring_text': s.lead_scoring_text,
        # Answers
        'q1_answer': s.q1_answer,
        'q2_answer': s.q2_answer,
        'q3_answer': s.q3_answer,
        'q4_answer': s.q4_answer,
        'q5_answer': s.q5_answer,
        'q6_answer': s.q6_answer,
        # UTMs
        'utm_source': s.utm_source,
        'utm_campaign': s.utm_campaign,
        'utm_medium': s.utm_medium,
        'utm_term': s.utm_term,
        'utm_content': s.utm_content,
        'utm_idcampaign': s.utm_idcampaign,
        'utm_adsetid': s.utm_adsetid,
        'utm_adid': s.utm_adid,
        'utm_vsl': s.utm_vsl,
        'utm_nuturing': s.utm_nuturing,
        'utm_form_length': s.utm_form_length,
        'utm_form_variant': s.utm_form_variant,
        # Tracking
        'event_id': s.event_id,
        'journey_id': s.journey_id,
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
            '[CRM] Reserva %s sent successfully (%dms) — response: %s',
            reserva.pk, elapsed_ms, response.text[:200],
        )
    else:
        logger.error(
            '[CRM] Reserva %s failed (%dms) — status=%d response=%s',
            reserva.pk, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()
