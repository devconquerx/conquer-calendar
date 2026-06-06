import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_alert_email(subject, body):
    """Envía un email de alerta de monitoreo usando el backend de email configurado (Anymail/Mailgun)."""
    recipients = getattr(settings, 'MONITORING_ALERT_RECIPIENTS', [])
    if not recipients:
        logger.warning('[Monitoring] Sin destinatarios configurados, salto alerta')
        return

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mg.conquerx.com')
    send_mail(
        subject=f'[ALERT] {subject}',
        message=body,
        from_email=from_email,
        recipient_list=recipients,
        fail_silently=False,
    )
    logger.info('[Monitoring] Alerta enviada: %s', subject)
