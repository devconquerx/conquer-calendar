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

    try:
        supabase.purgar(getattr(settings, 'SUPABASE_RETENTION_DAYS', 7))
    except Exception:
        logger.exception('[Supabase] purge falló')


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True,
             retry_backoff_max=300, default_retry_delay=30, acks_late=True)
def process_request_supabase(self, tabla, fila):
    """Sube a Supabase un request en crudo capturado por
    calendario.core.respaldo.RespaldoRequestsMiddleware. `tabla` es 'requests'
    o 'video_progress'. Upsert por `id` (uuid de la captura): los reintentos no
    duplican."""
    from . import supabase

    nombre = {
        'requests': settings.SUPABASE_TABLE_REQUESTS,
        'video_progress': settings.SUPABASE_TABLE_VIDEO_PROGRESS,
    }[tabla]
    supabase.insert_rows(nombre, [fila], on_conflict='id')
