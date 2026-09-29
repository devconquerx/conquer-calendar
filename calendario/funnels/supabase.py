"""Respaldo de la Prellamada en Supabase: el objeto completo en `datos` (jsonb).

Ver calendario/leads/services/supabase.py. Se reescribe en cada save de la
Prellamada (funnels/signals.py), así converge a su último estado.
"""
from django.conf import settings

from calendario.core import respaldo, supabase


def push_pre_schedule(prellamada):
    """Upsert de la Prellamada en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_PRE_SCHEDULES,
        [respaldo.fila_de_objeto(prellamada, prellamada.creado_en)],
        on_conflict='source_id',
    )
