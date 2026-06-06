import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Prellamada

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Prellamada)
def on_prellamada_saved(sender, instance, created, **kwargs):
    """Envía la Prellamada al CRM en cada create/update (réplica de funnels:
    on_pre_schedule_saved → process_pre_schedule_crm)."""
    from .tasks import process_pre_schedule_crm

    try:
        process_pre_schedule_crm.delay(instance.pk)
    except Exception:
        logger.exception('No se pudo encolar process_pre_schedule_crm para prellamada %s', instance.pk)
