"""Respaldo del Lead en Supabase: el objeto completo en `datos` (jsonb).

Todos los campos del modelo, no una lista fija de columnas: si el Lead gana un
campo, el respaldo lo recoge solo. Upsert por `source_id` (PK del Lead), así que
cada cambio reescribe la fila. El request en crudo que lo creó va aparte, a la
tabla `requests` (calendario/core/respaldo.py).
"""
from django.conf import settings

from calendario.core import respaldo, supabase


def push_lead(lead):
    """Upsert del Lead en Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_LEADS,
        [respaldo.fila_de_objeto(lead, lead.created)],
        on_conflict='source_id',
    )
