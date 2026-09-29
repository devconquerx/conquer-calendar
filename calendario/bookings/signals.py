import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Reserva

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Reserva)
def on_reserva_cambiada(sender, instance, created, **kwargs):
    """Reescribe el respaldo en Supabase en cada cambio de la reserva
    (cancelaciones, reprogramaciones...). El alta la despacha
    dispatch_schedule_tasks junto al resto de envíos."""
    if created:
        return
    reserva_id = instance.pk

    def encolar():
        try:
            from .tasks import process_schedule_supabase
            process_schedule_supabase.delay(reserva_id)
        except Exception:
            logger.exception('No se pudo encolar el respaldo de la reserva %s', reserva_id)
    transaction.on_commit(encolar)
