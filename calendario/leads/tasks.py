import logging
import os
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


# El sondeo SMTP pregunta a Gmail si el buzón existe, y Gmail corta la IP si se
# le pregunta demasiado seguido (nos pasó: 421 tras ~1.500 sondeos en 20 min).
# El caudal normal de leads son ~3/min, pero hay ráfagas de campaña de hasta 27
# en un minuto, así que sin freno una ráfaga bastaría para quemar la IP.
#
# `rate_limit` es por worker node y aquí solo hay uno, así que actúa de límite
# global: las ráfagas se reparten en el tiempo en vez de salir de golpe. Se
# puede subir por entorno sin tocar código si vemos que la cola se acumula.
NEVERBOUNCE_RATE_LIMIT = os.environ.get('EMAIL_VERIFIER_RATE_LIMIT', '6/m')


@shared_task(rate_limit=NEVERBOUNCE_RATE_LIMIT, **RETRY_POLICY)
def process_neverbounce(self, lead_id):
    from calendario.leads.models import Lead
    from calendario.leads.services import email_validation

    lead = Lead.objects.get(pk=lead_id)

    # La validación es enriquecimiento opcional: NO debe bloquear el envío al
    # CRM. Si no está configurada o falla, se continúa sin resultado.
    #
    # Desde el sondeo SMTP propio esto ya casi nunca depende de NeverBounce,
    # pero el contrato de la tarea no cambia: rellena `neverbounce_result` y
    # marca el mismo tag de siempre.
    if not lead.neverbounce_result:
        try:
            email_validation.validate_email(lead)
            lead.refresh_from_db(fields=['neverbounce_result'])
        except Exception as exc:
            # Aquí ya no llegan los timeouts de lectura ni los vetos del
            # proveedor (el servicio los registra como 'unknown' y no relanza),
            # sino los fallos transitorios de verdad: conexión caída, 5xx,
            # respuesta ilegible. Esos sí merecen reintento, porque la siguiente
            # vez pueden funcionar.
            #
            # Sólo se reporta como error cuando se agotan los intentos: antes se
            # logueaba uno por intento, así que un único lead generaba hasta
            # cuatro eventos en Sentry aunque el reintento acabara bien.
            if self.request.retries < self.max_retries:
                logger.warning(
                    'Lead %s: validación de email falló (intento %s de %s), se reintenta: %s',
                    lead_id, self.request.retries + 1, self.max_retries + 1, exc,
                )
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                logger.exception(
                    'Lead %s: la validación agotó los reintentos; se continúa sin '
                    'validación (el CRM lo reintentará al recibir el lead sin '
                    'neverbounce_result)', lead_id,
                )

    if lead.neverbounce_result:
        lead.tags.add('neverbounce_done')
        logger.info('Lead %s: neverbounce_done', lead_id)
    else:
        lead.tags.add('neverbounce_skipped')
        logger.info('Lead %s: neverbounce_skipped (sin validación)', lead_id)

    # Con el veredicto en la mano ya se puede decidir sobre ActiveCampaign.
    # Solo se frena cuando el servidor de correo ha dicho que ese buzón no
    # existe: cualquier duda (catch-all, timeout, proveedor que no nos habla)
    # deja pasar el lead, porque perder uno bueno cuesta más que colar uno malo.
    nb = lead.neverbounce_result or {}
    if es_lead_de_lanzamiento(lead):
        # De los de evento se encarga el CRM de punta a punta (etiquetas,
        # conversiones y ActiveCampaign), igual que cuando los mandaba Make.
        # Aquí solo se les añade el veredicto para que pueda decidir.
        pass
    elif nb.get('is_rejected'):
        lead.tags.add('activecampaign_skipped')
        logger.info(
            'Lead %s: ActiveCampaign OMITIDO — %s dice que el buzón no existe (%s)',
            lead_id, nb.get('source', '?'), nb.get('reason', nb.get('result')),
        )
    else:
        process_activecampaign.delay(lead_id)

    # El envío al CRM se dispara siempre (la validación viaja si está disponible).
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

    # Los leads de evento van SOLO al CRM. No es una decisión nueva: en el
    # escenario de Make esas ramas están apagadas y se ve en el log de
    # ejecuciones —un evento de Blocks consume 2 operaciones (webhook + CRM) y
    # uno de Languages con teléfono 3 (webhook + CRM + FunnelChat)—; si
    # salieran correos, Respond.io o las CAPI habría 5 o más, y no existe
    # ninguna ejecución por encima de 4. Tampoco pasan por NeverBounce: Make
    # postea directo al ingest y es el CRM quien valida el email.
    if es_lead_de_lanzamiento(lead):
        # Van al CRM validados. El CRM decide con `neverbounce_result` si el
        # lead entra en ActiveCampaign, y por sí solo no tiene forma de
        # averiguarlo: su IP está vetada en Gmail, así que si no le llega el
        # veredicto desde aquí se queda sin ninguno. `process_neverbounce`
        # encadena el envío al CRM al terminar.
        if lead.email:
            process_neverbounce.delay(lead_id)
        else:
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

    # Respaldo en Supabase: siempre, independiente del origen y del CRM.
    process_supabase.delay(lead_id)

    # Conquer Legal NO usa la API directa de conversiones: las suyas las
    # dispara el server container de sGTM (tags Google Ads/Meta del contenedor
    # de Legal) — empujarlas también por API las duplicaría. El resto de
    # marcas replica el push por API que hacía el CRM con el funnel viejo.
    es_legal = get_school_code(lead) == 'cg'

    # Meta CAPI va para TODOS los leads de landings con pixel (cualquier fuente),
    # igual que el CRM viejo — no solo los de MetaAds (paridad y dedup del pixel).
    if not es_legal and (fires_pixel_lead(lead) or is_from_meta(lead)):
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
        # ActiveCampaign ya no sale aquí: lo encadena process_neverbounce cuando
        # sabe si el email existe. Meter una dirección inexistente en AC es un
        # rebote duro asegurado, y el umbral que no se puede pasar es el 2%.
        process_neverbounce.delay(lead_id)
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

        # Mismo gate que dispatch_lead_tasks: Legal no usa la API directa de
        # conversiones (van por el server container de sGTM).
        es_legal = get_school_code(lead) == 'cg'

        if 'supabase_done' not in tag_names and 'supabase_failed' not in tag_names:
            process_supabase.delay(lead.pk)
            requeued += 1

        if not es_legal and (fires_pixel_lead(lead) or is_from_meta(lead)) and 'meta_capi_done' not in tag_names and 'meta_capi_failed' not in tag_names:
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
                and 'activecampaign_failed' not in tag_names
                and 'activecampaign_skipped' not in tag_names
                and not es_lead_de_lanzamiento(lead)):
            # Se repite aquí la decisión de process_neverbounce en vez de exigir
            # que la validación haya terminado: si el verificador se atasca, un
            # lead sin veredicto entra en AC igualmente en la siguiente pasada.
            # El sweep es la red que impide que un fallo nuestro deje leads sin
            # enviar, no otro sitio donde puedan quedarse atrapados.
            if (lead.neverbounce_result or {}).get('is_rejected'):
                lead.tags.add('activecampaign_skipped')
            else:
                process_activecampaign.delay(lead.pk)
                requeued += 1

        if lead.email and 'funnelchat_done' not in tag_names and 'funnelchat_failed' not in tag_names:
            process_funnelchat.delay(lead.pk)
            requeued += 1

        if (lead.email and 'neverbounce_done' not in tag_names
                and 'neverbounce_skipped' not in tag_names
                and 'neverbounce_failed' not in tag_names):
            process_neverbounce.delay(lead.pk)
            requeued += 1

        if (settings.CRM_INGEST_ENABLED and lead.email
                and ('neverbounce_done' in tag_names or 'neverbounce_skipped' in tag_names)
                and 'crm_done' not in tag_names and 'crm_failed' not in tag_names):
            process_crm_send.delay(lead.pk)
            requeued += 1

    logger.info('[Sweep] Checked leads since %s, requeued %d tasks', cutoff_old, requeued)
    return requeued
