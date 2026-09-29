"""Respaldo de la Reserva en Supabase: el objeto completo en `datos` (jsonb).

Ver calendario/leads/services/supabase.py. Se reescribe en cada cambio de la
Reserva (cancelaciones y reprogramaciones incluidas, ver bookings/signals.py).
"""
from django.conf import settings

from calendario.core import respaldo, supabase


def push_schedule(reserva):
    """Upsert de la Reserva en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_SCHEDULES,
        [respaldo.fila_de_objeto(reserva, reserva.fecha_creacion)],
        on_conflict='source_id',
    )
