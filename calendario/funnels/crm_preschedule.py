"""Envío de la Prellamada al CRM ingest (equivalente a funnels
schedules/services/crm_preschedule.py, que opera sobre PreSchedule).

En conquer-calendar la `Prellamada` es el equivalente del PreSchedule: se crea
al terminar el formulario. El tracking (journey_id/event_id/UTMs) vive en
`Prellamada.tracking` (JSON).
"""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def push_pre_schedule(prellamada):
    """Envía los datos de la Prellamada al CRM ingest (upsert por journey_id)."""
    base_url = settings.CRM_BASE_URL.rstrip('/')
    url = f'{base_url}/api/v1/ingest/pre-schedule/'
    api_key = settings.CRM_API_KEY

    if not api_key:
        logger.warning('[CRM] No API key configured, skipping prellamada %s', prellamada.pk)
        return

    tracking = prellamada.tracking if isinstance(prellamada.tracking, dict) else {}
    journey_id = tracking.get('journey_id')
    if not journey_id:
        logger.warning('[CRM] Prellamada %s sin journey_id, skipping', prellamada.pk)
        return

    # Preferimos las columnas de la prellamada (snapshot); fallback al JSON
    # `tracking` para filas viejas creadas antes de promover los campos.
    def _trk(field):
        return getattr(prellamada, field, '') or tracking.get(field)

    # El CRM guarda las respuestas en campos q1_answer..q6_answer (NO acepta el
    # dict `respuestas`). Las mapeamos según el `q_order` del funnel.
    respuestas = prellamada.respuestas if isinstance(prellamada.respuestas, dict) else {}
    funnel_cfg = (prellamada.funnel.config or {}) if prellamada.funnel_id else {}
    q_order = funnel_cfg.get('q_order') or []

    def _answer(idx):
        if idx >= len(q_order):
            return None
        val = respuestas.get(q_order[idx])
        if isinstance(val, (list, tuple)):
            val = val[0] if val else None
        return str(val) if val not in (None, '') else None

    # Estado de agenda para el CRM (campo `assistance`):
    #   7 = Pendiente de agendar · 8 = Agendada · 6 = Cancelada por el sistema
    # El listado de prellamadas del CRM SOLO muestra las que tienen assistance=7;
    # sin este campo el ingest las crea con NULL y nunca aparecen (que era el caso
    # de Conquer Legal). Igual que conquerx-funnels: el form manda 7/6 y el CRM
    # promueve a 8 al vincular la reserva. Lo derivamos del estado de la Prellamada
    # para no pisar el 8 en los reenvíos posteriores a la reserva.
    if prellamada.reserva_id:
        assistance = 8
    elif prellamada.resultado == 'rechazado':
        assistance = 6
    else:
        assistance = 7

    payload = {
        # El ingest del CRM hace upsert del PreSchedule por `uuid` (campo
        # obligatorio). Usamos el token estable de la Prellamada como uuid: es
        # único por recorrido y no cambia entre el upsert intermedio y el final.
        'uuid': str(prellamada.token),
        'journey_id': journey_id,
        'event_id': _trk('event_id'),
        'lead_email': prellamada.email,
        'lead_name': prellamada.nombre,
        'lead_phone_number': prellamada.telefono,
        'call_register': prellamada.creado_en.isoformat() if prellamada.creado_en else None,
        'token': str(prellamada.token),
        'form': prellamada.funnel.key if prellamada.funnel_id else None,
        'resultado': prellamada.resultado,
        # Pendiente de agendar / Agendada / Cancelada — sin esto el CRM no la lista.
        'assistance': assistance,
        'lead_scoring_score': float(prellamada.score) if prellamada.score is not None else None,
        # Respuestas mapeadas a los campos que el CRM espera (q1..q6 según q_order).
        'q1_answer': _answer(0),
        'q2_answer': _answer(1),
        'q3_answer': _answer(2),
        'q4_answer': _answer(3),
        'q5_answer': _answer(4),
        'q6_answer': _answer(5),
        # UTMs (columna con fallback al tracking)
        'utm_source': _trk('utm_source'),
        'utm_campaign': _trk('utm_campaign'),
        'utm_medium': _trk('utm_medium'),
        'utm_term': _trk('utm_term'),
        'utm_content': _trk('utm_content'),
        'utm_idcampaign': _trk('utm_idcampaign'),
        'utm_adsetid': _trk('utm_adsetid'),
        'utm_adid': _trk('utm_adid'),
        'utm_form_variant': _trk('utm_form_variant'),
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    start = time.time()
    response = requests.post(
        url,
        json=payload,
        headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
        timeout=15,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    if response.status_code in (200, 201):
        logger.info(
            '[CRM] Prellamada %s sent successfully (%dms) — created=%s',
            prellamada.pk, elapsed_ms, response.status_code == 201,
        )
    else:
        logger.error(
            '[CRM] Prellamada %s failed (%dms) — status=%d response=%s',
            prellamada.pk, elapsed_ms, response.status_code, response.text[:500],
        )
        response.raise_for_status()
