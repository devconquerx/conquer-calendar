import logging
import os
import sys
from pathlib import Path

from celery import Celery, Task
from celery.exceptions import Ignore
from celery.signals import task_failure, task_retry, task_success

# manage.py añade <repo>/calendario al sys.path para que apps como `metronic`/
# `layout` (ubicadas en calendario/) sean importables como top-level. El worker
# de Celery no pasa por manage.py, así que replicamos ese insert aquí.
_CALENDARIO_DIR = str(Path(__file__).resolve().parent.parent / 'calendario')
if _CALENDARIO_DIR not in sys.path:
    sys.path.append(_CALENDARIO_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

logger = logging.getLogger(__name__)

class TareaResiliente(Task):
    """Base de TODAS las tareas: aplica calendario/core/resiliencia.py.

    - Al encolar: si ya hay una copia pendiente con los mismos argumentos, no se
      encola otra (los sweeps no pueden multiplicar la cola).
    - Al ejecutar: si su servicio tiene el circuito abierto, va por encima de su
      ritmo o ya ocupa todos sus huecos, se aplaza (se reencola con retraso y
      esta ejecución termina en el acto) en vez de esperar ocupando el worker.
    """

    def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                    link=None, link_error=None, shadow=None, **options):
        from celery.utils import uuid
        from calendario.core import resiliencia

        task_id = task_id or uuid()
        try:
            from calendario.core import respaldo
            respaldo.al_encolar(self.name, args)
        except Exception:
            pass
        # Reintentos y aplazamientos (llevan `retries`) son la misma copia que
        # sigue viva: se encolan siempre y renuevan la marca de pendiente.
        if 'retries' in options:
            resiliencia.marcar_pendiente(self.name, args, kwargs, task_id)
        elif not self.app.conf.task_always_eager:
            if not resiliencia.reservar_pendiente(self.name, args, kwargs, task_id):
                logger.info('[Resiliencia] %s%s ya está pendiente: no se encola otra copia',
                            self.name, tuple(args or ()))
                return None
            # Lo que encola un sweep va por el carril de recuperación.
            if resiliencia.carril_actual() == resiliencia.CARRIL_RECUPERACION:
                options['headers'] = {**(options.get('headers') or {}),
                                      'carril': resiliencia.CARRIL_RECUPERACION}
        return super().apply_async(args, kwargs, task_id=task_id, producer=producer,
                                   link=link, link_error=link_error, shadow=shadow, **options)

    def __call__(self, *args, **kwargs):
        req = self.request
        if req.called_directly or req.is_eager:
            return super().__call__(*args, **kwargs)

        from calendario.core import resiliencia

        # Desde que empieza, un cambio nuevo del objeto puede encolar otra copia:
        # esta ya no lo verá.
        resiliencia.soltar_pendiente(self.name, args, kwargs)

        if self.name in resiliencia.SWEEPS:
            with resiliencia.en_carril(resiliencia.CARRIL_RECUPERACION):
                return super().__call__(*args, **kwargs)

        servicio = resiliencia.SERVICIO_DE_TAREA.get(self.name)
        limite = self.time_limit or self.app.conf.task_time_limit or 120
        aplazo = resiliencia.motivo_para_aplazar(
            servicio, req.id, carril=_carril_de(req), ttl_hueco=limite + resiliencia.MARGEN_HUECO,
        )
        if aplazo:
            segundos, motivo = aplazo
            espera = resiliencia.segundos_de_aplazo(segundos, motivo)
            try:
                self.signature_from_request(
                    req, args, kwargs, countdown=espera, retries=req.retries,
                ).apply_async()
            except Exception:
                # Si ni siquiera se puede reencolar, se ejecuta: nunca se pierde.
                logger.exception('[Resiliencia] No se pudo aplazar %s; se ejecuta ya', self.name)
            else:
                logger.info('[Resiliencia] %s%s aplazada %.0fs (%s: %s)%s',
                            self.name, args, espera, servicio, motivo,
                            ' [recuperación]' if _carril_de(req) else '')
                raise Ignore()
            servicio = None  # no ocupó hueco

        try:
            return super().__call__(*args, **kwargs)
        finally:
            if servicio:
                resiliencia.soltar_hueco(servicio, req.id)


    def retry(self, args=None, kwargs=None, exc=None, throw=True, eta=None, countdown=None,
              max_retries=None, **options):
        """Un fallo DEL SERVICIO (timeout, 5xx, 429, conexión) no gasta reintentos:
        la tarea se aplaza con espera creciente y lo sigue intentando hasta
        resiliencia.PACIENCIA_SERVICIO (24 h). Así un servicio lento o caído un
        rato nunca da un envío por perdido. Los fallos nuestros (un 400, un
        objeto borrado) siguen el camino normal: sus reintentos y, al agotarlos,
        el tag *_failed y la alerta."""
        from calendario.core import resiliencia

        req = self.request
        if (exc is not None and not req.called_directly and not req.is_eager
                and resiliencia.tiene_paciencia(self.name)
                and resiliencia.es_fallo_del_servicio(exc)):
            headers = dict(getattr(req, 'headers', None) or {})
            ahora = resiliencia.time.time()
            desde = float(headers.get('servicio_desde') or ahora)
            if ahora - desde < resiliencia.PACIENCIA_SERVICIO:
                aplazos = int(headers.get('servicio_aplazos') or 0) + 1
                espera = resiliencia.espera_tras_fallo(aplazos)
                resiliencia.registrar_fallo(resiliencia.SERVICIO_DE_TAREA.get(self.name), exc)
                headers.update(servicio_desde=desde, servicio_aplazos=aplazos)
                try:
                    self.signature_from_request(
                        req, args, kwargs, countdown=espera, retries=req.retries, headers=headers,
                    ).apply_async()
                except Exception:
                    logger.exception('[Resiliencia] No se pudo aplazar %s tras fallo del servicio', self.name)
                else:
                    logger.warning('[Resiliencia] %s%s: fallo del servicio (%s), aplazo %d en %.0fs '
                                   '(sin gastar reintento; lleva %.0f min)', self.name, tuple(req.args or ()),
                                   type(exc).__name__, aplazos, espera, (ahora - desde) / 60)
                    raise Ignore()
        return super().retry(args=args, kwargs=kwargs, exc=exc, throw=throw, eta=eta,
                             countdown=countdown, max_retries=max_retries, **options)


def _carril_de(req):
    """El carril viaja como header del mensaje (y se conserva al aplazar)."""
    headers = getattr(req, 'headers', None)
    if isinstance(headers, dict) and headers.get('carril'):
        return headers['carril']
    return getattr(req, 'carril', None)


app = Celery('calendario', task_cls=TareaResiliente)
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


def _rutas():
    from calendario.core.resiliencia import RUTAS
    return {nombre: {'queue': cola} for nombre, cola in RUTAS.items()}


app.conf.task_routes = _rutas()


@task_success.connect
def _exito_servicio(sender=None, **kw):
    from calendario.core import resiliencia
    resiliencia.registrar_exito(resiliencia.SERVICIO_DE_TAREA.get(getattr(sender, 'name', '')))


@task_retry.connect
def _reintento_servicio(sender=None, reason=None, **kw):
    from calendario.core import resiliencia
    resiliencia.registrar_fallo(resiliencia.SERVICIO_DE_TAREA.get(getattr(sender, 'name', '')), reason)


@task_failure.connect
def _fallo_servicio(sender=None, exception=None, **kw):
    from calendario.core import resiliencia
    resiliencia.registrar_fallo(resiliencia.SERVICIO_DE_TAREA.get(getattr(sender, 'name', '')), exception)


# Maps task name → (model_app_label, failed_tag).
# El barrido (sweep) salta los objetos con su tag *_failed.
TASK_FAILURE_TAGS = {
    'calendario.leads.tasks.process_meta_capi': ('leads.Lead', 'meta_capi_failed'),
    'calendario.leads.tasks.process_tiktok_events': ('leads.Lead', 'tiktok_events_failed'),
    'calendario.leads.tasks.process_google_ads': ('leads.Lead', 'google_ads_failed'),
    'calendario.leads.tasks.process_respondio': ('leads.Lead', 'respondio_failed'),
    'calendario.leads.tasks.process_activecampaign': ('leads.Lead', 'activecampaign_failed'),
    'calendario.leads.tasks.process_crm_send': ('leads.Lead', 'crm_failed'),
    'calendario.leads.tasks.process_supabase': ('leads.Lead', 'supabase_failed'),
    'calendario.bookings.tasks.process_schedule_meta_capi': ('bookings.Reserva', 'sch_meta_capi_failed'),
    'calendario.bookings.tasks.process_schedule_tiktok_events': ('bookings.Reserva', 'sch_tiktok_events_failed'),
    'calendario.bookings.tasks.process_schedule_google_ads': ('bookings.Reserva', 'sch_google_ads_failed'),
    'calendario.bookings.tasks.process_schedule_activecampaign': ('bookings.Reserva', 'sch_activecampaign_failed'),
    'calendario.bookings.tasks.process_schedule_respondio': ('bookings.Reserva', 'sch_respondio_failed'),
    'calendario.bookings.tasks.process_schedule_crm': ('bookings.Reserva', 'sch_crm_failed'),
    'calendario.bookings.tasks.process_schedule_supabase': ('bookings.Reserva', 'sch_supabase_failed'),
    'calendario.bookings.tasks.process_academia_sesion': ('bookings.Reserva', 'sch_academia_failed'),
    'calendario.bookings.tasks.process_academia_cancelacion': ('bookings.Reserva', 'sch_academia_cancelacion_failed'),
    'calendario.funnels.tasks.process_pre_schedule_supabase': ('funnels.Prellamada', 'supabase_failed'),
    'calendario.funnels.tasks.process_pre_schedule_crm': ('funnels.Prellamada', 'crm_failed'),
    'calendario.funnels.tasks.process_pre_schedule_respondio': ('funnels.Prellamada', 'respondio_failed'),
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

        # El objeto puede haberse borrado entre que la tarea se encoló y falló
        # —de hecho esa es una de las razones POR LAS QUE falla: la tarea busca
        # su Reserva y ya no está—. Enlazarlo entonces revienta con un
        # IntegrityError de clave ajena y se pierde el registro entero, que es
        # justo lo que no puede pasar aquí (FUNNELS-DQ/DT).
        #
        # Ambos FK admiten null, así que sin objeto se guarda igual y el id se
        # deja en el mensaje: sin él, un fallo suelto no se puede rastrear.
        campo = 'lead_id' if 'leads.Lead' in model_path else (
            'reserva_id' if 'bookings.Reserva' in model_path else None
        )
        if campo:
            from django.apps import apps
            Modelo = apps.get_model(*model_path.split('.'))
            if Modelo.objects.filter(pk=args[0]).exists():
                log_kwargs[campo] = args[0]
            else:
                log_kwargs['exception_message'] = (
                    f'{log_kwargs["exception_message"]} '
                    f'[{model_path} {args[0]} ya no existe: se registra sin enlace]'
                )

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
