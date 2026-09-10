import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

# Cuántos vídeos copia como mucho cada pasada. Con ~100 vídeos nuevos al mes
# esto no se roza nunca; el tope está para que una librería recién añadida (o la
# primera pasada tras una caída larga) no monopolice el worker durante horas.
LIMITE_POR_PASADA = 25


@shared_task(
    name='calendario.video_backup.tasks.sincronizar_bunny_r2',
    time_limit=3600,
    soft_time_limit=3540,
)
def sincronizar_bunny_r2():
    """Copia a R2 los vídeos de Bunny que aún no estén respaldados.

    El límite de tiempo es propio y generoso porque el global del proyecto
    (120 s) está pensado para tareas de leads: aquí una sola pasada puede
    mover varios GB.
    """
    from .services import espejo

    if not getattr(settings, 'VIDEO_BACKUP_ENABLED', False):
        return {'saltado': 'VIDEO_BACKUP_ENABLED=False'}

    resumen = espejo.barrer(limite=LIMITE_POR_PASADA)
    logger.info('video_backup: %s', resumen)
    return resumen
