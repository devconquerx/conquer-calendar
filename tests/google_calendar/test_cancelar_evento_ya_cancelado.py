"""
Cancelar algo que Google ya tiene cancelado no es un error.

Caso real (FUNNELS-3Q): el invitado o el host borran la cita desde su propio
Google Calendar, Google nos avisa por el webhook y llegamos a `cancelar_evento_
google` para marcar un evento que ya está `cancelled`. Google responde 403
Forbidden —comprobado contra la API de producción: NO es falta de permisos, el
mismo host lista eventos sin problema; es Google diciendo que un evento
cancelado ya no se toca—. Los dos sistemas están de acuerdo y no hay nada que
arreglar, pero se registraba como ERROR y llegaba a Sentry.

Un 403 de verdad (delegación mal configurada, host fuera del dominio) sí tiene
que seguir viéndose.
"""
import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from googleapiclient.errors import HttpError

from calendario.bookings.models import Reserva
from calendario.google_calendar.services import cancelar_evento_google
from tests.factories import crear_event_type, crear_host, slot_futuro

EVENT_ID = 'jqhavbjkfrvogmkf46aur2c75o'


def _http_error(status, reason='Forbidden'):
    resp = MagicMock()
    resp.status = status
    resp.reason = reason
    return HttpError(resp, b'{"error": {"message": "Forbidden"}}')


class CancelarEventoYaCanceladoTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        inicio = slot_futuro()
        self.reserva = Reserva.objects.create(
            event_type=self.et, host=self.host,
            inicio_utc=inicio, fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado='Kevin Murillo', email_invitado='kmurillo207@gmail.com',
            estado=Reserva.Estado.CANCELADA, google_event_id=EVENT_ID,
        )

    def _servicio(self, estado_evento, patch_falla_con=None):
        servicio = MagicMock()
        servicio.events().get().execute.return_value = {
            'status': estado_evento, 'attendees': [],
        }
        if patch_falla_con is not None:
            servicio.events().patch().execute.side_effect = patch_falla_con
        return servicio

    def test_evento_ya_cancelado_no_se_toca_ni_se_reporta(self):
        servicio = self._servicio('cancelled')

        with patch('calendario.google_calendar.services.obtener_servicio_calendar',
                   return_value=servicio), \
             self.assertNoLogs('calendario.google_calendar.services', level='ERROR'):
            cancelar_evento_google(self.reserva.pk)

        servicio.events().patch.assert_not_called()

    def test_carrera_se_cancela_entre_el_get_y_el_patch(self):
        """El `get` lo ve vivo, el `patch` llega tarde y se come el 403."""
        servicio = MagicMock()
        # 1ª lectura: vivo. 2ª (la del manejador de error): ya cancelado.
        servicio.events().get().execute.side_effect = [
            {'status': 'confirmed', 'attendees': [{'email': 'x@y.com'}]},
            {'status': 'cancelled', 'attendees': []},
        ]
        servicio.events().patch().execute.side_effect = _http_error(403)

        with patch('calendario.google_calendar.services.obtener_servicio_calendar',
                   return_value=servicio), \
             self.assertNoLogs('calendario.google_calendar.services', level='ERROR'):
            cancelar_evento_google(self.reserva.pk)

    def test_un_403_de_verdad_sigue_siendo_error(self):
        """Si el evento sigue vivo, el 403 es un problema real y tiene que verse."""
        servicio = MagicMock()
        servicio.events().get().execute.return_value = {
            'status': 'confirmed', 'attendees': [],
        }
        servicio.events().patch().execute.side_effect = _http_error(403)

        with patch('calendario.google_calendar.services.obtener_servicio_calendar',
                   return_value=servicio), \
             self.assertLogs('calendario.google_calendar.services', level='ERROR') as log:
            cancelar_evento_google(self.reserva.pk)

        self.assertIn('HttpError 403', '\n'.join(log.output))

    def test_evento_vivo_se_marca_como_cancelado(self):
        """El camino normal no cambia."""
        servicio = self._servicio('confirmed')

        with patch('calendario.google_calendar.services.obtener_servicio_calendar',
                   return_value=servicio):
            cancelar_evento_google(self.reserva.pk)

        servicio.events().patch.assert_called()
        cuerpo = servicio.events().patch.call_args.kwargs['body']
        self.assertTrue(cuerpo['summary'].startswith('Cancelado:'))
        self.assertEqual(cuerpo['transparency'], 'transparent')
