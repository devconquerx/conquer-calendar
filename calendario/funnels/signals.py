import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Prellamada

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Prellamada)
def on_prellamada_saved(sender, instance, created, **kwargs):
    """Envía la Prellamada al CRM en cada create/update (réplica de funnels:
    on_pre_schedule_saved → process_pre_schedule_crm) y la respalda en Supabase
    una sola vez, al crearla (el upsert por source_id la mantiene idempotente)."""
    from .tasks import process_pre_schedule_crm, process_pre_schedule_supabase

    try:
        process_pre_schedule_crm.delay(instance.pk)
    except Exception:
        logger.exception('No se pudo encolar process_pre_schedule_crm para prellamada %s', instance.pk)

    if created:
        try:
            process_pre_schedule_supabase.delay(instance.pk)
        except Exception:
            logger.exception('No se pudo encolar process_pre_schedule_supabase para prellamada %s', instance.pk)
