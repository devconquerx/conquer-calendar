import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Lead

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Lead)
def on_lead_created(sender, instance, created, **kwargs):
    """Dispara las tareas Celery de todos los servicios al crear un nuevo lead."""
    if not created:
        return

    from .tasks import dispatch_lead_tasks

    # El lead ya está guardado: si Redis/Celery no responde, no puede romper el
    # alta (el post_save corre dentro del request). El sweep lo reencola después
    # porque le faltarán sus tags *_done.
    try:
        dispatch_lead_tasks(instance.pk)
    except Exception:
        logger.exception('No se pudieron encolar las tareas del lead %s', instance.pk)
