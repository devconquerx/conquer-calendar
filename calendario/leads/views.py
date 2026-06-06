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
    'lead_phone', 'lead_phone_prefix', 'lead_country',
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
    # Other
    'page_url', 'funnel', 'school', 'product', 'conditions',
]

_FIELD_MAX_LENGTHS = {}
for f in Lead._meta.get_fields():
    if hasattr(f, 'max_length') and f.max_length:
        _FIELD_MAX_LENGTHS[f.name] = f.max_length


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

    brand_field = _VSL_FIELD_POR_ESCUELA.get(school)
    brand_updated = False
    if brand_field and percent > (getattr(lead, brand_field) or 0):
        setattr(lead, brand_field, percent)
        update_fields.append(brand_field)
        brand_updated = True

    if update_fields:
        lead.save(update_fields=update_fields)

    # Reenvía el progreso al CRM (réplica de funnels: reemplaza el webhook de Make).
    if brand_updated:
        _patch_vsl_progress_to_crm(email, brand_field, percent)

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
