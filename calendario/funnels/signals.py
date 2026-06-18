import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Prellamada

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Prellamada)
def on_prellamada_saved(sender, instance, created, **kwargs):
    """En cada create/update de la Prellamada re-envía a CRM y Supabase. Ambos
    hacen upsert (por journey_id / source_id), así convergen al último estado a
    medida que la prellamada se actualiza (respuestas, reserva vinculada, etc.).
    Cada task marca su tag `<dest>_done` al terminar; el sweep reencola las que
    no lo tengan (ni `<dest>_failed`).

    En un update reseteamos los tags de estado a 'pendiente' antes de reencolar:
    así, si el envío de ESE update falla, la prellamada queda sin `<dest>_done` y
    el sweep la agarra (no solo las nunca sincronizadas).

    Respond.io es la excepción: sus etiquetas de pre-schedule (`preschedule-<ABBR>`)
    se aplican UNA sola vez (no cambian con las respuestas del formulario), así que
    no se resetea ni se reencola en cada update — solo se despacha si aún no se
    aplicó/falló y hay teléfono (es WhatsApp)."""
    from .tasks import (
        process_pre_schedule_crm,
        process_pre_schedule_supabase,
        process_pre_schedule_respondio,
    )

    if not created:
        instance.tags.remove('supabase_done', 'supabase_failed', 'crm_done', 'crm_failed')

    for task in (process_pre_schedule_crm, process_pre_schedule_supabase):
        try:
            task.delay(instance.pk)
        except Exception:
            logger.exception('No se pudo encolar %s para prellamada %s', task.name, instance.pk)

    if instance.telefono:
        names = set(instance.tags.names())
        if 'respondio_done' not in names and 'respondio_failed' not in names:
            try:
                process_pre_schedule_respondio.delay(instance.pk)
            except Exception:
                logger.exception(
                    'No se pudo encolar %s para prellamada %s',
                    process_pre_schedule_respondio.name, instance.pk,
                )
