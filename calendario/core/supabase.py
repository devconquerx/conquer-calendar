"""Cliente compartido de Supabase para el respaldo rodante de los datos del CRM.

Escribe vía la REST API de Supabase (PostgREST) usando la *secret key* del lado
servidor (bypassa RLS). Cada origen (lead/preschedule/schedule) hace upsert por
`source_id` para que los reintentos de Celery no dupliquen filas.

Fail-safe: si SUPABASE_ENABLED=False o falta URL/secret, los métodos hacen no-op
y loguean — nunca lanzan por falta de configuración. Sí lanzan (para que Celery
reintente) cuando Supabase devuelve un error HTTP en una operación que sí se
intentó.

Retención corta: el respaldo guarda solo una ventana reciente; `purgar` (invocado
por la task periódica) borra lo más viejo que SUPABASE_RETENTION_DAYS.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BloqueadoPorCloudflare(requests.HTTPError):
    """El WAF de Cloudflare (delante de Supabase) rechazó la petición por lo que
    lleva dentro: un 403 con su página "Attention Required!", no un error de
    PostgREST. Reintentar lo mismo da lo mismo (FUNNELS-7M)."""


# Por debajo del soft time limit de Celery (90 s), para que la tarea no se corte antes.
PURGA_TIMEOUT_SECONDS = 80


def is_enabled():
    """True si el respaldo a Supabase está activo y mínimamente configurado."""
    if not getattr(settings, 'SUPABASE_ENABLED', False):
        return False
    if not getattr(settings, 'SUPABASE_URL', '') or not getattr(settings, 'SUPABASE_SECRET_KEY', ''):
        logger.warning('[Supabase] SUPABASE_ENABLED=True pero falta SUPABASE_URL/SUPABASE_SECRET_KEY; skip.')
        return False
    return True


def _base_url():
    return settings.SUPABASE_URL.rstrip('/') + '/rest/v1'


def _headers(extra=None):
    key = settings.SUPABASE_SECRET_KEY
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }
    if extra:
        headers.update(extra)
    return headers


def insert_rows(table, rows, on_conflict=None):
    """Inserta (o upsert si `on_conflict`) filas en `table` vía PostgREST.

    Args:
        table: nombre de la tabla en Supabase.
        rows: lista de dicts (una fila por dict).
        on_conflict: columna con constraint UNIQUE para hacer upsert idempotente.

    No-op silencioso si Supabase está deshabilitado o sin configurar. Lanza si
    Supabase responde con error HTTP, para que la task de Celery reintente.
    """
    if not rows:
        return
    if not is_enabled():
        logger.info('[Supabase] deshabilitado, skip insert en %s (%d filas)', table, len(rows))
        return

    params = {}
    prefer = 'return=minimal'
    if on_conflict:
        params['on_conflict'] = on_conflict
        prefer = 'resolution=merge-duplicates,return=minimal'

    response = requests.post(
        f'{_base_url()}/{table}',
        params=params,
        json=rows,
        headers=_headers({'Prefer': prefer}),
        timeout=settings.SUPABASE_TIMEOUT_SECONDS,
    )
    if response.status_code == 403 and 'cloudflare' in response.text[:2000].lower():
        logger.warning('[Supabase] Cloudflare bloqueó el insert en %s', table)
        raise BloqueadoPorCloudflare(f'Cloudflare bloqueó el insert en {table}', response=response)
    if response.status_code not in (200, 201, 204):
        logger.error('[Supabase] insert en %s falló — status=%d body=%s',
                     table, response.status_code, response.text[:500])
        response.raise_for_status()

    logger.info('[Supabase] %d fila(s) escrita(s) en %s', len(rows), table)


def purgar(days):
    """Borra lo más viejo que `days` días (función SQL purgar_respaldo, ver
    docs/supabase_backup_schema.sql). Va en SQL y no con un DELETE por tabla
    porque las filas dependen unas de otras: hay que borrar en orden y no tocar
    lo que otra fila todavía usa. Devuelve lo borrado por tabla."""
    if not is_enabled():
        return None
    # La purga recorre todas las tablas y tarda ~20 s: con el timeout de un
    # insert (15 s) se cortaba cada hora y el respaldo no se vaciaba (FUNNELS-FE).
    response = requests.post(f'{_base_url()}/rpc/purgar_respaldo', json={'dias': days},
                             headers=_headers(), timeout=PURGA_TIMEOUT_SECONDS)
    if not response.ok:
        # Sin el cuerpo, un 500 de la función SQL no dice qué paso falló (FUNNELS-F3).
        logger.error('[Supabase] purga — status=%d body=%s', response.status_code, response.text[:1000])
    response.raise_for_status()
    hecho = response.json()
    # Un paso que choca con una escritura simultánea no tumba la purga: devuelve
    # el error en lugar del número y se reintenta en la siguiente pasada.
    errores = {tabla: v for tabla, v in hecho.items() if not isinstance(v, int)}
    if errores:
        logger.error('[Supabase] purga incompleta: %s', errores)
    logger.info('[Supabase] purga de más de %d días: %s', days, hecho)
    return hecho


def tamano_mb():
    """Tamaño de la base de datos de Supabase en MB (función SQL tamano_bd_mb,
    ver docs/supabase_backup_schema.sql). None si no se puede saber."""
    if not is_enabled():
        return None
    response = requests.post(f'{_base_url()}/rpc/tamano_bd_mb', json={}, headers=_headers(),
                             timeout=settings.SUPABASE_TIMEOUT_SECONDS)
    response.raise_for_status()
    return float(response.json())
