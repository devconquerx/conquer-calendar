"""Adaptador Reserva → contexto 'schedule-like' para reutilizar la lógica de
conversiones de funnels (que opera sobre el modelo Schedule).

conquer-calendar no tiene Schedule: la `Reserva` es el equivalente. El tracking
y la PII enriquecida vienen del `Lead` enlazado (resuelto por journey_id/email)
y de la `Prellamada` asociada a la reserva.
"""
from types import SimpleNamespace

from calendario.leads.services.utils import (
    SCHOOL_SLUG_TO_CODE, FUNNEL_REGION_MAP, get_region_from_lead,
)


def find_lead_for_reserva(reserva, prellamada=None):
    """Encuentra el Lead más reciente por journey_id (de la prellamada) o por email."""
    from calendario.leads.models import Lead

    journey_id = ''
    if prellamada and isinstance(prellamada.tracking, dict):
        journey_id = prellamada.tracking.get('journey_id') or ''

    if journey_id:
        lead = Lead.objects.filter(journey_id=journey_id).order_by('-created').first()
        if lead:
            return lead

    email = reserva.email_invitado
    if email:
        return Lead.objects.filter(email=email).order_by('-created').first()

    return None


def _school_code_from_escuela(escuela):
    if not escuela:
        return None
    return SCHOOL_SLUG_TO_CODE.get(str(escuela).lower().strip())


def build_schedule_ctx(reserva):
    """Construye un SimpleNamespace con los atributos que esperan los servicios
    de conversión (portados de funnels/apps/schedules/services)."""
    prellamada = getattr(reserva, 'prellamada', None)
    lead = find_lead_for_reserva(reserva, prellamada)

    funnel = prellamada.funnel if prellamada else None
    escuela = funnel.escuela if funnel else (lead.school if lead else '')
    region_code = (funnel.region if funnel else '') or ''

    school_code = _school_code_from_escuela(escuela)
    if not school_code and lead:
        school_code = _school_code_from_escuela(lead.school)

    # Región: del lead si existe; si no, del campo region de la prellamada/funnel.
    if lead:
        region = get_region_from_lead(lead)
    else:
        region = FUNNEL_REGION_MAP.get(region_code.lower(), 'LATAM')

    tracking = prellamada.tracking if (prellamada and isinstance(prellamada.tracking, dict)) else {}

    host_email = getattr(getattr(reserva, 'host', None), 'email', '') or ''
    closer = host_email.split('@')[0] if host_email else ''

    s = SimpleNamespace()
    s.pk = reserva.pk
    s.lead = lead
    s.school_code = school_code
    s.region = region

    s.lead_email = reserva.email_invitado or ''
    s.lead_name = reserva.nombre_invitado or ''
    s.lead_phone_number = reserva.telefono_invitado or ''
    s.lead_country = (lead.lead_country or lead.country_name) if lead else ''

    s.call_register = reserva.fecha_creacion
    s.call_datetime = reserva.inicio_utc
    s.created = reserva.fecha_creacion

    # Preferimos el snapshot guardado en la propia reserva; fallback al Lead y al
    # tracking de la Prellamada (reservas viejas creadas antes del snapshot).
    s.event_id = reserva.event_id or (lead.event_id if lead else None) or tracking.get('event_id') or ''
    s.journey_id = reserva.journey_id or (lead.journey_id if lead else None) or tracking.get('journey_id') or ''
    s.page_url = (lead.page_url if lead else '') or ''

    s.setter = ''
    s.closer = closer
    s.closer_from_make = closer
    s.meet_join_url = reserva.google_meet_url or ''
    s.timezone_string = reserva.timezone_invitado or ''
    s.confirmation = None  # Reserva no tiene estados de confirmación de setter

    s.form = (funnel.key if funnel else '') or ''
    s.specialisation = ''
    s.lead_scoring_score = prellamada.score if prellamada else None
    s.lead_scoring_text = ''
    s.event = reserva.event_type.nombre if reserva.event_type_id else ''

    # Respuestas q1..q6: no hay mapeo fijo en conquer-calendar (CRM está disabled).
    for i in range(1, 7):
        setattr(s, f'q{i}_answer', None)

    # UTMs: snapshot de la reserva si lo tiene; si no, del lead; si no, del
    # tracking de la prellamada (para reservas viejas o sin Lead emparejado).
    for f in ('utm_source', 'utm_campaign', 'utm_medium', 'utm_term', 'utm_content',
              'utm_idcampaign', 'utm_adsetid', 'utm_adid'):
        val = getattr(reserva, f, None) or (getattr(lead, f, None) if lead else None) or tracking.get(f)
        setattr(s, f, val)
    s.utm_vsl = None
    s.utm_nuturing = None
    s.utm_form_length = None
    s.utm_form_variant = (
        getattr(reserva, 'utm_form_variant', None)
        or (getattr(lead, 'utm_form_variant', None) if lead else None)
        or tracking.get('utm_form_variant')
    )

    return s
