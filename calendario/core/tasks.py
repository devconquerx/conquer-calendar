"""Tasks de infraestructura compartida (Supabase)."""
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def purge_old_supabase_backups():
    """Borra del respaldo en Supabase las filas más viejas que la retención
    configurada (SUPABASE_RETENTION_DAYS). Mantiene la ventana rodante para no
    superar la capacidad del plan."""
    from . import supabase

    if not supabase.is_enabled():
        return

    days = getattr(settings, 'SUPABASE_RETENTION_DAYS', 7)
    tables = (
        settings.SUPABASE_TABLE_LEADS,
        settings.SUPABASE_TABLE_PRE_SCHEDULES,
        settings.SUPABASE_TABLE_SCHEDULES,
    )
    for table in tables:
        try:
            supabase.delete_older_than(table, 'created_at', days)
        except Exception:
            logger.exception('[Supabase] purge falló para %s', table)
