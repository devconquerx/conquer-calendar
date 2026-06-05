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

    dispatch_lead_tasks(instance.pk)
