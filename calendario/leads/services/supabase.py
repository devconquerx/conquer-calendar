"""Respaldo del Lead en Supabase (espejo de leads/services/crm.py:push_lead).

Captura los mismos campos que se envían al CRM, más `source_id` (PK del Lead,
clave de idempotencia) y `created_at`. Independiente del CRM: se encola al crear
el Lead, así el respaldo funciona aunque el envío al CRM esté desactivado.
"""
import logging

from django.conf import settings

from calendario.core import supabase

logger = logging.getLogger(__name__)


def _row_from_lead(lead):
    row = {
        'source_id': lead.pk,
        'created_at': lead.created.isoformat() if lead.created else None,
        'email': lead.email,
        'full_name': lead.full_name,
        'last_name': lead.last_name,
        'lead_phone': lead.lead_phone,
        'lead_phone_prefix': lead.lead_phone_prefix,
        'lead_country': lead.lead_country,
        'date_submitted': lead.date_submitted.isoformat() if lead.date_submitted else None,
        'ip_address': lead.ip_address,
        'page_url': lead.page_url,
        'funnel': lead.funnel,
        'school': lead.school,
        'product': lead.product,
        # UTMs
        'utm_source': lead.utm_source,
        'utm_campaign': lead.utm_campaign,
        'utm_medium': lead.utm_medium,
        'utm_content': lead.utm_content,
        'utm_term': lead.utm_term,
        'utm_idcampaign': lead.utm_idcampaign,
        'utm_adsetid': lead.utm_adsetid,
        'utm_adid': lead.utm_adid,
        'utm_form_variant': lead.utm_form_variant,
        'utm_title': lead.utm_title,
        'utm_vsl': lead.utm_vsl,
        # Click IDs
        'gclid': lead.gclid,
        'gbraid': lead.gbraid,
        'wbraid': lead.wbraid,
        'fbclid': lead.fbclid,
        'msclkid': lead.msclkid,
        'dclid': lead.dclid,
        'ttclid': lead.ttclid,
        'gclsrc': lead.gclsrc,
        # Tracking
        'event_id': lead.event_id,
        'journey_id': lead.journey_id,
        'recaptcha_score': float(lead.recaptcha_score) if lead.recaptcha_score is not None else None,
        'user_agent': lead.user_agent,
        # Geo
        'country_code': lead.country_code,
        'country_name': lead.country_name,
        'city': lead.city,
        'is_proxy': lead.is_proxy,
        # NeverBounce result (jsonb)
        'neverbounce_result': lead.neverbounce_result,
    }
    return {k: v for k, v in row.items() if v is not None}


def push_lead(lead):
    """Upsert del Lead en la tabla de respaldo de Supabase (idempotente por source_id)."""
    supabase.insert_rows(
        settings.SUPABASE_TABLE_LEADS,
        [_row_from_lead(lead)],
        on_conflict='source_id',
    )
