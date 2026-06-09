import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

RETRY_POLICY = dict(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    default_retry_delay=30,
    acks_late=True,
)


@shared_task(**RETRY_POLICY)
def process_pre_schedule_crm(self, prellamada_id):
    """Envía la Prellamada al CRM ingest. Gated por FUNNELS_PRESCHEDULE_CRM_ENABLED:
    mientras esté en False hace no-op (y el sweep no la reintenta)."""
    if not settings.FUNNELS_PRESCHEDULE_CRM_ENABLED:
        logger.info('Prellamada %s: CRM send SKIPPED (FUNNELS_PRESCHEDULE_CRM_ENABLED=False)', prellamada_id)
        return

    from .models import Prellamada
    from . import crm_preschedule

    prellamada = Prellamada.objects.select_related('funnel').get(pk=prellamada_id)
    crm_preschedule.push_pre_schedule(prellamada)
    prellamada.tags.add('crm_done')
    logger.info('Prellamada %s: crm_done', prellamada_id)


@shared_task(**RETRY_POLICY)
def process_pre_schedule_supabase(self, prellamada_id):
    """Respaldo de la Prellamada en Supabase (upsert por source_id). Se dispara en
    cada save: el upsert hace converger la fila al último estado de la Prellamada
    (respuestas, score, resultado, reserva…). Independiente del CRM."""
    from .models import Prellamada
    from . import supabase

    prellamada = Prellamada.objects.select_related('funnel').get(pk=prellamada_id)
    supabase.push_pre_schedule(prellamada)
    prellamada.tags.add('supabase_done')
    logger.info('Prellamada %s: supabase_done', prellamada_id)


# ---------------------------------------------------------------------------
# Sweep — red de seguridad: reencola los envíos que no completaron.
# Una prellamada está pendiente para un destino si no tiene `<dest>_done` ni
# `<dest>_failed` (este último lo pone el handler de celery al agotar reintentos).
# ---------------------------------------------------------------------------

@shared_task
def sweep_incomplete_prellamadas():
    """Reencola CRM/Supabase para prellamadas de las últimas 24 h (creadas hace
    > 2 min) que no tengan su tag `<dest>_done` ni `<dest>_failed`."""
    from .models import Prellamada

    now = timezone.now()
    cutoff_old = now - timedelta(hours=24)
    cutoff_recent = now - timedelta(minutes=2)

    prellamadas = (
        Prellamada.objects
        .filter(creado_en__gte=cutoff_old, creado_en__lte=cutoff_recent)
        .prefetch_related('tags')
    )
    crm_on = settings.FUNNELS_PRESCHEDULE_CRM_ENABLED

    requeued = 0
    for p in prellamadas.iterator(chunk_size=200):
        names = set(t.name for t in p.tags.all())

        if 'supabase_done' not in names and 'supabase_failed' not in names:
            process_pre_schedule_supabase.delay(p.pk)
            requeued += 1

        if crm_on and 'crm_done' not in names and 'crm_failed' not in names:
            process_pre_schedule_crm.delay(p.pk)
            requeued += 1

    logger.info('[Sweep] Prellamadas revisadas desde %s, re-encoladas %d', cutoff_old, requeued)
    return requeued
