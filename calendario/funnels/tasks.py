import logging

from celery import shared_task

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
    # TEMP: deshabilitado (igual que funnels) — habilitar cuando el CRM esté listo
    logger.info('Prellamada %s: CRM send SKIPPED (temporarily disabled)', prellamada_id)
    return

    from .models import Prellamada
    from . import crm_preschedule

    prellamada = Prellamada.objects.select_related('funnel').get(pk=prellamada_id)
    crm_preschedule.push_pre_schedule(prellamada)
    logger.info('Prellamada %s: crm_sent', prellamada_id)


@shared_task(**RETRY_POLICY)
def process_pre_schedule_supabase(self, prellamada_id):
    """Respaldo de la Prellamada en Supabase. Independiente del CRM: se ejecuta
    siempre, aunque el envío al CRM esté desactivado."""
    from .models import Prellamada
    from . import supabase

    prellamada = Prellamada.objects.select_related('funnel').get(pk=prellamada_id)
    supabase.push_pre_schedule(prellamada)
    logger.info('Prellamada %s: supabase_done', prellamada_id)
