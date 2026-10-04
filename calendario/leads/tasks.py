import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
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
def process_funnelchat(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import funnelchat

    lead = Lead.objects.get(pk=lead_id)
    funnelchat.push_lead(lead)
    lead.tags.add('funnelchat_done')
    logger.info('Lead %s: funnelchat_done', lead_id)


@shared_task(**RETRY_POLICY)
def process_vsl_activecampaign(self, lead_id, percent, region=None):
    """Escribe el % de VSL visto en ActiveCampaign (cada 10%).

    A diferencia del resto de tareas de este módulo no marca ningún tag *_done:
    se dispara una vez por cada tramo reportado, así que no la recoge el sweep.
    """
    from calendario.leads.models import Lead
    from calendario.leads.services import activecampaign

    lead = Lead.objects.get(pk=lead_id)
    activecampaign.push_vsl_percent(lead, percent, region)


@shared_task(**RETRY_POLICY)
def process_vsl_crm(self, email, vsl_key, percent):
    """Reenvía el hito de VSL al CRM.

    Salía con `requests.patch` dentro del request de `/f/api/video-progress/`,
    que es un ping cada 10% de vídeo: cuando el CRM tardaba, la petición del
    visitante se quedaba esperando hasta diez segundos y con ella uno de los
    tres workers de gunicorn (FUNNELS-5C, 121 read timeout en una semana). Ese
    dato no le urge a nadie, así que va por la cola como sus dos vecinos de la
    misma vista: el respaldo en Supabase y el % a ActiveCampaign.

    Ojo con `RETRY_POLICY`: aquí no reintenta nada. `push_vsl_progress` se traga
    los fallos —captura `RequestException` y de un 5xx solo deja un log—, así
    que la tarea nunca lanza y el reintento no llega a dispararse. Si algún día
    interesa que lo haga, hay que empezar por que esa función levante el error.
    """
    from calendario.leads.services import crm

    crm.push_vsl_progress(email, vsl_key, percent)


@shared_task(**RETRY_POLICY)
def process_neverbounce(self, lead_id):
    """PROVISIONAL: solo para vaciar la cola durante el despliegue.

    Ya no se encola (la validación del email es cosa de Relay), pero el color
    viejo pudo dejar mensajes pendientes. Hace lo que hacía al terminar —mandar a
    ActiveCampaign/puente y al CRM— sin validar nada. Se borra en el despliegue
    siguiente, junto con la migración que borra la columna.
    """
    from calendario.leads.models import Lead

    lead = Lead.objects.get(pk=lead_id)
    if not es_lead_de_lanzamiento(lead):
        process_activecampaign.delay(lead_id)
    process_crm_send.delay(lead_id)


@shared_task(**RETRY_POLICY)
def process_crm_send(self, lead_id):
    """Envía el Lead al CRM ingest. Gated por CRM_INGEST_ENABLED:
    mientras esté en False hace no-op (y el sweep no lo reintenta)."""
    if not settings.CRM_INGEST_ENABLED:
        logger.info('Lead %s: CRM send SKIPPED (CRM_INGEST_ENABLED=False)', lead_id)
        return

    from calendario.leads.models import Lead
    from calendario.leads.services import crm, geo

    lead = Lead.objects.get(pk=lead_id)
    # Geo por IP antes del envío (el funnel viejo mandaba city/country con el
    # lead). Best-effort: si geojs falla, el lead viaja sin geo igualmente.
    try:
        geo.enrich_lead(lead)
    except Exception:
        logger.exception('Lead %s: geo enrichment falló; se continúa sin geo', lead_id)
    enviado = crm.push_lead(lead)
    if not enviado:
        # Sin API key no ha salido nada. Se marca aparte para que el sweep lo
        # reintente cuando la key vuelva, en vez de darlo por enviado.
        lead.tags.add('crm_skipped')
        logger.warning('Lead %s: crm_skipped (sin API key)', lead_id)
        return
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


# ---------------------------------------------------------------------------
# Dispatch helper — called from the signal
# ---------------------------------------------------------------------------

from calendario.leads.services.utils import es_lead_de_lanzamiento  # noqa: F401


def dispatch_lead_tasks(lead_id):
    """Evaluate conditions and enqueue applicable service tasks for a lead."""
    from calendario.leads.models import Lead
    from calendario.leads.services.utils import fires_pixel_lead, is_from_meta, is_from_tiktok, is_from_google

    from calendario.leads.services.utils import get_school_code

    lead = Lead.objects.get(pk=lead_id)

    # Respaldo en Supabase: siempre, de cualquier lead (también los de evento),
    # independiente del origen y del CRM.
    process_supabase.delay(lead_id)

    # Los leads de evento van SOLO al CRM (el respaldo de arriba no es un envío). No es una decisión nueva: en el
    # escenario de Make esas ramas están apagadas y se ve en el log de
    # ejecuciones —un evento de Blocks consume 2 operaciones (webhook + CRM) y
    # uno de Languages con teléfono 3 (webhook + CRM + FunnelChat)—; si
    # salieran correos, Respond.io o las CAPI habría 5 o más, y no existe
    # ninguna ejecución por encima de 4.
    if es_lead_de_lanzamiento(lead):
        process_crm_send.delay(lead_id)
        # La única excepción es FunnelChat, y solo en Languages: en Make cuelga
        # de la rama de Languages, que filtra `funnel` por 'cl'. Los de Blocks
        # no tienen módulo, y los de Finance tampoco entran porque esa rama
        # filtra por 'fi' y sus códigos son 'cf-lanzamientoN'. Se ve en el log:
        # los lanzamientos de Languages con teléfono son los únicos que gastan
        # 4 operaciones (webhook + ingest + FunnelChat + Sheets), 1.467 de
        # 1.715; los de Blocks y Finance se quedan en 3.
        if get_school_code(lead) == 'cl' and lead.lead_phone:
            process_funnelchat.delay(lead_id)
        logger.info('Lead %s: lanzamiento → CRM (+FunnelChat si CL)', lead_id)
        return

    # Conquer Legal: Google Ads/TikTok los dispara el server container de sGTM
    # — empujarlos también por API los duplicaría. Meta sí va por API (el sGTM
    # no lo manda), con el token de su negocio (META_ACCESS_TOKEN_LEGAL).
    es_legal = get_school_code(lead) == 'cg'

    # Meta CAPI va para TODOS los leads de landings con pixel (cualquier fuente),
    # igual que el CRM viejo — no solo los de MetaAds (paridad y dedup del pixel).
    if fires_pixel_lead(lead) or is_from_meta(lead):
        process_meta_capi.delay(lead_id)
    if not es_legal and is_from_tiktok(lead):
        process_tiktok_events.delay(lead_id)
    if not es_legal and is_from_google(lead):
        process_google_ads.delay(lead_id)
    # Respond.io: las etiquetas de lead (lead-<ABBR>, <ABBR>, región) se asignan
    # al crear el lead, tenga teléfono o no. Si llega sin teléfono, el contacto se
    # crea por email y el número se reconcilia luego (prellamada/reserva).
    if lead.email:
        process_respondio.delay(lead_id)
        # Validar el email no es cosa del calendario: lo hace Relay al recibir
        # el contacto, y él decide si lo escribe en ActiveCampaign.
        process_activecampaign.delay(lead_id)
        process_crm_send.delay(lead_id)
        process_funnelchat.delay(lead_id)

    logger.info('Lead %s: dispatched processing tasks', lead_id)


# ---------------------------------------------------------------------------
# Periodic sweep — catches anything that failed after all retries
# ---------------------------------------------------------------------------

@shared_task
def sweep_incomplete_leads():
    """Re-encola tareas cuyo tag *_done falta (leads de las últimas 24 h, creados hace > 5 min)."""
    from calendario.leads.models import Lead
    from calendario.leads.services.utils import fires_pixel_lead, is_from_meta, is_from_tiktok, is_from_google

    now = timezone.now()
    cutoff_old = now - timedelta(hours=24)
    cutoff_recent = now - timedelta(minutes=5)

    leads = (
        Lead.objects
        .filter(created__gte=cutoff_old, created__lte=cutoff_recent)
        .prefetch_related('tags')
    )

    from calendario.leads.services.utils import get_school_code

    requeued = 0
    for lead in leads.iterator(chunk_size=200):
        # .all() reutiliza la caché de prefetch_related; .names() la descarta y
        # relanza un values_list por cada lead (N+1).
        tag_names = set(t.name for t in lead.tags.all())

        # Supabase: todos, también los de evento.
        if 'supabase_done' not in tag_names and 'supabase_failed' not in tag_names:
            process_supabase.delay(lead.pk)
            requeued += 1

        # Misma regla que dispatch_lead_tasks: los de evento solo van al CRM,
        # así que el sweep no debe reencolarles el resto de servicios.
        if es_lead_de_lanzamiento(lead):
            if (settings.CRM_INGEST_ENABLED and lead.email
                    and 'crm_done' not in tag_names and 'crm_failed' not in tag_names):
                process_crm_send.delay(lead.pk)
                requeued += 1
            if (get_school_code(lead) == 'cl' and lead.lead_phone
                    and 'funnelchat_done' not in tag_names):
                process_funnelchat.delay(lead.pk)
                requeued += 1
            continue

        # Mismo gate que dispatch_lead_tasks: Legal manda Meta por API;
        # Google Ads/TikTok van por el server container de sGTM.
        es_legal = get_school_code(lead) == 'cg'

        if (fires_pixel_lead(lead) or is_from_meta(lead)) and 'meta_capi_done' not in tag_names and 'meta_capi_failed' not in tag_names:
            process_meta_capi.delay(lead.pk)
            requeued += 1

        if not es_legal and is_from_tiktok(lead) and 'tiktok_events_done' not in tag_names and 'tiktok_events_failed' not in tag_names:
            process_tiktok_events.delay(lead.pk)
            requeued += 1

        if not es_legal and is_from_google(lead) and 'google_ads_done' not in tag_names and 'google_ads_failed' not in tag_names:
            process_google_ads.delay(lead.pk)
            requeued += 1

        if lead.email and 'respondio_done' not in tag_names and 'respondio_failed' not in tag_names:
            process_respondio.delay(lead.pk)
            requeued += 1

        if (lead.email and 'activecampaign_done' not in tag_names
                and 'activecampaign_failed' not in tag_names):
            process_activecampaign.delay(lead.pk)
            requeued += 1

        if lead.email and 'funnelchat_done' not in tag_names and 'funnelchat_failed' not in tag_names:
            process_funnelchat.delay(lead.pk)
            requeued += 1

        if (settings.CRM_INGEST_ENABLED and lead.email
                and 'crm_done' not in tag_names and 'crm_failed' not in tag_names):
            process_crm_send.delay(lead.pk)
            requeued += 1

    logger.info('[Sweep] Checked leads since %s, requeued %d tasks', cutoff_old, requeued)
    return requeued
