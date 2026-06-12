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

    # Preferimos las columnas (snapshot); fallback al JSON `tracking` para filas
    # viejas. journey_id es columna propia con fallback al tracking.
    def _trk(field):
        return getattr(prellamada, field, '') or tracking.get(field)

    row = {
        'source_id': prellamada.pk,
        'created_at': prellamada.creado_en.isoformat() if prellamada.creado_en else None,
        'journey_id': prellamada.journey_id or tracking.get('journey_id'),
        'event_id': _trk('event_id'),
        'lead_email': prellamada.email,
        'lead_name': prellamada.nombre,
        'lead_phone_number': prellamada.telefono,
        'call_register': prellamada.creado_en.isoformat() if prellamada.creado_en else None,
        'token': str(prellamada.token),
        'form': prellamada.funnel.key if prellamada.funnel_id else None,
        'resultado': prellamada.resultado,
        'lead_scoring_score': float(prellamada.score) if prellamada.score is not None else None,
        'respuestas': prellamada.respuestas or {},
        # UTMs (columna con fallback al tracking)
        'utm_source': _trk('utm_source'),
        'utm_campaign': _trk('utm_campaign'),
        'utm_medium': _trk('utm_medium'),
        'utm_term': _trk('utm_term'),
        'utm_content': _trk('utm_content'),
        'utm_idcampaign': _trk('utm_idcampaign'),
        'utm_adsetid': _trk('utm_adsetid'),
        'utm_adid': _trk('utm_adid'),
        'utm_form_variant': _trk('utm_form_variant'),
    }
    return {k: v for k, v in row.items() if v is not None}


def push_pre_schedule(prellamada):
    """Upsert de la Prellamada en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_PRE_SCHEDULES,
        [_row_from_prellamada(prellamada)],
        on_conflict='source_id',
    )
