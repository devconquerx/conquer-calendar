"""Respaldo de la Prellamada en Supabase (espejo de funnels/crm_preschedule.py).

Captura los mismos campos que se envían al CRM pre-schedule, más `source_id`
(PK de la Prellamada, clave de idempotencia) y `created_at`. Se respalda al
crear la Prellamada.
"""
import logging

from django.conf import settings

from calendario.core import supabase

logger = logging.getLogger(__name__)


def _row_from_prellamada(prellamada):
    tracking = prellamada.tracking if isinstance(prellamada.tracking, dict) else {}

    row = {
        'source_id': prellamada.pk,
        'created_at': prellamada.creado_en.isoformat() if prellamada.creado_en else None,
        'journey_id': tracking.get('journey_id'),
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
    return {k: v for k, v in row.items() if v is not None}


def push_pre_schedule(prellamada):
    """Upsert de la Prellamada en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_PRE_SCHEDULES,
        [_row_from_prellamada(prellamada)],
        on_conflict='source_id',
    )
