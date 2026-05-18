import logging
import threading

import requests
from django.conf import settings
from django.utils import timezone

from .models import Reserva


logger = logging.getLogger(__name__)


def _payload_para_make(reserva: Reserva) -> dict:
    """
    Arma un payload con la misma estructura que devolvían en Make los módulos
    de Calendly (1: Watch Events, 25: Get Organization Membership). Así los
    mapeos del módulo PostgreSQL siguen apuntando a los mismos nombres de campo.
    """
    ahora_iso = timezone.now().isoformat()
    questions_and_answers = []
    if reserva.telefono_invitado:
        questions_and_answers.append({
            'question': 'Teléfono',
            'answer': reserva.telefono_invitado,
        })

    return {
        # Equivalente a "1.X" — datos del invitee + scheduled_event.
        'name': reserva.nombre_invitado,
        'email': reserva.email_invitado,
        'questions_and_answers': questions_and_answers,
        'scheduled_event': {
            'name': reserva.event_type.nombre,
            'start_time': reserva.inicio_utc.isoformat(),
            'end_time': reserva.fin_utc.isoformat(),
        },
        # Equivalente a "25.X" — Organization Membership del host.
        'created_at': ahora_iso,
        'event_memberships': [
            {'user_email': reserva.host.email},
        ],
    }


def _enviar_post(url: str, payload: dict, headers: dict, timeout: int) -> None:
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if response.status_code >= 400:
            logger.error(
                "notificar_crm: respuesta %s de Make. body=%s",
                response.status_code, response.text[:500],
            )
        else:
            logger.info("notificar_crm: webhook enviado (status=%s)", response.status_code)
    except requests.RequestException:
        logger.exception("notificar_crm: error enviando webhook a Make")


def notificar_crm(reserva_id: int) -> None:
    """
    Envía un POST al webhook de Make con los datos de la reserva. Se ejecuta
    en un thread daemon para no bloquear la response del booking. Si el
    webhook está caído o tarda, la reserva ya quedó creada igualmente.
    """
    url = getattr(settings, 'CRM_WEBHOOK_URL', '')
    if not url:
        logger.warning("notificar_crm: CRM_WEBHOOK_URL no configurado, salto envío.")
        return

    reserva = (Reserva.objects
               .select_related('event_type', 'host')
               .filter(pk=reserva_id)
               .first())
    if not reserva:
        logger.warning("notificar_crm: reserva %s no encontrada.", reserva_id)
        return

    payload = _payload_para_make(reserva)
    timeout = getattr(settings, 'CRM_WEBHOOK_TIMEOUT_SECONDS', 8)
    headers = {}
    api_key = getattr(settings, 'CRM_WEBHOOK_API_KEY', '')
    if api_key:
        headers['x-make-apikey'] = api_key

    threading.Thread(
        target=_enviar_post,
        args=(url, payload, headers, timeout),
        daemon=True,
    ).start()
