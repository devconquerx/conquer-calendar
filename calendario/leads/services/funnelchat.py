import logging

import requests

from .utils import get_school_code

logger = logging.getLogger(__name__)

# Triggers de "Flows" de FunnelChat (flows-api.funnelchat.app) por escuela.
# Cada trigger dispara un flow configurado en el dashboard de FunnelChat que
# manda el correo de bienvenida ("Aquí tienes la clase que me pediste") y crea
# el contacto en su inbox de WhatsApp. Antes esto lo disparaba un módulo HTTP
# en el Make.com del funnel viejo (escenario "Formularios de Embudos" — los
# módulos de email directo ahí están desactivados; el único camino activo es
# este webhook). Por ahora solo Finance está confirmado/urgente; Languages
# tiene un trigger conocido (7db0da3a-27df-4ae9-919a-0beabc5b1250) pero sin
# confirmar, así que no se activa todavía. Blocks no tiene trigger en el Make
# viejo (todos sus caminos de email también están desactivados).
SCHOOL_FUNNELCHAT_TRIGGER = {
    'cf': 'https://flows-api.funnelchat.app/api/v1/users/3231/triggers/db9c763c-6af4-4119-b953-ff238b87a321',
    'fi': 'https://flows-api.funnelchat.app/api/v1/users/3231/triggers/db9c763c-6af4-4119-b953-ff238b87a321',
}


def push_lead(lead):
    """Dispara el flow de bienvenida de FunnelChat (email + WhatsApp) para el lead.

    Réplica del módulo HTTP del Make viejo: mismos campos (name/email/phone) y
    misma condición (solo si el lead tiene teléfono)."""
    school_code = get_school_code(lead)
    url = SCHOOL_FUNNELCHAT_TRIGGER.get(school_code)
    if not url:
        logger.info('[FunnelChat] Lead %s: escuela %s sin trigger, skip', lead.pk, school_code)
        return

    if not lead.lead_phone:
        logger.info('[FunnelChat] Lead %s: sin teléfono, skip (mismo filtro que el Make viejo)', lead.pk)
        return

    if not lead.email:
        logger.warning('[FunnelChat] Lead %s: sin email, skip', lead.pk)
        return

    phone = f'{lead.lead_phone_prefix or ""}{lead.lead_phone}'.strip()
    payload = {
        'name': lead.full_name or '',
        'email': lead.email,
        'phone': phone,
    }

    response = requests.post(url, json=payload, timeout=15)
    if response.status_code == 200:
        logger.info('[FunnelChat] Lead %s synced (%s)', lead.pk, school_code)
    else:
        logger.warning(
            '[FunnelChat] Lead %s failed — status=%d response=%s',
            lead.pk, response.status_code, response.text[:300],
        )
        response.raise_for_status()
