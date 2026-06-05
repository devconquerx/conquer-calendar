import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

COOLDOWN_MINUTES = 30


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
