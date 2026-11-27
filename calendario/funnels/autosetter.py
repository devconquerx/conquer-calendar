"""Closers sin setter: sus leads de LATAM confirman la llamada por WhatsApp.

La lista vive en el CRM (Configuración > Closers para autosetter). Se pide al
reservar y se guarda unos minutos en caché para no llamar al CRM en cada
reserva. Si el CRM no responde se usa la última lista buena; sin ninguna, nadie
ve la página de WhatsApp (sale la confirmación de siempre).
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = 'crm_autosetter_closers'
CACHE_KEY_ULTIMA = 'crm_autosetter_closers_ultima'
CACHE_SEGUNDOS = 5 * 60
TIMEOUT_SEGUNDOS = 3

# Regiones del funnel en las que se pide confirmar por WhatsApp
REGIONES = {'latam'}


def emails_sin_setter():
    """Emails (en minúsculas) de los closers sin setter, según el CRM."""
    emails = cache.get(CACHE_KEY)
    if emails is not None:
        return set(emails)

    api_key = getattr(settings, 'CRM_API_KEY', '')
    if not api_key:
        return set()

    url = f"{settings.CRM_BASE_URL.rstrip('/')}/api/v1/ingest/autosetter-closers/"
    try:
        response = requests.get(url, headers={'X-API-Key': api_key}, timeout=TIMEOUT_SEGUNDOS)
        response.raise_for_status()
        emails = [e.strip().lower() for e in response.json().get('emails', []) if e]
    except (requests.RequestException, ValueError, AttributeError) as exc:
        logger.warning('[CRM] No se pudo leer la lista de closers sin setter: %s', exc)
        return set(cache.get(CACHE_KEY_ULTIMA) or [])

    cache.set(CACHE_KEY, emails, CACHE_SEGUNDOS)
    cache.set(CACHE_KEY_ULTIMA, emails, None)
    return set(emails)


def confirmar_por_whatsapp(funnel, reserva):
    """True si este lead tiene que confirmar la llamada por WhatsApp."""
    if funnel is None or (funnel.region or '').lower() not in REGIONES:
        return False
    host_email = (getattr(reserva.host, 'email', '') or '').strip().lower()
    return bool(host_email) and host_email in emails_sin_setter()
