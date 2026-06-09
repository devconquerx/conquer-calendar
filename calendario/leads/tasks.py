import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry policy shared by all service tasks
# ---------------------------------------------------------------------------
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
# Individual service tasks
# ---------------------------------------------------------------------------

@shared_task(**RETRY_POLICY)
def process_meta_capi(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import meta_capi

    lead = Lead.objects.get(pk=lead_id)
    meta_capi.push_lead(lead)
    lead.tags.add('meta_capi_done')
    logger.info('Lead %s: meta_capi_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_tiktok_events(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import tiktok_events

    lead = Lead.objects.get(pk=lead_id)
    tiktok_events.push_lead(lead)
    lead.tags.add('tiktok_events_done')
    logger.info('Lead %s: tiktok_events_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_google_ads(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import google_ads

    lead = Lead.objects.get(pk=lead_id)
    google_ads.push_lead(lead)
    lead.tags.add('google_ads_done')
    logger.info('Lead %s: google_ads_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_respondio(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import respondio

    lead = Lead.objects.get(pk=lead_id)
    respondio.push_lead(lead)
    lead.tags.add('respondio_done')
    logger.info('Lead %s: respondio_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_activecampaign(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import activecampaign

    lead = Lead.objects.get(pk=lead_id)
    activecampaign.push_lead(lead)
    lead.tags.add('activecampaign_done')
    logger.info('Lead %s: activecampaign_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_neverbounce(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import neverbounce

    lead = Lead.objects.get(pk=lead_id)
    if lead.neverbounce_result:
        lead.tags.add('neverbounce_done')
        process_crm_send.delay(lead_id)
        return
    neverbounce.validate_email(lead)
    lead.refresh_from_db(fields=['neverbounce_result'])
    if lead.neverbounce_result:
        lead.tags.add('neverbounce_done')
        logger.info('Lead %s: neverbounce_done', lead_id)
        process_crm_send.delay(lead_id)
    else:
        raise RuntimeError(f'NeverBounce did not populate result for lead {lead_id}')


@shared_task(**RETRY_POLICY)
def process_crm_send(self, lead_id):
    # TEMP: deshabilitado (igual que funnels) — habilitar cuando el CRM esté listo
    logger.info('Lead %s: CRM send SKIPPED (temporarily disabled)', lead_id)
    return

    from calendario.leads.models import Lead
    from calendario.leads.services import crm

    lead = Lead.objects.get(pk=lead_id)
    crm.push_lead(lead)
    lead.tags.add('crm_done')
    logger.info('Lead %s: crm_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_supabase(self, lead_id):
    """Respaldo del Lead en Supabase. Independiente del CRM: se ejecuta siempre,
    aunque el envío al CRM esté desactivado."""
    from calendario.leads.models import Lead
    from calendario.leads.services import supabase

    lead = Lead.objects.get(pk=lead_id)
    supabase.push_lead(lead)
    lead.tags.add('supabase_done')
    logger.info('Lead %s: supabase_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_welcome_email(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import mailgun

    lead = Lead.objects.get(pk=lead_id)
    mailgun.send_welcome_email(lead)
    lead.tags.add('welcome_email_done')
    logger.info('Lead %s: welcome_email_done', lead_id)


# ---------------------------------------------------------------------------
# Dispatch helper — called from the signal
# ---------------------------------------------------------------------------

def dispatch_lead_tasks(lead_id):
    """Evaluate conditions and enqueue applicable service tasks for a lead."""
    from calendario.leads.models import Lead
    from calendario.leads.services.utils import is_from_meta, is_from_tiktok, is_from_google

    lead = Lead.objects.get(pk=lead_id)

    # Respaldo en Supabase: siempre, independiente del origen y del CRM.
    process_supabase.delay(lead_id)

    if is_from_meta(lead):
        process_meta_capi.delay(lead_id)
    if is_from_tiktok(lead):
        process_tiktok_events.delay(lead_id)
    if is_from_google(lead):
        process_google_ads.delay(lead_id)
    if lead.lead_phone:
        process_respondio.delay(lead_id)
    if lead.email:
        process_activecampaign.delay(lead_id)
        process_neverbounce.delay(lead_id)
        process_welcome_email.delay(lead_id)

    logger.info('Lead %s: dispatched processing tasks', lead_id)


# ---------------------------------------------------------------------------
# Periodic sweep — catches anything that failed after all retries
# ---------------------------------------------------------------------------

@shared_task
def sweep_incomplete_leads():
    """Re-encola tareas cuyo tag *_done falta (leads de las últimas 24 h, creados hace > 5 min)."""
    from calendario.leads.models import Lead
    from calendario.leads.services.utils import is_from_meta, is_from_tiktok, is_from_google

    now = timezone.now()
    cutoff_old = now - timedelta(hours=24)
    cutoff_recent = now - timedelta(minutes=5)

    leads = (
        Lead.objects
        .filter(created__gte=cutoff_old, created__lte=cutoff_recent)
        .prefetch_related('tags')
    )

    requeued = 0
    for lead in leads.iterator(chunk_size=200):
        tag_names = set(lead.tags.names())

        if 'supabase_done' not in tag_names and 'supabase_failed' not in tag_names:
            process_supabase.delay(lead.pk)
            requeued += 1

        if is_from_meta(lead) and 'meta_capi_done' not in tag_names and 'meta_capi_failed' not in tag_names:
            process_meta_capi.delay(lead.pk)
            requeued += 1

        if is_from_tiktok(lead) and 'tiktok_events_done' not in tag_names and 'tiktok_events_failed' not in tag_names:
            process_tiktok_events.delay(lead.pk)
            requeued += 1

        if is_from_google(lead) and 'google_ads_done' not in tag_names and 'google_ads_failed' not in tag_names:
            process_google_ads.delay(lead.pk)
            requeued += 1

        if lead.lead_phone and 'respondio_done' not in tag_names and 'respondio_failed' not in tag_names:
            process_respondio.delay(lead.pk)
            requeued += 1

        if lead.email and 'activecampaign_done' not in tag_names and 'activecampaign_failed' not in tag_names:
            process_activecampaign.delay(lead.pk)
            requeued += 1

        if lead.email and 'neverbounce_done' not in tag_names and 'neverbounce_failed' not in tag_names:
            process_neverbounce.delay(lead.pk)
            requeued += 1

        if lead.email and 'welcome_email_done' not in tag_names and 'welcome_email_failed' not in tag_names:
            process_welcome_email.delay(lead.pk)
            requeued += 1

        if lead.email and 'neverbounce_done' in tag_names and 'crm_done' not in tag_names and 'crm_failed' not in tag_names:
            process_crm_send.delay(lead.pk)
            requeued += 1

    logger.info('[Sweep] Checked leads since %s, requeued %d tasks', cutoff_old, requeued)
    return requeued
