import logging

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import GoogleCalendarSyncEstado

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class GoogleWebhookView(View):
    """
    Receptor de notificaciones push de Google Calendar (events.watch).
    Google envía un POST vacío con cabeceras X-Goog-Channel-ID y
    X-Goog-Resource-ID. No trae datos del cambio: solo avisa que algo cambió.
    Se valida el canal registrado, se responde 200 de inmediato y se dispara
    el sync incremental.
    """

    def post(self, request, *args, **kwargs):
        canal_id = request.headers.get('X-Goog-Channel-Id', '')
        resource_id = request.headers.get('X-Goog-Resource-Id', '')
        resource_state = request.headers.get('X-Goog-Resource-State', '')

        if not canal_id:
            logger.warning("webhook: POST sin X-Goog-Channel-Id, ignorado")
            return HttpResponse(status=200)

        # Google envía un primer POST con state='sync' al registrar el canal;
        # es solo una confirmación, no implica cambios.
        if resource_state == 'sync':
            logger.info("webhook: sync handshake canal=%s", canal_id)
            return HttpResponse(status=200)

        try:
            sync_estado = GoogleCalendarSyncEstado.objects.select_related('host').get(
                canal_id=canal_id,
            )
        except GoogleCalendarSyncEstado.DoesNotExist:
            logger.warning(
                "webhook: canal desconocido canal_id=%s resource_id=%s, ignorado",
                canal_id, resource_id,
            )
            return HttpResponse(status=200)

        host = sync_estado.host
        logger.info(
            "webhook: notificación recibida host=%s canal=%s state=%s",
            host.email, canal_id, resource_state,
        )

        # Sync incremental en el mismo request (es rápido si no hay muchos cambios).
        # Si fuera un volumen alto, se podría diferir con transaction.on_commit,
        # pero aquí va directo para minimizar el desfase.
        from .sync import sincronizar_host_incremental
        sincronizar_host_incremental(host)

        return HttpResponse(status=200)
