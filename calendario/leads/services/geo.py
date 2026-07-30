"""Geo-enriquecimiento del Lead por IP (paridad con el funnel viejo).

conquerx-funnels-new resolvía la geo EN EL NAVEGADOR (geojs.io / ipapi.co) y la
mandaba junto con el lead; por eso los LeadRegister del CRM viejos traen
city/country_code/country_name. Aquí se resuelve server-side desde
Lead.ip_address con geojs.io (gratuito, sin API key — el mismo proveedor que
usaba el proyecto viejo), justo antes del envío al CRM.
"""
import logging

import requests

logger = logging.getLogger(__name__)

GEOJS_URL = 'https://get.geojs.io/v1/ip/geo/{ip}.json'


def enrich_lead(lead):
    """Rellena country_code/country_name/city desde la IP si están vacíos.

    Best-effort: cualquier fallo se loguea y se sigue sin geo (nunca bloquea
    el envío al CRM). Devuelve True si guardó algo.
    """
    if lead.country_code or not lead.ip_address:
        return False
    try:
        resp = requests.get(GEOJS_URL.format(ip=lead.ip_address), timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning('Lead %s: geo lookup falló (%s)', lead.pk, exc)
        return False

    updates = []
    for field, key in (
        ('country_code', 'country_code'),
        ('country_name', 'country'),
        ('city', 'city'),
    ):
        value = (data.get(key) or '').strip()
        if value:
            setattr(lead, field, value)
            updates.append(field)
    if updates:
        lead.save(update_fields=updates)
        logger.info('Lead %s: geo %s', lead.pk, ', '.join(updates))
    return bool(updates)
