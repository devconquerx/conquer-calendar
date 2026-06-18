"""Celery tasks de conversiones del lado 'schedule' (sobre Reserva).

Equivalente a funnels/apps/schedules/tasks.py, adaptado a conquer-calendar:
la Reserva es el evento agendado (no hay Calendly ni webhook), así que las
tareas se despachan directamente al crear la reserva. El tracking/PII viene del
Lead enlazado (resuelto en build_schedule_ctx).
"""
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


# ---------------------------------------------------------------------------
# Ad platform / CRM tasks para Reserva
# ---------------------------------------------------------------------------

@shared_task(**RETRY_POLICY)
def process_schedule_meta_capi(self, reserva_id):
    from .models import Reserva
    from .conversions.services import meta_capi

    reserva = Reserva.objects.get(pk=reserva_id)
    meta_capi.push_schedule(reserva)
    reserva.tags.add('sch_meta_capi_done')
    logger.info('Reserva %s: sch_meta_capi_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_tiktok_events(self, reserva_id):
    from .models import Reserva
    from .conversions.services import tiktok_events

    reserva = Reserva.objects.get(pk=reserva_id)
    tiktok_events.push_schedule(reserva)
    reserva.tags.add('sch_tiktok_events_done')
    logger.info('Reserva %s: sch_tiktok_events_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_google_ads(self, reserva_id):
    from .models import Reserva
    from .conversions.services import google_ads

    reserva = Reserva.objects.get(pk=reserva_id)
    google_ads.push_schedule(reserva)
    reserva.tags.add('sch_google_ads_done')
    logger.info('Reserva %s: sch_google_ads_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_activecampaign(self, reserva_id):
    from .models import Reserva
    from .conversions.services import activecampaign

    reserva = Reserva.objects.get(pk=reserva_id)
    activecampaign.push_schedule(reserva)
    reserva.tags.add('sch_activecampaign_done')
    logger.info('Reserva %s: sch_activecampaign_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_respondio(self, reserva_id):
    from .models import Reserva
    from .conversions.services import respondio

    reserva = Reserva.objects.get(pk=reserva_id)
    respondio.push_schedule(reserva)
    reserva.tags.add('sch_respondio_done')
    logger.info('Reserva %s: sch_respondio_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_crm(self, reserva_id):
    """Envía la Reserva al CRM ingest. Doble gate:
    1. CRM_INGEST_ENABLED (interruptor global).
    2. EventType.notificar_crm: solo se envían las reservas cuyo tipo de evento
       está marcado como "Notificar al CRM" (la casilla de las llamadas de
       venta). El resto (tutorías, team calls, internos) no va al CRM.
    Mientras no aplique hace no-op (el sweep no reintenta: sch_crm_dispatched ya
    está puesto en el dispatch)."""
    if not settings.CRM_INGEST_ENABLED:
        logger.info('Reserva %s: CRM send SKIPPED (CRM_INGEST_ENABLED=False)', reserva_id)
        return

    from .models import Reserva
    from .conversions.services import crm

    reserva = Reserva.objects.select_related('event_type').get(pk=reserva_id)
    if not (reserva.event_type and reserva.event_type.notificar_crm):
        logger.info('Reserva %s: CRM send SKIPPED (event_type sin "Notificar al CRM")', reserva_id)
        reserva.tags.add('sch_crm_skipped')
        return

    crm.push_schedule(reserva)
    reserva.tags.add('sch_crm_done')
    logger.info('Reserva %s: sch_crm_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_onboarding_session(self, reserva_id):
    """Envía la Reserva al CRM como OnboardingSession (nuestro endpoint, en lugar del
    de Schedule de Andres). Mismo doble gate:
    1. CRM_INGEST_ENABLED (interruptor global).
    2. EventType.notificar_crm: solo las reservas marcadas para el CRM.
    El código de `process_schedule_crm` (Andres) se mantiene intacto pero ya no se
    despacha; este es el método que usamos ahora."""
    if not settings.CRM_INGEST_ENABLED:
        logger.info('Reserva %s: ONB send SKIPPED (CRM_INGEST_ENABLED=False)', reserva_id)
        return

    from .models import Reserva
    from .conversions.services import onboarding

    reserva = Reserva.objects.select_related('event_type').get(pk=reserva_id)
    if not (reserva.event_type and reserva.event_type.notificar_crm):
        logger.info('Reserva %s: ONB send SKIPPED (event_type sin "Notificar al CRM")', reserva_id)
        reserva.tags.add('sch_onboarding_skipped')
        return

    onboarding.push_onboarding_session(reserva)
    reserva.tags.add('sch_onboarding_done')
    logger.info('Reserva %s: sch_onboarding_done', reserva_id)


@shared_task(**RETRY_POLICY)
def process_schedule_supabase(self, reserva_id):
    """Respaldo de la Reserva en Supabase. Independiente del CRM: se ejecuta
    siempre, aunque el envío al CRM esté desactivado."""
    from .models import Reserva
    from .conversions.services import supabase

    reserva = Reserva.objects.get(pk=reserva_id)
    supabase.push_schedule(reserva)
    reserva.tags.add('sch_supabase_done')
    logger.info('Reserva %s: sch_supabase_done', reserva_id)


def dispatch_schedule_tasks(reserva_id):
    """Evalúa condiciones y encola las tareas de conversión para una reserva."""
    from .models import Reserva
    from .conversions.services.utils import build_schedule_ctx
    from calendario.leads.services.utils import is_from_meta, is_from_tiktok, is_from_google

    reserva = Reserva.objects.select_related('event_type').prefetch_related('tags').get(pk=reserva_id)

    # Guard: evita doble despacho
    if 'sch_tasks_dispatched' in set(reserva.tags.names()):
        logger.info('Reserva %s: tasks already dispatched, skipping', reserva_id)
        return
    reserva.tags.add('sch_tasks_dispatched')

    # Respaldo en Supabase: siempre, independiente del origen y del CRM.
    process_schedule_supabase.delay(reserva_id)

    s = build_schedule_ctx(reserva)
    lead = s.lead

    # Tareas de plataformas de ads (condicionadas por la fuente de tráfico). Si no
    # hay Lead emparejado, se usa el utm_source del tracking como fallback (igual
    # que funnels), para no perder conversiones de reservas sin Lead.
    if lead:
        if is_from_meta(lead):
            process_schedule_meta_capi.delay(reserva_id)
        if is_from_tiktok(lead):
            process_schedule_tiktok_events.delay(reserva_id)
        if is_from_google(lead):
            process_schedule_google_ads.delay(reserva_id)
    else:
        src = (s.utm_source or '').lower()
        if src == 'metaads':
            process_schedule_meta_capi.delay(reserva_id)
        if 'tiktok' in src:
            process_schedule_tiktok_events.delay(reserva_id)
        if src == 'googleads':
            process_schedule_google_ads.delay(reserva_id)

    if s.lead_email:
        process_schedule_activecampaign.delay(reserva_id)

    if s.lead_phone_number:
        process_schedule_respondio.delay(reserva_id)

    # CRM: el destino depende del tipo de evento (EventType.crm_destino):
    #   'schedule'   → tabla Schedules del CRM (llamada de venta) vía process_schedule_crm
    #   'onboarding' → tabla OnboardingSession (default) vía process_onboarding_session
    # El gate notificar_crm lo revisa cada task internamente.
    et = reserva.event_type
    if et and et.crm_destino == 'schedule':
        process_schedule_crm.delay(reserva_id)
        reserva.tags.add('sch_crm_dispatched')
    else:
        process_onboarding_session.delay(reserva_id)
        reserva.tags.add('sch_onboarding_dispatched')

    logger.info('Reserva %s: dispatched processing tasks', reserva_id)


@shared_task
def sweep_incomplete_reservas():
    """Re-encola tareas cuyo tag sch_*_done falta (reservas de las últimas 24 h, creadas hace > 5 min)."""
    from .models import Reserva
    from .conversions.services.utils import build_schedule_ctx
    from calendario.leads.services.utils import is_from_meta, is_from_tiktok, is_from_google

    now = timezone.now()
    cutoff_old = now - timedelta(hours=24)
    cutoff_recent = now - timedelta(minutes=5)

    reservas = (
        Reserva.objects
        .filter(fecha_creacion__gte=cutoff_old, fecha_creacion__lte=cutoff_recent)
        .select_related('event_type')
        .prefetch_related('tags')
    )

    requeued = 0
    for reserva in reservas.iterator(chunk_size=200):
        tag_names = set(reserva.tags.names())
        s = build_schedule_ctx(reserva)
        lead = s.lead

        if 'sch_supabase_done' not in tag_names and 'sch_supabase_failed' not in tag_names:
            process_schedule_supabase.delay(reserva.pk)
            requeued += 1

        # Plataformas de ads: por Lead si existe, si no por utm_source (fallback).
        if lead:
            meta_on = is_from_meta(lead)
            tiktok_on = is_from_tiktok(lead)
            google_on = is_from_google(lead)
        else:
            src = (s.utm_source or '').lower()
            meta_on = src == 'metaads'
            tiktok_on = 'tiktok' in src
            google_on = src == 'googleads'

        if meta_on and 'sch_meta_capi_done' not in tag_names and 'sch_meta_capi_failed' not in tag_names:
            process_schedule_meta_capi.delay(reserva.pk)
            requeued += 1
        if tiktok_on and 'sch_tiktok_events_done' not in tag_names and 'sch_tiktok_events_failed' not in tag_names:
            process_schedule_tiktok_events.delay(reserva.pk)
            requeued += 1
        if google_on and 'sch_google_ads_done' not in tag_names and 'sch_google_ads_failed' not in tag_names:
            process_schedule_google_ads.delay(reserva.pk)
            requeued += 1
        if s.lead_email and 'sch_activecampaign_done' not in tag_names and 'sch_activecampaign_failed' not in tag_names:
            process_schedule_activecampaign.delay(reserva.pk)
            requeued += 1
        if s.lead_phone_number and 'sch_respondio_done' not in tag_names and 'sch_respondio_failed' not in tag_names:
            process_schedule_respondio.delay(reserva.pk)
            requeued += 1

        # CRM: el destino (schedule vs onboarding) depende del EventType.crm_destino.
        et = reserva.event_type
        if et and et.crm_destino == 'schedule':
            if ('sch_crm_done' not in tag_names and 'sch_crm_failed' not in tag_names
                    and 'sch_crm_dispatched' not in tag_names):
                process_schedule_crm.delay(reserva.pk)
                reserva.tags.add('sch_crm_dispatched')
                requeued += 1
        else:
            if ('sch_onboarding_done' not in tag_names and 'sch_onboarding_failed' not in tag_names
                    and 'sch_onboarding_dispatched' not in tag_names):
                process_onboarding_session.delay(reserva.pk)
                reserva.tags.add('sch_onboarding_dispatched')
                requeued += 1

    logger.info('[Sweep] Checked reservas since %s, requeued %d tasks', cutoff_old, requeued)
    return requeued
