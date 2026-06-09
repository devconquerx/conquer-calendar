"""Respaldo de la Reserva en Supabase (espejo de conversions/services/crm.py).

Captura los mismos campos que se envían al CRM schedule, más `source_id` (PK de
la Reserva, clave de idempotencia) y `created_at`. Se encola al crear la reserva.
"""
import logging

from django.conf import settings

from calendario.core import supabase
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)


def _row_from_reserva(reserva):
    s = build_schedule_ctx(reserva)

    row = {
        'source_id': reserva.pk,
        'created_at': s.created.isoformat() if s.created else None,
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
    return {k: v for k, v in row.items() if v is not None}


def push_schedule(reserva):
    """Upsert de la Reserva en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_SCHEDULES,
        [_row_from_reserva(reserva)],
        on_conflict='source_id',
    )
