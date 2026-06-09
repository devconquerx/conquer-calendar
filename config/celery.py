import logging
import os
import sys
from pathlib import Path

from celery import Celery
from celery.signals import task_failure

# manage.py añade <repo>/calendario al sys.path para que apps como `metronic`/
# `layout` (ubicadas en calendario/) sean importables como top-level. El worker
# de Celery no pasa por manage.py, así que replicamos ese insert aquí.
_CALENDARIO_DIR = str(Path(__file__).resolve().parent.parent / 'calendario')
if _CALENDARIO_DIR not in sys.path:
    sys.path.append(_CALENDARIO_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

logger = logging.getLogger(__name__)

app = Celery('calendario')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# Maps task name → (model_app_label, failed_tag).
# El barrido (sweep) salta los objetos con su tag *_failed.
TASK_FAILURE_TAGS = {
    'calendario.leads.tasks.process_meta_capi': ('leads.Lead', 'meta_capi_failed'),
    'calendario.leads.tasks.process_tiktok_events': ('leads.Lead', 'tiktok_events_failed'),
    'calendario.leads.tasks.process_google_ads': ('leads.Lead', 'google_ads_failed'),
    'calendario.leads.tasks.process_respondio': ('leads.Lead', 'respondio_failed'),
    'calendario.leads.tasks.process_activecampaign': ('leads.Lead', 'activecampaign_failed'),
    'calendario.leads.tasks.process_neverbounce': ('leads.Lead', 'neverbounce_failed'),
    'calendario.leads.tasks.process_crm_send': ('leads.Lead', 'crm_failed'),
    'calendario.leads.tasks.process_supabase': ('leads.Lead', 'supabase_failed'),
    'calendario.leads.tasks.process_welcome_email': ('leads.Lead', 'welcome_email_failed'),
    'calendario.bookings.tasks.process_schedule_meta_capi': ('bookings.Reserva', 'sch_meta_capi_failed'),
    'calendario.bookings.tasks.process_schedule_tiktok_events': ('bookings.Reserva', 'sch_tiktok_events_failed'),
    'calendario.bookings.tasks.process_schedule_google_ads': ('bookings.Reserva', 'sch_google_ads_failed'),
    'calendario.bookings.tasks.process_schedule_activecampaign': ('bookings.Reserva', 'sch_activecampaign_failed'),
    'calendario.bookings.tasks.process_schedule_respondio': ('bookings.Reserva', 'sch_respondio_failed'),
    'calendario.bookings.tasks.process_schedule_crm': ('bookings.Reserva', 'sch_crm_failed'),
    'calendario.bookings.tasks.process_schedule_supabase': ('bookings.Reserva', 'sch_supabase_failed'),
    'calendario.funnels.tasks.process_pre_schedule_supabase': ('funnels.Prellamada', 'supabase_failed'),
    'calendario.funnels.tasks.process_pre_schedule_crm': ('funnels.Prellamada', 'crm_failed'),
}


def _tag_as_failed(task_name, args):
    """Añade un tag *_failed al lead/reserva para que el sweep lo salte."""
    mapping = TASK_FAILURE_TAGS.get(task_name)
    if not mapping or not args:
        return

    model_path, failed_tag = mapping
    app_label, model_name = model_path.split('.')

    try:
        from django.apps import apps
        Model = apps.get_model(app_label, model_name)
        obj = Model.objects.get(pk=args[0])
        obj.tags.add(failed_tag)
        logger.info('Tagged %s %s with %s', model_name, args[0], failed_tag)
    except Exception:
        logger.exception('Failed to tag %s %s with %s', model_path, args[0] if args else '?', failed_tag)


def _log_task_failure(task_name, task_id, exception, args, einfo):
    """Guarda un TaskFailureLog (con enlace a Sentry si está disponible)."""
    mapping = TASK_FAILURE_TAGS.get(task_name)
    if not mapping or not args:
        return

    model_path, _ = mapping
    tb_text = ''.join(einfo.traceback) if einfo and hasattr(einfo, 'traceback') else str(einfo or '')

    sentry_event_id = ''
    sentry_url = ''
    try:
        import sentry_sdk
        sentry_event_id = sentry_sdk.last_event_id() or ''
        if sentry_event_id:
            from django.conf import settings
            sentry_org_url = getattr(settings, 'SENTRY_ORG_URL', '')
            if sentry_org_url:
                sentry_url = f'{sentry_org_url}?query={sentry_event_id}'
    except Exception:
        pass

    try:
        from calendario.monitoring.models import TaskFailureLog

        log_kwargs = {
            'task_name': task_name,
            'task_id': str(task_id),
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': tb_text,
            'sentry_event_id': sentry_event_id,
            'sentry_url': sentry_url,
        }

        if 'leads.Lead' in model_path:
            log_kwargs['lead_id'] = args[0]
        elif 'bookings.Reserva' in model_path:
            log_kwargs['reserva_id'] = args[0]

        TaskFailureLog.objects.create(**log_kwargs)
        logger.info('TaskFailureLog created for %s (obj %s)', task_name, args[0])
    except Exception:
        logger.exception('Failed to create TaskFailureLog for %s', task_name)


@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback=None, einfo=None, **kw):
    """Al agotar reintentos: tag *_failed, log de fallo y email de alerta."""
    max_retries = getattr(sender, 'max_retries', None)
    retries = sender.request.retries if sender.request else 0

    if max_retries is not None and retries < max_retries:
        return

    task_name = sender.name or type(sender).__name__

    _tag_as_failed(task_name, args)
    _log_task_failure(task_name, task_id, exception, args, einfo)

    try:
        from calendario.monitoring.tasks import _record_and_send

        tb_text = ''.join(einfo.traceback) if einfo and hasattr(einfo, 'traceback') else str(einfo or '')
        _record_and_send(
            f'task_final_failure:{task_name}',
            f'Task {task_name} falló tras {max_retries} reintentos',
            f'Task: {task_name}\n'
            f'Task ID: {task_id}\n'
            f'Args: {args}\n'
            f'Kwargs: {kwargs}\n'
            f'Reintentos agotados: {retries}/{max_retries}\n'
            f'Excepción: {type(exception).__name__}: {exception}\n\n'
            f'Traceback:\n{tb_text}',
        )
    except Exception:
        logger.exception('Failed to send task-failure alert for %s', task_name)
