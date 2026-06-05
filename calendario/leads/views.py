import json
import logging
import re

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
