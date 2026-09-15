"""
Lo que se manda al CRM de cada llamada (Schedule).

El CRM guarda el ID del evento de Google Calendar en
`Schedule.google_calendar_event_id` para poder localizar el evento: detectar
double bookings y transferir la llamada a otro closer.
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from calendario.bookings.conversions.services import crm
from calendario.bookings.models import Reserva
from tests.factories import crear_event_type, crear_host, slot_futuro


@override_settings(CRM_BASE_URL='https://crm.test', CRM_API_KEY='clave')
class PayloadScheduleTest(TestCase):

    def setUp(self):
        host = crear_host()
        inicio = slot_futuro()
        self.reserva = Reserva.objects.create(
            event_type=crear_event_type(host), host=host,
            inicio_utc=inicio, fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado='Lead', email_invitado='lead@ejemplo.com',
            google_event_id='s4pad0kn95ic6tel4d5ikhpkf8',
        )

    def _payload(self):
        with patch.object(crm.requests, 'post', return_value=MagicMock(status_code=201, text='')) as post:
            crm.push_schedule(self.reserva)
        return post.call_args.kwargs['json']

    def test_manda_el_id_del_evento_de_google(self):
        self.assertEqual(self._payload()['google_calendar_event_id'], 's4pad0kn95ic6tel4d5ikhpkf8')

    def test_sin_evento_de_google_no_lo_manda(self):
        self.reserva.google_event_id = ''
        self.reserva.save(update_fields=['google_event_id'])
        self.assertNotIn('google_calendar_event_id', self._payload())
