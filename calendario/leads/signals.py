import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Lead

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Lead)
def on_lead_created(sender, instance, created, **kwargs):
    """Dispara las tareas Celery de todos los servicios al crear un nuevo lead.
    En los cambios posteriores solo reescribe su respaldo en Supabase."""
    if not created:
        _respaldar_cambio(instance.pk)
        return

    from .tasks import dispatch_lead_tasks

    # El lead ya está guardado: si Redis/Celery no responde, no puede romper el
    # alta (el post_save corre dentro del request). El sweep lo reencola después
    # porque le faltarán sus tags *_done.
    try:
        dispatch_lead_tasks(instance.pk)
    except Exception:
        logger.exception('No se pudieron encolar las tareas del lead %s', instance.pk)


def _respaldar_cambio(lead_id):
    """Tras el commit (para no subir un estado a medias). Si ya hay una copia
    pendiente, la deduplicación de calendario/core/resiliencia.py no encola otra."""
    def encolar():
        try:
            from .tasks import process_supabase
            process_supabase.delay(lead_id)
        except Exception:
            logger.exception('No se pudo encolar el respaldo del lead %s', lead_id)
    transaction.on_commit(encolar)
