import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

COOLDOWN_MINUTES = 30

# Mínimo esperado por hora (UTC). Si el conteo de la última hora cae por debajo
# → alerta de volumen degradado. (Réplica de funnels; ajustar a datos reales.)
HOURLY_MIN_LEADS = {
    0: 25, 1: 30, 2: 30, 3: 25, 4: 20,
    5: 15, 6: 15, 7: 15, 8: 10, 9: 15,
    10: 15, 11: 30, 12: 40, 13: 40, 14: 40,
    15: 40, 16: 35, 17: 35, 18: 25, 19: 35,
    20: 35, 21: 35, 22: 30, 23: 35,
}

HOURLY_MIN_PRELLAMADAS = {
    0: 5, 1: 5, 2: 5, 3: 5, 4: 4,
    5: 4, 6: 4, 7: 3, 8: 3, 9: 3,
    10: 4, 11: 5, 12: 8, 13: 10, 14: 10,
    15: 10, 16: 8, 17: 10, 18: 10, 19: 8,
    20: 8, 21: 8, 22: 8, 23: 8,
}

HOURLY_MIN_RESERVAS = {
    0: 2, 1: 2, 2: 2, 3: 2, 4: 2,
    5: 1, 6: 1, 7: 1, 8: 1, 9: 2,
    10: 2, 11: 2, 12: 3, 13: 3, 14: 3,
    15: 3, 16: 3, 17: 3, 18: 3, 19: 2,
    20: 2, 21: 2, 22: 2, 23: 2,
}


def _should_alert(metric):
    """Respeta cooldown: True si no se mandó alerta de esta métrica en los últimos COOLDOWN_MINUTES."""
    from .models import AlertLog

    cutoff = timezone.now() - timedelta(minutes=COOLDOWN_MINUTES)
    return not AlertLog.objects.filter(metric=metric, created__gte=cutoff).exists()


def _record_and_send(metric, subject, body):
    """Registra la alerta y la envía por email, respetando el cooldown.

    Las alertas se repiten cada COOLDOWN_MINUTES mientras la condición persista.
    """
    # AlertLog.metric tiene max_length=50; truncamos para no romper el create.
    metric = (metric or '')[:50]

    if not _should_alert(metric):
        logger.info('[Monitoring] Salto %s (cooldown, re-check en %d min)', metric, COOLDOWN_MINUTES)
        return

    from .models import AlertLog
    from .alerts import send_alert_email

    AlertLog.objects.create(metric=metric, message=body)
    logger.warning('[Monitoring] ALERT: %s', subject)

    try:
        send_alert_email(subject, body)
    except Exception:
        logger.exception('[Monitoring] Falló el envío de alerta para %s', metric)


@shared_task
def check_funnel_health():
    """Chequeo periódico (cada 5 min vía Celery Beat). Gated por MONITORING_ENABLED.

    - 0 leads en los últimos 5 min
    - 0 prellamadas en los últimos 15 min
    - 0 reservas en los últimos 20 min
    - 5+ leads con tareas Celery incompletas (sin tag crm_done, creados hace 5-60 min)
    """
    from django.conf import settings

    if not getattr(settings, 'MONITORING_ENABLED', False):
        logger.info('[Monitoring] Deshabilitado (MONITORING_ENABLED=false)')
        return

    from calendario.leads.models import Lead
    from calendario.funnels.models import Prellamada
    from calendario.bookings.models import Reserva

    now = timezone.now()

    zero_checks = [
        ('leads_zero', Lead, 'created', 5),
        ('prellamadas_zero', Prellamada, 'creado_en', 15),
        ('reservas_zero', Reserva, 'fecha_creacion', 20),
    ]

    for metric, model, field, minutes in zero_checks:
        cutoff = now - timedelta(minutes=minutes)
        count = model.objects.filter(**{f'{field}__gte': cutoff}).count()
        if count == 0:
            _record_and_send(
                metric,
                f'URGENTE: 0 {model.__name__} en {minutes} min',
                f'{model.__name__} count = 0 desde {cutoff:%H:%M UTC}.\n'
                f'Verificar: landing pages, Celery workers (docker ps), Redis broker, APIs externas.\n'
                f'Hora del check: {now:%Y-%m-%d %H:%M:%S UTC}',
            )
        else:
            logger.info('[Monitoring] %s OK: %d en %d min', metric, count, minutes)

    # ── Chequeos de volumen horario (por debajo del mínimo = degradado) ──
    hour = now.hour
    hourly_cutoff = now - timedelta(hours=1)
    hourly_checks = [
        ('leads_low', Lead, 'created', HOURLY_MIN_LEADS),
        ('prellamadas_low', Prellamada, 'creado_en', HOURLY_MIN_PRELLAMADAS),
        ('reservas_low', Reserva, 'fecha_creacion', HOURLY_MIN_RESERVAS),
    ]
    for metric, model, field, thresholds in hourly_checks:
        count = model.objects.filter(**{f'{field}__gte': hourly_cutoff}).count()
        expected_min = thresholds.get(hour, 10)
        if count < expected_min:
            _record_and_send(
                metric,
                f'{model.__name__} por debajo del mínimo ({count}/{expected_min})',
                f'{model.__name__} en la última hora: {count} (mínimo esperado: {expected_min} '
                f'para las {hour}:00 UTC).\n'
                f'Puede indicar problemas con ads, landing pages o APIs.\n'
                f'Hora del check: {now:%Y-%m-%d %H:%M:%S UTC}',
            )
        else:
            logger.info('[Monitoring] %s OK: %d (min=%d) hora %d', metric, count, expected_min, hour)

    # Salud de tareas Celery: leads sin crm_done creados hace 5-60 min
    stale_cutoff = now - timedelta(minutes=60)
    recent_cutoff = now - timedelta(minutes=5)
    stale_leads = (
        Lead.objects
        .filter(created__gte=stale_cutoff, created__lte=recent_cutoff)
        .filter(email__isnull=False)
        .exclude(email='')
        .exclude(tags__name='crm_done')
        .count()
    )
    if stale_leads >= 5:
        _record_and_send(
            'leads_task_stale',
            f'{stale_leads} leads con tareas Celery incompletas',
            f'{stale_leads} leads (creados hace 5-60 min) sin tag crm_done.\n'
            f'Posibles causas: Celery workers caídos, Redis no responde, NeverBounce/CRM caídos.\n'
            f'Hora del check: {now:%Y-%m-%d %H:%M:%S UTC}',
        )
    else:
        logger.info('[Monitoring] leads_task_stale OK: %d stale', stale_leads)
