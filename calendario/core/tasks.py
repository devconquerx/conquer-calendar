"""Tasks de infraestructura compartida (Supabase)."""
import base64
import json
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


# Lo que trae el que manda la petición: ahí puede ir algo que el WAF de Cloudflare
# tome por un ataque (lo es: bots contra la raíz).
CAMPOS_DEL_CLIENTE = ('host', 'ruta', 'query', 'headers', 'body', 'body_texto')


def blindar(fila):
    """La misma fila con lo que mandó el cliente en un solo texto en base64, que
    el WAF ya no puede leer. Se guarda igual, solo que hay que decodificarlo."""
    original = {c: fila[c] for c in CAMPOS_DEL_CLIENTE if fila.get(c) is not None}
    blindada = {k: v for k, v in fila.items() if k not in CAMPOS_DEL_CLIENTE}
    blindada['body_texto'] = 'cloudflare-base64:' + base64.b64encode(
        json.dumps(original, ensure_ascii=False).encode()).decode()
    return blindada


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True,
             retry_backoff_max=300, default_retry_delay=30, acks_late=True)
def process_request_supabase(self, tabla, fila):
    """Sube a Supabase un request en crudo capturado por
    calendario.core.respaldo.RespaldoRequestsMiddleware. `tabla` es 'requests'
    o 'video_progress'. Upsert por `id` (uuid de la captura): los reintentos no
    duplican.

    Si el WAF de Cloudflare rechaza la fila por su contenido, va blindada
    (ver `blindar`): reintentarla tal cual se perdía siempre."""
    from . import supabase

    nombre = {
        'requests': settings.SUPABASE_TABLE_REQUESTS,
        'video_progress': settings.SUPABASE_TABLE_VIDEO_PROGRESS,
    }[tabla]
    try:
        supabase.insert_rows(nombre, [fila], on_conflict='id')
    except supabase.BloqueadoPorCloudflare:
        supabase.insert_rows(nombre, [blindar(fila)], on_conflict='id')
