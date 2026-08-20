import json
import logging
import re

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Lead

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
MAX_BODY_SIZE = 32 * 1024  # 32 KB

# Campos que mapean directamente del payload al modelo Lead
DIRECT_FIELDS = [
    'email', 'original_email', 'full_name', 'last_name',
    'lead_phone', 'lead_phone_prefix', 'lead_country', 'wants_whatsapp',
    # UTMs
    'utm_source', 'utm_campaign', 'utm_medium', 'utm_content', 'utm_term',
    'utm_idcampaign', 'utm_adsetid', 'utm_adid',
    'utm_form_variant', 'utm_title', 'utm_vsl',
    # Click IDs
    'gclid', 'gbraid', 'wbraid', 'fbclid', 'msclkid', 'dclid', 'ttclid', 'gclsrc',
    # Pixel cookies
    '_fbp', '_fbc', '_ttp', '_ga', '_gid',
    # Tracking
    'event_id', 'journey_id', 'user_agent',
    # IPv6 resuelta en cliente: el servidor solo ve la IPv4 de Cloudflare.
    'ipv6_address',
    # Other
    'page_url', 'funnel', 'school', 'product', 'conditions',
]

_FIELD_MAX_LENGTHS = {}
for f in Lead._meta.get_fields():
    if hasattr(f, 'max_length') and f.max_length:
        _FIELD_MAX_LENGTHS[f.name] = f.max_length


# FunnelForm.slug (canónico del calendario) → código de funnel del CRM
# (vocabulario del proyecto viejo: cb/fi/cl/cg-<region>). Es lo que se guarda
# en Lead.funnel y viaja al ingest del CRM, a AC y a Respond.io. Sin entrada
# aquí (especialización) se conserva el slug tal cual.
#
# OJO con dejar un slug sin traducir: el ingest del CRM, en
# `_normalize_lead_funnel`, SUSTITUYE por el utm_campaign cualquier funnel que
# no esté en su STANDARD_LEAD_FUNNELS. Un lead de kids llegaba con
# 'languages-kids-eu' y se guardaba con el nombre de la campaña como funnel.
_FUNNEL_SLUG_TO_CRM_CODE = {
    'blocks-latam': 'cb-latam', 'blocks-eu': 'cb-eu', 'blocks-us': 'cb-us', 'blocks-eu-2': 'cb-eu-2',
    'finance-latam': 'fi-latam', 'finance-eu': 'fi-eu', 'finance-us': 'fi-us',
    'languages-latam': 'cl-latam', 'languages-eu': 'cl-eu', 'languages-us': 'cl-us',
    'languages-kids-latam': 'cl-kids-latam', 'languages-kids-eu': 'cl-kids-eu',
    'languages-kids-us': 'cl-kids-us',
    'legal-eu': 'cg-eu',
}


def _truncate_fields(fields):
    for key, value in fields.items():
        if isinstance(value, str) and key in _FIELD_MAX_LENGTHS:
            fields[key] = value[:_FIELD_MAX_LENGTHS[key]]


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


@csrf_exempt
@require_POST
def register_lead(request):
    if len(request.body) > MAX_BODY_SIZE:
        return JsonResponse({'error': 'Payload too large'}, status=413)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = data.get('email', '').strip()
    if not email:
        return JsonResponse({'error': 'email is required'}, status=400)
    if not EMAIL_RE.match(email):
        return JsonResponse({'error': 'Invalid email format'}, status=400)
    data['email'] = email

    # Mapear nombres del frontend a campos del modelo
    if 'name' in data and 'full_name' not in data:
        data['full_name'] = data['name']
    if 'escuela' in data and 'school' not in data:
        data['school'] = data['escuela']
    if 'form_key' in data and 'funnel' not in data:
        data['funnel'] = data['form_key']
    if 'url' in data and 'page_url' not in data:
        data['page_url'] = data['url']

    # Normalizar el funnel: si llega el `key` del FunnelForm (p.ej. 'LegalEu'),
    # se resuelve primero a su slug ('legal-eu'), y después el slug se traduce
    # al código de funnel del vocabulario del CRM (cb/fi/cl/cg-<region>, el del
    # proyecto viejo de funnels). El CRM indexa TODO por esos códigos
    # (FUNNEL_TAG_MAPPING, STANDARD_LEAD_FUNNELS, guardas de deduplicación como
    # `funnel == 'cg-eu'`): mandar el slug largo ('finance-latam') deja al lead
    # sin tag/lista y fuera de los listados de setters.
    if data.get('funnel'):
        from calendario.funnels.models import FunnelForm
        ff = FunnelForm.objects.filter(key=data['funnel']).only('slug').first()
        if ff and ff.slug:
            data['funnel'] = ff.slug
        data['funnel'] = _FUNNEL_SLUG_TO_CRM_CODE.get(data['funnel'], data['funnel'])

    fields = {}
    for field in DIRECT_FIELDS:
        if field in data and data[field]:
            fields[field] = data[field]

    _truncate_fields(fields)

    fields['ip_address'] = _get_client_ip(request)
    fields['date_submitted'] = timezone.now()

    lead = Lead.objects.create(**fields)

    return JsonResponse({'status': 'ok', 'id': lead.id})


# Escuela (slug) → campo VSL por marca en el modelo Lead.
_VSL_FIELD_POR_ESCUELA = {
    'conquer-blocks': 'vsl_percent_cb',
    'conquerblocks': 'vsl_percent_cb',
    'conquer-languages': 'vsl_percent_cl',
    'conquerlanguages': 'vsl_percent_cl',
    'conquer-finance': 'vsl_percent_cf',
    'conquerfinance': 'vsl_percent_cf',
}

# Hitos VSL aceptados por el CRM (IngestVslProgressView.VALID_PERCENTS). El campo
# por marca (vsl_percent_cb/cl/cf) refleja exactamente el del CRM, así que solo
# guarda/reenvía estos valores; cualquier otro % el CRM lo rechazaría con 400.
_VSL_MILESTONES = (25, 50, 75, 100)


def _vsl_milestone(percent):
    """Trunca el % al hito VSL inferior aceptado por el CRM (25/50/75/100).

    Devuelve None si todavía no se alcanza el primer hito (< 25).
    """
    milestone = None
    for m in _VSL_MILESTONES:
        if percent >= m:
            milestone = m
    return milestone


@csrf_exempt
@require_POST
def video_progress(request):
    """POST /f/api/video-progress/ — actualiza el % visto del video en el Lead.

    Fire-and-forget desde la página de video (cada 10%). Busca el Lead más
    reciente por email y guarda el máximo entre el valor actual y el reportado
    (nunca decrece). Devuelve 200 aunque no haya Lead, para no romper el flujo.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = (data.get('email') or '').strip()
    try:
        percent = int(data.get('percent') or 0)
    except (TypeError, ValueError):
        percent = 0
    school = (data.get('school') or '').strip()
    region = (data.get('region') or '').strip()

    if not email or percent <= 0:
        return JsonResponse({'status': 'skipped'})

    percent = max(0, min(percent, 100))

    lead = Lead.objects.filter(email__iexact=email).order_by('-created').first()
    if lead is None:
        return JsonResponse({'status': 'no_lead'})

    update_fields = []
    if percent > (lead.vsl_percentage or 0):
        lead.vsl_percentage = percent
        update_fields.append('vsl_percentage')

    # Campo por marca (cb/cl/cf): igual que el CRM, solo guarda hitos
    # 25/50/75/100 y nunca decrece.
    brand_field = _VSL_FIELD_POR_ESCUELA.get(school)
    milestone = _vsl_milestone(percent)
    milestone_to_send = None
    if brand_field and milestone and milestone > (getattr(lead, brand_field) or 0):
        setattr(lead, brand_field, milestone)
        update_fields.append(brand_field)
        milestone_to_send = milestone

    if update_fields:
        lead.save(update_fields=update_fields)
        # Re-respalda el Lead en Supabase con el VSL actualizado (la señal solo
        # corre al crear, así que el update del % no lo cubre). Upsert por
        # source_id: converge al último estado. Fire-and-forget.
        try:
            from .tasks import process_supabase
            process_supabase.delay(lead.pk)
        except Exception:
            logger.exception('No se pudo re-encolar Supabase para lead %s (vsl)', lead.pk)

    # Reenvía el progreso del VSL al CRM ingest (mismo hito y campo que guardamos).
    if milestone_to_send:
        _patch_vsl_progress_to_crm(email, brand_field, milestone_to_send)

    # ActiveCampaign, campo por marca+región. Sustituye al POST que la página de
    # vídeo hacía desde el navegador a video-progress-tracker.php: mismo destino
    # y misma cadencia (cada 10%, de ahí que vaya fuera del `if milestone`), pero
    # desde el servidor, sin exponer un endpoint sin autenticar ni depender de
    # que el navegador del usuario no lo bloquee.
    try:
        from .tasks import process_vsl_activecampaign
        process_vsl_activecampaign.delay(lead.pk, percent, region)
    except Exception:
        logger.exception('No se pudo encolar el %% de VSL a ActiveCampaign para lead %s', lead.pk)

    return JsonResponse({'status': 'ok'})


def _patch_vsl_progress_to_crm(email, vsl_key, percent):
    """PATCH del progreso de video al CRM ingest (fire-and-forget).

    Fail-safe: si no hay CRM_API_KEY configurada, hace no-op y loguea (no rompe
    el flujo). Réplica de funnels/apps/leads/views.py:_patch_vsl_progress_to_crm.
    """
    api_key = getattr(settings, 'CRM_API_KEY', '')
    if not api_key:
        logger.warning('[CRM] No API key configured, skipping vsl-progress PATCH')
        return

    base_url = getattr(settings, 'CRM_BASE_URL', '').rstrip('/')
    url = f'{base_url}/api/v1/ingest/lead-register/vsl-progress/'

    payload = {
        'email': email,
        'vsl_percent_cb': None,
        'vsl_percent_cl': None,
        'vsl_percent_cf': None,
    }
    payload[vsl_key] = percent

    try:
        response = requests.patch(
            url,
            json=payload,
            headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
            timeout=10,
        )
        if response.status_code in (200, 201):
            logger.info('[CRM] vsl-progress PATCH ok for %s (%s=%s)', email, vsl_key, percent)
        else:
            logger.error(
                '[CRM] vsl-progress PATCH failed — status=%d response=%s',
                response.status_code, response.text[:500],
            )
    except requests.RequestException as exc:
        logger.error('[CRM] vsl-progress PATCH error: %s', exc)
