import logging

import requests
from django.conf import settings

from calendario.leads.services.activecampaign import ActiveCampaignClient
from .utils import build_schedule_ctx

logger = logging.getLogger(__name__)

# Puente de Relay (migración desde ActiveCampaign). Para las escuelas de RELAY_PUENTE_ESCUELAS la agenda se manda a
# Relay, que decide si atiende al contacto y escribe él mismo en AC (contacto, tag de agenda y relay-<automatización>).
# Si Relay falla, tarda más de RELAY_PUENTE_TIMEOUT o no responde 200, calendar etiqueta AC directamente (plan B).
# Contrato: relay/apps/puente_ac/README.md. Se quita cuando se apague AC (relay/docs/provisional-migracion-ac.md).
RELAY_PUENTE_TIMEOUT = 2

# Tag IDs por escuela para eventos Schedule (distintos de los tags lead funnel-region)
SCHEDULE_SCHOOL_TAG_MAP = {
    'cb': '460',   # Blocks
    'cf': '464',   # Finance
    'fi': '464',   # Finance
    'cl': '477',   # Languages
    'cg': '513',   # Legal
}


# Se mandan TODAS las escuelas: cuáles atiende el puente lo decide Relay en su .env (sin tocar ni reiniciar calendar).
# Una escuela no activada en Relay responde 404 y aquí se escribe en AC como siempre (plan B).
ESCUELAS_PUENTE = {'cb', 'cf', 'cl', 'cg'}


def _escuelas_puente():
    return ESCUELAS_PUENTE


def _registro_del_lead(lead, escuela, email):
    """Registro del lead de la reserva (funnel, nombre, UTM y si llegó a AC), para que Relay complete a quien se
    registró antes de activar el puente y agenda ahora. Solo si es el mismo email y la misma escuela que la agenda."""
    if lead is None or (lead.email or '').strip().lower() != (email or '').strip().lower():
        return None
    from calendario.leads.services.activecampaign import CUSTOM_FIELD_MAP, _escuela_relay, _funnel_key, get_school_code

    codigo = get_school_code(lead)
    if _escuela_relay(codigo) != escuela:
        return None
    etiquetas = set(lead.tags.names())
    return {'funnel': _funnel_key(lead, codigo) or '', 'nombre_completo': lead.full_name or '',
            'utm': {k: str(getattr(lead, k)) for k in CUSTOM_FIELD_MAP if getattr(lead, k, None)},
            'en_ac': bool(etiquetas & {'activecampaign_done', 'relay_puente_lead_done'})}


def push_relay(reserva, s=None):
    """Manda la agenda al puente de Relay. True si Relay la aceptó (200): entonces Relay escribe en AC.

    False si la escuela no está activada, Relay no está configurado o la llamada falla (el llamador hace el plan B)."""
    s = s or build_schedule_ctx(reserva)
    escuela = 'cf' if s.school_code == 'fi' else s.school_code
    url = (getattr(settings, 'RELAY_API_URL', '') or '').rstrip('/')
    clave = getattr(settings, 'RELAY_API_KEY', '') or ''
    if not s.lead_email or not escuela or escuela not in _escuelas_puente() or not url or not clave:
        return False
    datos = {'email': s.lead_email, 'nombre_completo': s.lead_name or '', 'escuela': escuela,
             'telefono': s.lead_phone_number or '', 'origen': 'calendar', 'reiniciar': False}
    if registro := _registro_del_lead(getattr(s, 'lead', None), escuela, s.lead_email):
        datos['registro'] = registro
    try:
        r = requests.post(f'{url}/api/v1/puente-ac/agenda', json=datos, timeout=RELAY_PUENTE_TIMEOUT,
                          headers={'Authorization': f'Bearer {clave}', 'Accept': 'application/json'})
    except requests.RequestException as e:
        logger.warning('[Relay] Reserva %s: puente no disponible (%s): plan B (AC directo)', reserva.pk, type(e).__name__)
        return False
    if r.status_code != 200:
        logger.warning('[Relay] Reserva %s: puente respondió %s: plan B (AC directo)', reserva.pk, r.status_code)
        return False
    try:
        relay = bool(r.json().get('relay'))
    except ValueError:
        relay = None
    logger.info('[Relay] Reserva %s: agenda %s enviada al puente (relay=%s)', reserva.pk, escuela, relay)
    return True


def push_schedule(reserva):
    """Sync schedule to ActiveCampaign: create/update contact and assign school tag.

    Para las escuelas de RELAY_PUENTE_ESCUELAS va primero por el puente de Relay; si falla, sigue como siempre."""
    if push_relay(reserva):
        reserva.tags.add('sch_relay_puente_done')
        return

    api_url = getattr(settings, 'ACTIVECAMPAIGN_API_URL', '')
    api_key = getattr(settings, 'ACTIVECAMPAIGN_API_KEY', '')
    if not api_url or not api_key:
        logger.warning('[ActiveCampaign] API not configured')
        return

    s = build_schedule_ctx(reserva)
    if not s.lead_email:
        return

    school_code = s.school_code
    client = ActiveCampaignClient()

    try:
        first_name = None
        if s.lead_name:
            first_name = s.lead_name.split()[0] if s.lead_name.strip() else None

        contact = client.create_or_update_contact(s.lead_email, first_name)
        if not contact:
            logger.warning('[ActiveCampaign] Reserva %s: failed to create/update contact', reserva.pk)
            return

        contact_id = contact.get('id')
        if not contact_id:
            return

        tag_id = SCHEDULE_SCHOOL_TAG_MAP.get(school_code)
        if tag_id:
            client.add_tag(contact_id, tag_id)

        logger.info('[ActiveCampaign] Reserva %s synced, contact_id=%s', reserva.pk, contact_id)

    except Exception as e:
        logger.error('[ActiveCampaign] Reserva %s error: %s', reserva.pk, e)
        raise
